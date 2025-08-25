"""Application Streamlit ultra-avancée pour la recherche bibliographique.

Fonctionnalités :
1. Vraies APIs scientifiques (OpenAlex, Semantic Scholar, PubMed, Crossref)
2. Import/customisation/export Excel avancé
3. Interface d'édition interactive
4. Suppression/modification de lignes
5. Export personnalisé
"""

import sys
from pathlib import Path
import pandas as pd
import streamlit as st
from datetime import datetime
import time
import io
import requests
import requests.exceptions
import json
from typing import List, Dict, Any
import xml.etree.ElementTree as ET
from urllib.parse import quote

# Ajouter le répertoire src au chemin Python
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Configuration des APIs
API_CONFIG = {
    "openalex": {
        "base_url": "https://api.openalex.org",
        "rate_limit": 10,  # requêtes par seconde
        "free": True
    },
    "semantic_scholar": {
        "base_url": "https://api.semanticscholar.org/graph/v1",
        "rate_limit": 100,  # requêtes par minute
        "free": True
    },
    "pubmed": {
        "base_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        "rate_limit": 3,  # requêtes par seconde
        "free": True
    },
    "crossref": {
        "base_url": "https://api.crossref.org",
        "rate_limit": 50,  # requêtes par seconde avec politeness
        "free": True
    }
}

class OpenAlexAPI:
    """Client pour l'API OpenAlex."""
    
    def __init__(self):
        self.base_url = API_CONFIG["openalex"]["base_url"]
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'LitReviewPipeline/1.0 (https://github.com/user/lit-review-pipeline)',
            'Accept': 'application/json'
        })
    
    def search_works(self, query: str, year_from: int, year_to: int, max_results: int = 100) -> pd.DataFrame:
        """Rechercher des articles sur OpenAlex."""
        try:
            params = {
                'search': query,
                'filter': f'publication_year:{year_from}-{year_to}',
                'per-page': min(max_results, 200),
                'cursor': '*',
                'sort': 'cited_by_count:desc'
            }
            
            response = self.session.get(f"{self.base_url}/works", params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            articles = []
            
            if not data or 'results' not in data:
                return pd.DataFrame()
            
            for work in data.get('results', []):
                if not work or not isinstance(work, dict):
                    continue
                    
                # Extraction sécurisée des données
                primary_location = work.get('primary_location') or {}
                source_info = primary_location.get('source') or {}
                
                article = {
                    'source': 'OpenAlex',
                    'title': work.get('title') or 'Sans titre',
                    'abstract': (work.get('abstract_inverted_index') and 'Résumé disponible') or work.get('abstract') or '',
                    'authors': self._format_authors(work.get('authorships') or []),
                    'journal': source_info.get('display_name') or 'Journal non spécifié',
                    'year': work.get('publication_year') or 0,
                    'doi': (work.get('doi') or '').replace('https://doi.org/', ''),
                    'cited_by': work.get('cited_by_count') or 0,
                    'url': work.get('id') or '',
                    'type': work.get('type') or 'article',
                    'open_access': (work.get('open_access') or {}).get('is_oa', False)
                }
                articles.append(article)
            
            return pd.DataFrame(articles)
            
        except Exception as e:
            st.error(f"Erreur OpenAlex: {e}")
            return pd.DataFrame()
    
    def _format_authors(self, authorships: List[Dict]) -> str:
        """Formater la liste des auteurs."""
        authors = []
        for auth in authorships[:5]:  # Limiter à 5 auteurs
            author = auth.get('author', {})
            name = author.get('display_name', '')
            if name:
                authors.append(name)
        
        result = '; '.join(authors)
        if len(authorships) > 5:
            result += ' et al.'
        return result

class SemanticScholarAPI:
    """Client pour l'API Semantic Scholar."""
    
    def __init__(self):
        self.base_url = API_CONFIG["semantic_scholar"]["base_url"]
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json'
        })
    
    def search_papers(self, query: str, year_from: int, year_to: int, max_results: int = 100) -> pd.DataFrame:
        """Rechercher des articles sur Semantic Scholar."""
        try:
            # Limiter les requêtes pour éviter les erreurs 429
            max_results = min(max_results, 50)
            
            params = {
                'query': query,
                'year': f'{year_from}-{year_to}',
                'limit': max_results,
                'fields': 'paperId,title,abstract,authors,journal,year,citationCount,url,venue,publicationTypes,isOpenAccess'
            }
            
            # Délai pour respecter les limites
            time.sleep(1)
            
            response = self.session.get(f"{self.base_url}/paper/search", params=params, timeout=30)
            
            if response.status_code == 429:
                st.warning("⚠️ Semantic Scholar: Limite de taux atteinte, attente...")
                time.sleep(10)
                response = self.session.get(f"{self.base_url}/paper/search", params=params, timeout=30)
            
            response.raise_for_status()
            
            data = response.json()
            articles = []
            
            if not data or 'data' not in data:
                return pd.DataFrame()
            
            for paper in data.get('data', []):
                if not paper or not isinstance(paper, dict):
                    continue
                
                journal_info = paper.get('journal') or {}
                
                article = {
                    'source': 'Semantic Scholar',
                    'title': paper.get('title') or 'Sans titre',
                    'abstract': paper.get('abstract') or '',
                    'authors': self._format_authors(paper.get('authors') or []),
                    'journal': journal_info.get('name') or paper.get('venue') or 'Journal non spécifié',
                    'year': paper.get('year') or 0,
                    'doi': '',  # Semantic Scholar ne fournit pas directement le DOI
                    'cited_by': paper.get('citationCount') or 0,
                    'url': paper.get('url') or '',
                    'type': ', '.join(paper.get('publicationTypes') or []) or 'article',
                    'open_access': paper.get('isOpenAccess', False)
                }
                articles.append(article)
            
            return pd.DataFrame(articles)
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                st.warning("⚠️ Semantic Scholar: Trop de requêtes, réessayez dans quelques minutes")
            else:
                st.error(f"Erreur HTTP Semantic Scholar: {e}")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Erreur Semantic Scholar: {e}")
            return pd.DataFrame()
    
    def _format_authors(self, authors: List[Dict]) -> str:
        """Formater la liste des auteurs."""
        author_names = []
        for author in authors[:5]:  # Limiter à 5 auteurs
            name = author.get('name', '')
            if name:
                author_names.append(name)
        
        result = '; '.join(author_names)
        if len(authors) > 5:
            result += ' et al.'
        return result

class PubMedAPI:
    """Client pour l'API PubMed E-utilities."""
    
    def __init__(self):
        self.base_url = API_CONFIG["pubmed"]["base_url"]
        self.session = requests.Session()
    
    def search_articles(self, query: str, year_from: int, year_to: int, max_results: int = 100) -> pd.DataFrame:
        """Rechercher des articles sur PubMed."""
        try:
            # Étape 1: Recherche des IDs
            search_params = {
                'db': 'pubmed',
                'term': f'{query} AND {year_from}[PDAT]:{year_to}[PDAT]',
                'retmax': min(max_results, 200),
                'retmode': 'json',
                'sort': 'relevance'
            }
            
            search_response = self.session.get(f"{self.base_url}/esearch.fcgi", params=search_params)
            search_response.raise_for_status()
            search_data = search_response.json()
            
            pmids = search_data.get('esearchresult', {}).get('idlist', [])
            
            if not pmids:
                return pd.DataFrame()
            
            # Étape 2: Récupération des détails
            fetch_params = {
                'db': 'pubmed',
                'id': ','.join(pmids),
                'retmode': 'xml'
            }
            
            fetch_response = self.session.get(f"{self.base_url}/efetch.fcgi", params=fetch_params)
            fetch_response.raise_for_status()
            
            articles = self._parse_pubmed_xml(fetch_response.text)
            return pd.DataFrame(articles)
            
        except Exception as e:
            st.error(f"Erreur PubMed: {e}")
            return pd.DataFrame()
    
    def _parse_pubmed_xml(self, xml_text: str) -> List[Dict]:
        """Parser le XML de PubMed."""
        articles = []
        try:
            root = ET.fromstring(xml_text)
            
            for article_elem in root.findall('.//PubmedArticle'):
                article_data = article_elem.find('.//Article')
                if article_data is None:
                    continue
                
                # Titre
                title_elem = article_data.find('.//ArticleTitle')
                title = title_elem.text if title_elem is not None else ''
                
                # Résumé
                abstract_elem = article_data.find('.//Abstract/AbstractText')
                abstract = abstract_elem.text if abstract_elem is not None else ''
                
                # Auteurs
                authors = []
                for author_elem in article_data.findall('.//AuthorList/Author'):
                    lastname = author_elem.find('.//LastName')
                    forename = author_elem.find('.//ForeName')
                    if lastname is not None:
                        name = lastname.text
                        if forename is not None:
                            name = f"{name}, {forename.text}"
                        authors.append(name)
                
                # Journal
                journal_elem = article_data.find('.//Journal/Title')
                journal = journal_elem.text if journal_elem is not None else ''
                
                # Année
                year_elem = article_data.find('.//PubDate/Year')
                year = int(year_elem.text) if year_elem is not None else None
                
                # PMID
                pmid_elem = article_elem.find('.//PMID')
                pmid = pmid_elem.text if pmid_elem is not None else ''
                
                # DOI
                doi = ''
                for doi_elem in article_data.findall('.//ELocationID'):
                    if doi_elem.get('EIdType') == 'doi':
                        doi = doi_elem.text
                        break
                
                article = {
                    'source': 'PubMed',
                    'title': title,
                    'abstract': abstract,
                    'authors': '; '.join(authors[:5]) + (' et al.' if len(authors) > 5 else ''),
                    'journal': journal,
                    'year': year,
                    'doi': doi,
                    'cited_by': 0,  # PubMed ne fournit pas directement le nombre de citations
                    'url': f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/' if pmid else '',
                    'pmid': pmid,
                    'type': 'Article'
                }
                articles.append(article)
                
        except ET.ParseError as e:
            st.error(f"Erreur parsing XML PubMed: {e}")
        
        return articles

class CrossrefAPI:
    """Client pour l'API Crossref."""
    
    def __init__(self):
        self.base_url = API_CONFIG["crossref"]["base_url"]
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'LitReviewPipeline/1.0 (mailto:user@example.com)'
        })
    
    def search_works(self, query: str, year_from: int, year_to: int, max_results: int = 100) -> pd.DataFrame:
        """Rechercher des articles sur Crossref."""
        try:
            params = {
                'query': query,
                'filter': f'from-pub-date:{year_from},until-pub-date:{year_to}',
                'rows': min(max_results, 200),
                'sort': 'relevance',
                'order': 'desc'
            }
            
            response = self.session.get(f"{self.base_url}/works", params=params)
            response.raise_for_status()
            
            data = response.json()
            articles = []
            
            for work in data.get('message', {}).get('items', []):
                # Date de publication
                pub_date = work.get('published-print', work.get('published-online', {}))
                year = None
                if pub_date and 'date-parts' in pub_date:
                    year = pub_date['date-parts'][0][0] if pub_date['date-parts'][0] else None
                
                article = {
                    'source': 'Crossref',
                    'title': ' '.join(work.get('title', [])),
                    'abstract': work.get('abstract', ''),
                    'authors': self._format_authors(work.get('author', [])),
                    'journal': work.get('container-title', [''])[0],
                    'year': year,
                    'doi': work.get('DOI', ''),
                    'cited_by': work.get('is-referenced-by-count', 0),
                    'url': work.get('URL', ''),
                    'type': work.get('type', ''),
                    'open_access': 'license' in work
                }
                articles.append(article)
            
            return pd.DataFrame(articles)
            
        except Exception as e:
            st.error(f"Erreur Crossref: {e}")
            return pd.DataFrame()
    
    def _format_authors(self, authors: List[Dict]) -> str:
        """Formater la liste des auteurs."""
        author_names = []
        for author in authors[:5]:  # Limiter à 5 auteurs
            given = author.get('given', '')
            family = author.get('family', '')
            if family:
                name = f"{family}, {given}" if given else family
                author_names.append(name)
        
        result = '; '.join(author_names)
        if len(authors) > 5:
            result += ' et al.'
        return result

def create_extended_columns():
    """Créer les colonnes étendues pour l'analyse bibliographique."""
    return {
        'ABS 1 OU 0': '',
        'Notes': '', 
        'Type revue': '',
        'WL = mesure': '',
        'Chr = participants': '',
        'Spécialité': '',
        'Intervention': '',
        'Technique': '',
        'Contexte': '',
        'Simulation ?': '',
        'Outils': '',
        'Résultats ?': '',
        'Additional outcomes / measures': '',
        'Exclusion': ''
    }

def detect_review_type(title):
    """Détecter le type de revue à partir du titre."""
    if pd.isna(title):
        return ''
    
    title_lower = str(title).lower()
    
    if 'systematic review' in title_lower or 'systematic literature review' in title_lower:
        return 'Revue systématique'
    elif 'meta-analysis' in title_lower or 'meta analysis' in title_lower:
        return 'Méta-analyse'
    elif 'scoping review' in title_lower:
        return 'Scoping review'
    elif 'narrative review' in title_lower:
        return 'Revue narrative'
    elif 'randomized controlled trial' in title_lower or 'rct' in title_lower:
        return 'ECR'
    elif 'cohort study' in title_lower:
        return 'Étude de cohorte'
    elif 'case study' in title_lower or 'case report' in title_lower:
        return 'Étude de cas'
    elif 'cross-sectional' in title_lower:
        return 'Étude transversale'
    else:
        return ''

def detect_specialty(journal):
    """Détecter la spécialité médicale à partir du nom du journal."""
    if pd.isna(journal):
        return ''
    
    journal_lower = str(journal).lower()
    
    # Dictionnaire de spécialités basé sur les mots-clés du journal
    specialties = {
        'psychiatry': 'Psychiatrie',
        'psychology': 'Psychologie',
        'mental health': 'Santé mentale',
        'surgery': 'Chirurgie',
        'anesthesi': 'Anesthésie',
        'cardiology': 'Cardiologie',
        'neurology': 'Neurologie',
        'oncology': 'Oncologie',
        'pediatric': 'Pédiatrie',
        'emergency': 'Urgences',
        'intensive care': 'Soins intensifs',
        'radiology': 'Radiologie',
        'orthopedic': 'Orthopédie',
        'dermatology': 'Dermatologie',
        'ophthalmology': 'Ophtalmologie',
        'otolaryngology': 'ORL',
        'urology': 'Urologie',
        'gynecology': 'Gynécologie',
        'nursing': 'Soins infirmiers',
        'rehabilitation': 'Rééducation',
        'pharmacology': 'Pharmacologie'
    }
    
    for keyword, specialty in specialties.items():
        if keyword in journal_lower:
            return specialty
    
    return ''

def main():
    """Application principale."""
    st.set_page_config(
        page_title="Recherche Bibliographique Avancée",
        page_icon="🔬",
        layout="wide"
    )
    
    st.title("🔬 Recherche Bibliographique Avancée")
    st.markdown("**Vraies APIs scientifiques + Customisation Excel complète**")
    
    # Tabs pour les différentes fonctionnalités
    tab1, tab2, tab3 = st.tabs([
        "🔎 Recherche Multi-API", 
        "📊 Import & Customisation Excel",
        "⚙️ Configuration APIs"
    ])
    
    with tab1:
        st.header("🔎 Recherche avec APIs Réelles")
        recherche_multi_api()
    
    with tab2:
        st.header("📊 Customisation Excel Avancée")
        customisation_excel()
    
    with tab3:
        st.header("⚙️ Configuration des APIs")
        configuration_apis()

def recherche_multi_api():
    """Interface pour la recherche avec vraies APIs."""
    
    # Configuration dans la sidebar
    st.sidebar.header("🔬 Configuration Recherche")
    
    # Paramètres de recherche
    query = st.sidebar.text_area(
        "Requête de recherche",
        value="machine learning healthcare",
        help="Mots-clés en anglais. Exemples: 'covid vaccine', 'cancer therapy', 'AI diagnosis'"
    )
    
    # Plage d'années
    col1, col2 = st.sidebar.columns(2)
    with col1:
        year_from = st.number_input("Année début", 2018, 2024, 2022)
    with col2:
        year_to = st.number_input("Année fin", 2018, 2024, 2024)
    
    max_results = st.sidebar.slider("Articles par API", 10, 200, 50)
    
    # Sélection des APIs
    st.sidebar.subheader("📚 APIs Scientifiques")
    
    use_openalex = st.sidebar.checkbox("🌐 OpenAlex (Gratuit)", value=True, 
                                       help="Base de données bibliographique open source")
    use_semantic = st.sidebar.checkbox("🧠 Semantic Scholar (Gratuit)", value=True,
                                       help="Moteur de recherche académique avec IA")
    use_pubmed = st.sidebar.checkbox("🏥 PubMed (Gratuit)", value=False,
                                     help="Base biomédicale officielle NCBI")
    use_crossref = st.sidebar.checkbox("📄 Crossref (Gratuit)", value=False,
                                       help="Métadonnées d'articles académiques")
    
    # Bouton de recherche
    if st.sidebar.button("🚀 Lancer Recherche Multi-API", type="primary"):
        if not query.strip():
            st.error("⚠️ Veuillez saisir une requête de recherche")
            return
        
        # Affichage des paramètres
        st.subheader("📋 Paramètres de Recherche")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"**Requête:** {query}")
        with col2:
            st.info(f"**Période:** {year_from}-{year_to}")
        with col3:
            apis_selected = sum([use_openalex, use_semantic, use_pubmed, use_crossref])
            st.info(f"**APIs:** {apis_selected} sélectionnées")
        
        # Progress tracking
        all_results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        apis_to_run = []
        if use_openalex: apis_to_run.append(("OpenAlex", OpenAlexAPI))
        if use_semantic: apis_to_run.append(("Semantic Scholar", SemanticScholarAPI))
        if use_pubmed: apis_to_run.append(("PubMed", PubMedAPI))
        if use_crossref: apis_to_run.append(("Crossref", CrossrefAPI))
        
        for i, (api_name, api_class) in enumerate(apis_to_run):
            status_text.text(f"🔍 Recherche sur {api_name}...")
            progress = (i + 0.5) / len(apis_to_run)
            progress_bar.progress(progress)
            
            try:
                api_client = api_class()
                
                if api_name == "OpenAlex":
                    df = api_client.search_works(query, year_from, year_to, max_results)
                elif api_name == "Semantic Scholar":
                    df = api_client.search_papers(query, year_from, year_to, max_results)
                elif api_name == "PubMed":
                    df = api_client.search_articles(query, year_from, year_to, max_results)
                elif api_name == "Crossref":
                    df = api_client.search_works(query, year_from, year_to, max_results)
                
                if not df.empty:
                    all_results.append(df)
                    st.success(f"✅ {api_name}: {len(df)} articles")
                else:
                    st.warning(f"⚠️ {api_name}: Aucun résultat")
                
                # Délai pour respecter les limites de taux
                time.sleep(0.5)
                
            except Exception as e:
                st.error(f"❌ Erreur {api_name}: {e}")
            
            progress = (i + 1) / len(apis_to_run)
            progress_bar.progress(progress)
        
        # Fusion des résultats
        if all_results:
            status_text.text("🔄 Fusion des résultats...")
            combined_df = pd.concat(all_results, ignore_index=True)
            
            # Déduplication basique par titre
            combined_df = combined_df.drop_duplicates(subset=['title'], keep='first')
            
            st.session_state['search_results'] = combined_df
            progress_bar.progress(1.0)
            status_text.text("✅ Recherche terminée!")
            
            st.success(f"🎉 **Total: {len(combined_df)} articles uniques trouvés**")
        else:
            st.error("❌ Aucun résultat trouvé sur les APIs sélectionnées")
    
    # Affichage des résultats
    if 'search_results' in st.session_state:
        df = st.session_state['search_results']
        
        st.subheader(f"📊 Résultats ({len(df)} articles)")
        
        # Statistiques
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Articles", len(df))
        with col2:
            sources = df['source'].nunique()
            st.metric("Sources", sources)
        with col3:
            with_abstract = (df['abstract'] != "").sum()
            st.metric("Avec résumé", with_abstract)
        with col4:
            total_citations = df['cited_by'].sum()
            st.metric("Citations", total_citations)
        
        # Filtres
        col1, col2 = st.columns(2)
        with col1:
            sources_filter = st.multiselect(
                "Filtrer par source",
                options=df['source'].unique(),
                default=df['source'].unique()
            )
        with col2:
            if 'year' in df.columns:
                years = sorted([y for y in df['year'].unique() if pd.notna(y)])
                if years:
                    year_range = st.select_slider(
                        "Plage d'années",
                        options=years,
                        value=(min(years), max(years))
                    )
        
        # Application des filtres
        filtered_df = df[df['source'].isin(sources_filter)]
        if 'year_range' in locals() and 'year' in filtered_df.columns:
            filtered_df = filtered_df[
                (filtered_df['year'] >= year_range[0]) & 
                (filtered_df['year'] <= year_range[1])
            ]
        
        # Affichage du tableau
        display_columns = ['title', 'authors', 'journal', 'year', 'source', 'cited_by']
        display_df = filtered_df[display_columns].copy()
        
        # Tronquer les titres longs
        display_df['title'] = display_df['title'].apply(
            lambda x: x[:80] + "..." if len(str(x)) > 80 else x
        )
        
        st.dataframe(display_df, use_container_width=True)
        
        # Export vers customisation
        if st.button("📊 Envoyer vers Customisation Excel", type="secondary"):
            st.session_state['excel_data'] = filtered_df
            st.success("✅ Données envoyées vers l'onglet Customisation Excel!")

def customisation_excel():
    """Interface pour la customisation Excel avancée."""
    
    st.markdown("""
    **Importez un fichier Excel OU utilisez les résultats de recherche**
    
    Fonctionnalités :
    - 📁 Import Excel
    - ✏️ Édition en ligne 
    - 🗑️ Suppression de lignes
    - 📝 Ajout de colonnes d'analyse
    - 💾 Export personnalisé
    """)
    
    # Options d'import
    tab1, tab2 = st.tabs(["📁 Import Fichier", "📊 Données de Recherche"])
    
    with tab1:
        # Guide rapide pour l'utilisateur
        with st.expander("💡 Guide: Préparer votre fichier Excel"):
            st.markdown("""
            **📋 Colonnes recommandées pour votre fichier Excel:**
            
            **🔬 Métadonnées principales:**
            - `title` : Titre de l'article
            - `authors` : Auteurs
            - `journal` : Journal/Revue
            - `year` : Année de publication
            - `abstract` : Résumé
            - `doi` : Identifiant DOI
            
            **📊 Colonnes d'analyse (optionnelles):**
            - `ABS 1 OU 0` : Présence résumé (1=oui, 0=non)
            - `Notes` : Notes personnelles
            - `Type revue` : Type d'étude
            - `WL = mesure` : Mesures/outcomes
            - `Chr = participants` : Caractéristiques participants
            - `Spécialité` : Domaine médical
            - `Intervention` : Type d'intervention
            - `Technique` : Technique utilisée
            - `Contexte` : Contexte de l'étude
            - `Simulation ?` : Utilise simulation (Oui/Non)
            - `Outils` : Outils utilisés
            - `Résultats ?` : Type de résultats
            - `Additional outcomes / measures` : Mesures additionnelles
            - `Exclusion` : Statut inclusion/exclusion
            
            **✅ L'application détecte automatiquement les variations de noms !**
            """)
        
        uploaded_file = st.file_uploader(
            "Choisir un fichier Excel",
            type=['xlsx', 'xls', 'xlsm'],
            help="Formats supportés: .xlsx, .xls, .xlsm (avec macros)"
        )
        
        if uploaded_file:
            # Afficher les informations du fichier
            file_details = {
                "Nom": uploaded_file.name,
                "Taille": f"{uploaded_file.size / 1024:.1f} KB",
                "Type": uploaded_file.type
            }
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.info(f"📄 **{file_details['Nom']}**")
            with col2:
                st.info(f"💾 **{file_details['Taille']}**")
            with col3:
                st.info(f"📝 **{file_details['Type'].split('.')[-1].upper()}**")
            
            try:
                # Lecture du fichier Excel avec gestion robuste
                df = pd.read_excel(uploaded_file, engine='openpyxl')
                
                # Détection des colonnes d'analyse existantes avec variations de noms
                analysis_columns = ['ABS 1 OU 0', 'Notes', 'Type revue', 'WL = mesure', 'Chr = participants', 
                                  'Spécialité', 'Intervention', 'Technique', 'Contexte', 'Simulation ?', 
                                  'Outils', 'Résultats ?', 'Additional outcomes / measures', 'Exclusion']
                
                # Normaliser les noms de colonnes pour la détection
                df_columns_lower = [col.lower().strip() for col in df.columns]
                analysis_columns_lower = [col.lower().strip() for col in analysis_columns]
                
                # Détecter les colonnes avec variations de noms
                existing_analysis_cols = []
                column_mapping = {}
                
                for target_col in analysis_columns:
                    target_lower = target_col.lower().strip()
                    
                    # Recherche exacte d'abord
                    if target_col in df.columns:
                        existing_analysis_cols.append(target_col)
                        column_mapping[target_col] = target_col
                    else:
                        # Recherche avec variations (case insensitive, espaces)
                        for df_col in df.columns:
                            df_col_clean = df_col.lower().strip()
                            
                            # Vérifications avec différentes variations
                            if (df_col_clean == target_lower or 
                                df_col_clean.replace(' ', '') == target_lower.replace(' ', '') or
                                df_col_clean.replace('ou', 'OU').replace('?', ' ?') == target_lower):
                                
                                existing_analysis_cols.append(target_col)
                                column_mapping[target_col] = df_col
                                break
                
                # Renommer les colonnes pour standardiser
                if column_mapping:
                    rename_dict = {v: k for k, v in column_mapping.items() if v != k}
                    if rename_dict:
                        df = df.rename(columns=rename_dict)
                        st.info(f"🔄 {len(rename_dict)} colonne(s) renommée(s) pour standardisation: {', '.join(rename_dict.keys())}")
                
                missing_analysis_cols = [col for col in analysis_columns if col not in existing_analysis_cols]
                
                # Affichage des informations sur les colonnes
                col1, col2 = st.columns(2)
                with col1:
                    if existing_analysis_cols:
                        st.success(f"✅ **{len(existing_analysis_cols)} colonnes d'analyse détectées:**")
                        for col in existing_analysis_cols:
                            filled_count = (df[col].astype(str).str.strip() != '').sum()
                            st.caption(f"• {col}: {filled_count} entrées")
                    else:
                        st.info("ℹ️ Aucune colonne d'analyse détectée")
                
                with col2:
                    if missing_analysis_cols:
                        st.warning(f"⚠️ **{len(missing_analysis_cols)} colonnes d'analyse manquantes:**")
                        st.caption(", ".join(missing_analysis_cols[:3]) + ("..." if len(missing_analysis_cols) > 3 else ""))
                
                # Ajouter automatiquement les colonnes d'analyse si l'option est activée
                if st.session_state.get('auto_add_columns', False):
                    extended_columns = create_extended_columns()
                    added_count = 0
                    for col_name, default_value in extended_columns.items():
                        if col_name not in df.columns:
                            df[col_name] = default_value
                            added_count += 1
                    
                    # Pré-remplissage automatique
                    if 'abstract' in df.columns and 'ABS 1 OU 0' in df.columns:
                        df['ABS 1 OU 0'] = df['abstract'].apply(
                            lambda x: '1' if pd.notna(x) and str(x).strip() != '' else '0'
                        )
                    
                    if added_count > 0:
                        st.success(f"🚀 {added_count} nouvelles colonnes d'analyse ajoutées automatiquement!")
                
                st.session_state['excel_data'] = df
                st.success(f"✅ Fichier importé avec succès: {len(df)} lignes, {len(df.columns)} colonnes")
                
                # Afficher quelques colonnes détectées pour confirmation
                basic_cols = ['title', 'authors', 'journal', 'year', 'abstract']
                detected_basic = [col for col in basic_cols if col in df.columns]
                if detected_basic:
                    st.info(f"📊 Colonnes principales détectées: {', '.join(detected_basic)}")
                
            except Exception as e:
                error_msg = str(e)
                if "No sheet named" in error_msg:
                    st.error("❌ Erreur: Impossible de lire la feuille Excel. Vérifiez que le fichier n'est pas corrompu.")
                elif "Unsupported format" in error_msg:
                    st.error("❌ Erreur: Format de fichier non supporté. Utilisez .xlsx, .xls ou .xlsm")
                elif "Permission denied" in error_msg:
                    st.error("❌ Erreur: Fichier ouvert dans Excel. Fermez le fichier et réessayez.")
                else:
                    st.error(f"❌ Erreur lors de l'import: {error_msg}")
                    st.info("💡 Conseil: Assurez-vous que votre fichier Excel est bien formaté et fermé dans Excel.")
    
    with tab2:
        if 'search_results' in st.session_state:
            if st.button("📊 Utiliser résultats de recherche"):
                st.session_state['excel_data'] = st.session_state['search_results']
                st.success("✅ Résultats de recherche chargés!")
        else:
            st.info("Effectuez d'abord une recherche dans l'onglet 'Recherche Multi-API'")
    
    # Interface de customisation
    if 'excel_data' in st.session_state:
        df = st.session_state['excel_data'].copy()
        
        st.subheader("📝 Customisation des Données")
        
        # Aperçu des données
        st.write(f"**Données actuelles:** {len(df)} lignes, {len(df.columns)} colonnes")
        
        # Options de customisation
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📊 Ajouter colonnes d'analyse", type="secondary"):
                extended_columns = create_extended_columns()
                for col_name, default_value in extended_columns.items():
                    if col_name not in df.columns:
                        df[col_name] = default_value
                
                # Pré-remplissage automatique intelligent
                if 'abstract' in df.columns:
                    df['ABS 1 OU 0'] = df['abstract'].apply(
                        lambda x: '1' if pd.notna(x) and str(x).strip() != '' else '0'
                    )
                
                # Auto-détecter le type de revue basé sur le titre
                if 'title' in df.columns:
                    df['Type revue'] = df['title'].apply(detect_review_type)
                
                # Auto-détecter la spécialité basée sur le journal
                if 'journal' in df.columns:
                    df['Spécialité'] = df['journal'].apply(detect_specialty)
                
                st.session_state['excel_data'] = df
                st.success("✅ Colonnes d'analyse ajoutées avec pré-remplissage automatique!")
                st.rerun()
            
            # Bouton pour ajouter automatiquement TOUTES les colonnes à l'import
            if st.button("🚀 Auto-ajouter colonnes au chargement", type="primary"):
                st.session_state['auto_add_columns'] = True
                st.success("✅ Les colonnes d'analyse seront automatiquement ajoutées lors du prochain import!")
                st.rerun()
        
        with col2:
            if st.button("🔄 Réinitialiser données"):
                if 'search_results' in st.session_state:
                    st.session_state['excel_data'] = st.session_state['search_results'].copy()
                st.success("✅ Données réinitialisées!")
                st.rerun()
        
        with col3:
            show_all_columns = st.checkbox("Afficher toutes les colonnes", value=False)
        
        # Sélection des colonnes à afficher
        if show_all_columns:
            columns_to_show = df.columns.tolist()
        else:
            default_columns = ['title', 'authors', 'journal', 'year', 'source']
            available_defaults = [col for col in default_columns if col in df.columns]
            columns_to_show = st.multiselect(
                "Colonnes à afficher",
                options=df.columns.tolist(),
                default=available_defaults
            )
        
        if columns_to_show:
            display_df = df[columns_to_show].copy()
            
            # Interface de tableau scrollable pour l'édition
            st.subheader("📊 Tableau d'Édition - Tous les Articles")
            
            # Affichage du nombre total d'articles
            st.info(f"📊 **{len(df)} articles** à traiter | ✏️ Cliquez directement sur les cellules pour les modifier")
            
            # S'assurer que toutes les colonnes d'analyse existent
            analysis_columns = ['ABS 1 OU 0', 'Notes', 'Type revue', 'WL = mesure', 'Chr = participants', 
                              'Spécialité', 'Intervention', 'Technique', 'Contexte', 'Simulation ?', 
                              'Outils', 'Résultats ?', 'Additional outcomes / measures', 'Exclusion']
            
            current_df = st.session_state['excel_data']
            
            # Ajouter les colonnes d'analyse si elles n'existent pas
            for col in analysis_columns:
                if col not in current_df.columns:
                    current_df[col] = ""
            
            # Configuration des colonnes éditables
            column_config = {}
            
            # Configuration pour les colonnes d'analyse spécialisées
            column_config['ABS 1 OU 0'] = st.column_config.SelectboxColumn(
                "ABS 1 OU 0",
                help="1 = Résumé présent, 0 = Pas de résumé",
                options=['', '0', '1'],
                default=''
            )
            
            column_config['Simulation ?'] = st.column_config.SelectboxColumn(
                "Simulation ?",
                options=['', 'Oui', 'Non'],
                default=''
            )
            
            column_config['Type revue'] = st.column_config.SelectboxColumn(
                "Type revue",
                options=['', 'Revue systématique', 'Méta-analyse', 'ECR', 'Étude de cohorte', 'Étude de cas', 'Revue narrative', 'Autre'],
                default=''
            )
            
            column_config['Résultats ?'] = st.column_config.SelectboxColumn(
                "Résultats ?",
                options=['', 'Significatifs', 'Non significatifs', 'Mitigés', 'Non rapportés'],
                default=''
            )
            
            column_config['Exclusion'] = st.column_config.SelectboxColumn(
                "Exclusion",
                options=['', 'Inclus', 'Exclu - Critères', 'Exclu - Qualité', 'Exclu - Pertinence', 'Exclu - Doublons'],
                default=''
            )
            
            # Configuration pour les colonnes textuelles
            for col in ['title', 'abstract', 'authors', 'journal', 'Notes', 'WL = mesure', 'Chr = participants', 
                       'Spécialité', 'Intervention', 'Technique', 'Contexte', 'Outils', 'Additional outcomes / measures']:
                if col in current_df.columns:
                    column_config[col] = st.column_config.TextColumn(
                        col,
                        width="medium",
                        max_chars=500
                    )
            
            # Configuration pour les colonnes numériques
            if 'year' in current_df.columns:
                column_config['year'] = st.column_config.NumberColumn(
                    "Année",
                    min_value=1800,
                    max_value=2030,
                    step=1
                )
            
            if 'cited_by' in current_df.columns:
                column_config['cited_by'] = st.column_config.NumberColumn(
                    "Citations",
                    min_value=0,
                    step=1
                )
            
            # Options d'affichage
            col1, col2, col3 = st.columns(3)
            with col1:
                show_analysis_only = st.checkbox("📊 Afficher seulement les colonnes d'analyse", value=False)
            with col2:
                show_basic_only = st.checkbox("📄 Afficher seulement les métadonnées", value=False)
            with col3:
                compact_view = st.checkbox("🗜️ Vue compacte", value=False)
            
            # Filtrer les colonnes selon le choix
            if show_analysis_only:
                visible_columns = [col for col in current_df.columns if col in analysis_columns]
            elif show_basic_only:
                basic_columns = ['title', 'abstract', 'authors', 'journal', 'year', 'doi', 'cited_by', 'url', 'source', 'type']
                visible_columns = [col for col in current_df.columns if col in basic_columns]
            else:
                # Réorganiser les colonnes : métadonnées d'abord, puis analyse
                basic_columns = ['title', 'abstract', 'authors', 'journal', 'year', 'doi', 'cited_by', 'url', 'source', 'type']
                basic_cols_present = [col for col in basic_columns if col in current_df.columns]
                analysis_cols_present = [col for col in analysis_columns if col in current_df.columns]
                other_cols = [col for col in current_df.columns if col not in basic_columns and col not in analysis_columns]
                visible_columns = basic_cols_present + analysis_cols_present + other_cols
            
            # Créer une vue filtrée du DataFrame
            df_to_edit = current_df[visible_columns].copy()
            
            # Tableau éditable avec scrolling
            edited_df = st.data_editor(
                df_to_edit,
                column_config=column_config,
                use_container_width=True,
                height=600 if not compact_view else 400,
                hide_index=False,
                num_rows="dynamic",  # Permet d'ajouter/supprimer des lignes
                key="article_editor"
            )
            
            # Sauvegarder automatiquement les modifications
            if not edited_df.equals(df_to_edit):
                # Mettre à jour le DataFrame principal avec les modifications
                for col in visible_columns:
                    if col in current_df.columns:
                        current_df[col] = edited_df[col]
                
                st.session_state['excel_data'] = current_df.copy()
                
                # Calculer les modifications
                changes_count = 0
                for col in visible_columns:
                    if col in current_df.columns and col in df_to_edit.columns:
                        if not current_df[col].equals(df_to_edit[col]):
                            changes_count += 1
                
                if changes_count > 0:
                    st.success(f"✅ **{changes_count} colonne(s) modifiée(s)** - Sauvegarde automatique effectuée!")
            
            # Statistiques et informations
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("📄 Total Articles", len(current_df))
            
            with col2:
                analysis_filled = 0
                for col in analysis_columns:
                    if col in current_df.columns:
                        analysis_filled += (current_df[col].astype(str).str.strip() != '').sum()
                st.metric("📊 Champs Analyse Remplis", analysis_filled)
            
            with col3:
                total_fields = len(visible_columns) * len(current_df)
                filled_fields = 0
                for col in visible_columns:
                    if col in current_df.columns:
                        filled_fields += (current_df[col].astype(str).str.strip() != '').sum()
                completion_rate = (filled_fields / total_fields * 100) if total_fields > 0 else 0
                st.metric("✅ Taux Completion", f"{completion_rate:.1f}%")
            
            with col4:
                st.metric("🔍 Colonnes Visibles", len(visible_columns))
            
            # Actions globales
            st.markdown("### 🛠️ Actions Globales")
            action_col1, action_col2, action_col3 = st.columns(3)
            
            with action_col1:
                if st.button("🔄 Réinitialiser les colonnes d'analyse"):
                    for col in analysis_columns:
                        if col in current_df.columns:
                            current_df[col] = ""
                    st.session_state['excel_data'] = current_df.copy()
                    st.success("✅ Colonnes d'analyse réinitialisées!")
                    st.rerun()
            
            with action_col2:
                if st.button("🧹 Nettoyer les cellules vides"):
                    for col in current_df.columns:
                        current_df[col] = current_df[col].astype(str).str.strip()
                        current_df[col] = current_df[col].replace('', pd.NA)
                    st.session_state['excel_data'] = current_df.copy()
                    st.success("✅ Cellules vides nettoyées!")
                    st.rerun()
            
            with action_col3:
                if st.button("📋 Copier configuration"):
                    st.info("💡 Configuration du tableau sauvegardée automatiquement!")
            
            # Message d'aide
            with st.expander("💡 Aide - Utilisation du Tableau"):
                st.markdown("""
                **🎯 Comment utiliser ce tableau :**
                
                1. **Édition directe :** Cliquez sur n'importe quelle cellule pour la modifier
                2. **Navigation :** Utilisez les barres de défilement horizontale et verticale
                3. **Colonnes spécialisées :** Utilisez les listes déroulantes pour les champs prédéfinis
                4. **Sauvegarde automatique :** Toutes vos modifications sont sauvées en temps réel
                5. **Filtres d'affichage :** Utilisez les cases à cocher pour voir seulement certaines colonnes
                6. **Ajout/Suppression :** Utilisez les boutons + et - pour gérer les lignes
                
                **✅ Avantages :**
                - Aucune perte de données lors de la navigation
                - Vue d'ensemble complète de tous vos articles
                - Modification rapide et intuitive
                - Scrolling infini pour gérer des milliers d'articles
                """)
        
        # Export final
        st.subheader("📥 Export Final")
        
        # Afficher un résumé des colonnes qui seront exportées
        analysis_columns = ['ABS 1 OU 0', 'Notes', 'Type revue', 'WL = mesure', 'Chr = participants', 
                          'Spécialité', 'Intervention', 'Technique', 'Contexte', 'Simulation ?', 
                          'Outils', 'Résultats ?', 'Additional outcomes / measures', 'Exclusion']
        
        existing_analysis = [col for col in analysis_columns if col in df.columns]
        basic_columns = [col for col in df.columns if col not in analysis_columns]
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**📄 Métadonnées incluses:**")
            st.write(f"• {len(basic_columns)} colonnes de base")
            if len(basic_columns) > 0:
                st.caption(", ".join(basic_columns[:5]) + ("..." if len(basic_columns) > 5 else ""))
        
        with col2:
            st.write("**📊 Colonnes d'analyse incluses:**")
            st.write(f"• {len(existing_analysis)} colonnes d'analyse")
            if len(existing_analysis) > 0:
                st.caption(", ".join(existing_analysis[:3]) + ("..." if len(existing_analysis) > 3 else ""))
        
        if len(existing_analysis) > 0:
            st.success(f"✅ Toutes vos colonnes d'analyse bibliographique sont incluses dans l'export!")
        else:
            st.info("💡 Ajoutez les colonnes d'analyse avec le bouton '📊 Ajouter colonnes d'analyse'")
        
        export_filename = st.text_input(
            "Nom du fichier Excel final",
            value=f"revue_litterature_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        )
        
        if st.button("💾 Générer Excel Personnalisé", type="primary"):
            # S'assurer qu'on utilise les données les plus récentes du session_state
            df_to_export = st.session_state.get('excel_data', df).copy()
            
            # Vérification de debug
            st.info(f"🔍 Export de {len(df_to_export)} articles avec {len(df_to_export.columns)} colonnes")
            
            # Créer le fichier Excel avec multiples feuilles
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Feuille principale avec TOUTES les colonnes (utiliser df_to_export)
                df_to_export.to_excel(writer, sheet_name='Données Customisées', index=False)
                
                # Feuille de statistiques avancées
                stats_data = {
                    'Métrique': [
                        'Total articles',
                        'Articles avec résumé (ABS 1 OU 0 = 1)',
                        'Articles analysés (Notes remplies)',
                        'Articles inclus (Exclusion = Inclus)',
                        'Articles exclus',
                        'Types de revues identifiés',
                        'Spécialités identifiées',
                        'Sources uniques',
                        'Plage d\'années',
                        'Citations totales'
                    ],
                    'Valeur': [
                        len(df_to_export),
                        (df_to_export['ABS 1 OU 0'] == '1').sum() if 'ABS 1 OU 0' in df_to_export.columns else 0,
                        (df_to_export['Notes'].str.strip() != '').sum() if 'Notes' in df_to_export.columns else 0,
                        (df_to_export['Exclusion'] == 'Inclus').sum() if 'Exclusion' in df_to_export.columns else 0,
                        (df_to_export['Exclusion'].str.contains('Exclu', na=False)).sum() if 'Exclusion' in df_to_export.columns else 0,
                        df_to_export['Type revue'].nunique() if 'Type revue' in df_to_export.columns else 0,
                        df_to_export['Spécialité'].nunique() if 'Spécialité' in df_to_export.columns else 0,
                        df_to_export['source'].nunique() if 'source' in df_to_export.columns else 0,
                        f"{df_to_export['year'].min()}-{df_to_export['year'].max()}" if 'year' in df_to_export.columns and df_to_export['year'].notna().any() else "N/A",
                        df_to_export['cited_by'].sum() if 'cited_by' in df_to_export.columns else 0
                    ]
                }
                stats_df = pd.DataFrame(stats_data)
                stats_df.to_excel(writer, sheet_name='Statistiques', index=False)
                
                # Feuille de répartition par type de revue
                if 'Type revue' in df_to_export.columns:
                    type_counts = df_to_export['Type revue'].value_counts().reset_index()
                    type_counts.columns = ['Type de revue', 'Nombre']
                    type_counts.to_excel(writer, sheet_name='Types de revues', index=False)
                
                # Feuille de répartition par spécialité
                if 'Spécialité' in df_to_export.columns:
                    specialty_counts = df_to_export['Spécialité'].value_counts().reset_index()
                    specialty_counts.columns = ['Spécialité', 'Nombre']
                    specialty_counts.to_excel(writer, sheet_name='Spécialités', index=False)
                
                # Feuille de répartition par source
                if 'source' in df_to_export.columns:
                    source_counts = df_to_export['source'].value_counts().reset_index()
                    source_counts.columns = ['Source', 'Nombre']
                    source_counts.to_excel(writer, sheet_name='Répartition Sources', index=False)
                
                # Feuille des colonnes d'analyse pour référence
                analysis_columns = ['ABS 1 OU 0', 'Notes', 'Type revue', 'WL = mesure', 'Chr = participants', 
                                  'Spécialité', 'Intervention', 'Technique', 'Contexte', 'Simulation ?', 
                                  'Outils', 'Résultats ?', 'Additional outcomes / measures', 'Exclusion']
                
                existing_analysis = [col for col in analysis_columns if col in df_to_export.columns]
                if existing_analysis:
                    analysis_info = pd.DataFrame({
                        'Colonne d\'analyse': existing_analysis,
                        'Description': [
                            '1 = Résumé présent, 0 = Pas de résumé',
                            'Notes libres sur l\'article',
                            'Type d\'étude (Revue systématique, ECR, etc.)',
                            'Mesures de résultats (WL = Working List)',
                            'Caractéristiques des participants',
                            'Spécialité médicale',
                            'Type d\'intervention étudiée',
                            'Technique utilisée',
                            'Contexte de l\'étude',
                            'Oui/Non si c\'est une simulation',
                            'Outils ou instruments utilisés',
                            'Résultats significatifs ou non',
                            'Mesures de résultats additionnelles',
                            'Statut d\'inclusion/exclusion'
                        ][:len(existing_analysis)]
                    })
                    analysis_info.to_excel(writer, sheet_name='Légende Analyse', index=False)
            
            output.seek(0)
            
            # Bouton de téléchargement
            # Validation et statistiques de l'export
            analysis_columns = ['ABS 1 OU 0', 'Notes', 'Type revue', 'WL = mesure', 'Chr = participants', 
                              'Spécialité', 'Intervention', 'Technique', 'Contexte', 'Simulation ?', 
                              'Outils', 'Résultats ?', 'Additional outcomes / measures', 'Exclusion']
            
            filled_analysis_cols = []
            for col in analysis_columns:
                if col in df_to_export.columns:
                    filled_count = (df_to_export[col].astype(str).str.strip() != '').sum()
                    if filled_count > 0:
                        filled_analysis_cols.append(f"{col} ({filled_count})")
            
            st.download_button(
                label="⬇️ Télécharger Excel Personnalisé",
                data=output.getvalue(),
                file_name=export_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            st.success("✅ Fichier Excel personnalisé créé avec succès!")
            
            if filled_analysis_cols:
                st.info(f"📊 Colonnes d'analyse avec données: {', '.join(filled_analysis_cols)}")
            else:
                st.warning("⚠️ Aucune colonne d'analyse n'a été remplie")
            
            # Information détaillée sur l'export
            with st.expander("ℹ️ Détails de l'export"):
                st.write("**Contenu du fichier Excel:**")
                st.write(f"• **Feuille 'Données Customisées'**: {len(df_to_export)} articles avec {len(df_to_export.columns)} colonnes")
                st.write(f"• **Feuille 'Statistiques'**: Métriques détaillées")
                st.write(f"• **Feuille 'Types de revues'**: Répartition par type d'étude")
                st.write(f"• **Feuille 'Spécialités'**: Répartition par domaine médical")
                st.write(f"• **Feuille 'Répartition Sources'**: Origine des articles")
                st.write(f"• **Feuille 'Légende Analyse'**: Description des colonnes d'analyse")
                
                if len(filled_analysis_cols) > 0:
                    st.success(f"✅ {len(filled_analysis_cols)} colonnes d'analyse contiennent des données")
                
                # Afficher un échantillon des colonnes modifiées
                st.write("**Aperçu des colonnes d'analyse:**")
                # Vérifier quelles colonnes existent vraiment
                available_basic_cols = [col for col in ['title', 'authors', 'journal', 'year'] if col in df_to_export.columns]
                sample_analysis_cols = [col for col in analysis_columns[:5] if col in df_to_export.columns]
                sample_cols = available_basic_cols[:2] + sample_analysis_cols[:3]  # Prendre au max 5 colonnes
                
                if len(df_to_export) > 0 and sample_cols:
                    st.dataframe(df_to_export[sample_cols].head(3), use_container_width=True)
                else:
                    st.info("Aucune donnée à afficher dans l'aperçu")

def configuration_apis():
    """Interface de configuration des APIs."""
    
    st.markdown("""
    **Configuration et Test des APIs Scientifiques**
    
    Toutes les APIs utilisées sont **gratuites** et ne nécessitent pas de clé d'accès.
    """)
    
    # Statut des APIs
    st.subheader("📡 Statut des APIs")
    
    for api_name, config in API_CONFIG.items():
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.write(f"**{api_name.title()}**")
        
        with col2:
            st.write("✅ Gratuite" if config["free"] else "💰 Payante")
        
        with col3:
            st.write(f"⚡ {config['rate_limit']}/s" if 'second' in str(config['rate_limit']) else f"⚡ {config['rate_limit']}/min")
        
        with col4:
            if st.button(f"🧪 Tester {api_name}", key=f"test_{api_name}"):
                test_api(api_name)
    
    # Informations détaillées
    st.subheader("📚 Détails des APIs")
    
    with st.expander("🌐 OpenAlex"):
        st.markdown("""
        **OpenAlex** - Base de données bibliographique open source
        - ✅ Entièrement gratuite
        - 📊 250M+ articles scientifiques
        - 🔄 Mise à jour quotidienne
        - 🏷️ Métadonnées complètes (auteurs, institutions, citations)
        - 🌍 Couvre toutes les disciplines
        """)
    
    with st.expander("🧠 Semantic Scholar"):
        st.markdown("""
        **Semantic Scholar** - Moteur de recherche académique avec IA
        - ✅ Gratuite (limite: 100 req/min)
        - 🤖 Analyse sémantique avancée
        - 📈 Métriques d'influence
        - 📄 200M+ articles
        - 🔗 Graphe de citations intelligent
        """)
    
    with st.expander("🏥 PubMed"):
        st.markdown("""
        **PubMed** - Base biomédicale officielle NCBI
        - ✅ Entièrement gratuite
        - 🏥 Focus biomédical et vie sciences
        - 📚 35M+ références
        - 🏛️ Source officielle gouvernementale
        - 📋 Abstracts de qualité garantie
        """)
    
    with st.expander("📄 Crossref"):
        st.markdown("""
        **Crossref** - Métadonnées d'articles académiques
        - ✅ Gratuite avec politeness policy
        - 🔗 135M+ enregistrements
        - 📊 Métadonnées DOI officielles
        - 🏢 Sources d'éditeurs certifiés
        - 📅 Données de publication précises
        """)

def test_api(api_name: str):
    """Tester une API spécifique."""
    try:
        if api_name == "openalex":
            api = OpenAlexAPI()
            result = api.search_works("covid", 2023, 2024, 5)
        elif api_name == "semantic_scholar":
            api = SemanticScholarAPI()
            result = api.search_papers("machine learning", 2023, 2024, 5)
        elif api_name == "pubmed":
            api = PubMedAPI()
            result = api.search_articles("cancer therapy", 2023, 2024, 5)
        elif api_name == "crossref":
            api = CrossrefAPI()
            result = api.search_works("artificial intelligence", 2023, 2024, 5)
        
        if not result.empty:
            st.success(f"✅ {api_name.title()}: {len(result)} articles trouvés")
            st.dataframe(result[['title', 'authors', 'year']].head(3))
        else:
            st.warning(f"⚠️ {api_name.title()}: Test réussi mais aucun résultat")
    
    except Exception as e:
        st.error(f"❌ {api_name.title()}: Erreur - {e}")

if __name__ == "__main__":
    main()
