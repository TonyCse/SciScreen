"""Application Streamlit pour la recherche bibliographique automatisée.

Cette application permet de :
1. Rechercher sur PubMed, Scopus et autres bases
2. Extraire automatiquement les métadonnées
3. Exporter les résultats en Excel
"""

import sys
from pathlib import Path
import pandas as pd
import streamlit as st
from datetime import datetime
import time

# Ajouter le répertoire src au chemin Python
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

try:
    # Import avec gestion d'erreur pour les modules optionnels
    pubmed = None
    openalex = None 
    crossref = None
    scopus = None
    
    try:
        from harvest import pubmed, openalex, crossref
    except ImportError:
        pass
    
    try:
        from harvest.scopus import search_scopus as scopus
    except ImportError:
        pass
    
    try:
        from utils_io import save_dataframe, merge_dataframes
    except ImportError:
        # Fallback functions
        def save_dataframe(df, filepath):
            df.to_excel(filepath, index=False)
        
        def merge_dataframes(dataframes, source_names=None):
            if not dataframes:
                return pd.DataFrame()
            result = pd.concat(dataframes, ignore_index=True)
            if source_names and len(source_names) == len(dataframes):
                # Add source column if provided
                for i, source in enumerate(source_names):
                    mask = result.index.isin(dataframes[i].index)
                    result.loc[mask, 'source'] = source
            return result

except Exception as e:
    st.error(f"Erreur d'import: {e}")
    st.info("Utilisation du mode démonstration uniquement.")

def create_demo_data():
    """Créer des données de démonstration."""
    return pd.DataFrame([
        {
            "source": "demo",
            "title": "Cognitive Behavioral Therapy for Depression in Adults",
            "abstract": "This systematic review examines the effectiveness of CBT for treating depression in adult populations.",
            "authors": "Smith, J.A.; Johnson, M.K.",
            "journal": "Journal of Clinical Psychology",
            "year": 2023,
            "doi": "10.1000/demo1",
            "cited_by": 45
        },
        {
            "source": "demo", 
            "title": "Machine Learning Applications in Mental Health",
            "abstract": "Recent advances in ML have opened new possibilities for mental health screening and diagnosis.",
            "authors": "Davis, R.M.; Wilson, K.J.",
            "journal": "AI in Medicine",
            "year": 2022,
            "doi": "10.1000/demo2",
            "cited_by": 23
        }
    ])

def search_pubmed_safe(query, year_from, year_to, max_results):
    """Recherche PubMed avec gestion d'erreur."""
    if pubmed is None:
        st.warning("Module PubMed non disponible")
        return pd.DataFrame()
    try:
        return pubmed.search_and_fetch(query, year_from, year_to, max_results)
    except Exception as e:
        st.error(f"Erreur PubMed: {e}")
        return pd.DataFrame()

def search_openalex_safe(query, year_from, year_to, max_results):
    """Recherche OpenAlex avec gestion d'erreur."""
    if openalex is None:
        st.warning("Module OpenAlex non disponible")
        return pd.DataFrame()
    try:
        return openalex.get_works(query, year_from, year_to, max_results)
    except Exception as e:
        st.error(f"Erreur OpenAlex: {e}")
        return pd.DataFrame()

def search_crossref_safe(query, year_from, year_to, max_results):
    """Recherche Crossref avec gestion d'erreur."""
    if crossref is None:
        st.warning("Module Crossref non disponible")
        return pd.DataFrame()
    try:
        return crossref.search_works(query, year_from, year_to, max_results)
    except Exception as e:
        st.error(f"Erreur Crossref: {e}")
        return pd.DataFrame()

def search_scopus_safe(query, year_from, year_to, max_results, api_key):
    """Recherche Scopus avec gestion d'erreur."""
    if scopus is None:
        st.warning("Module Scopus non disponible")
        return pd.DataFrame()
    try:
        return scopus(query, year_from, year_to, max_results, api_key)
    except Exception as e:
        st.error(f"Erreur Scopus: {e}")
        return pd.DataFrame()

def format_dataframe_for_display(df):
    """Formater le DataFrame pour l'affichage."""
    if df.empty:
        return df
    
    # Sélectionner et réorganiser les colonnes pour l'affichage
    display_columns = [
        'title', 'authors', 'journal', 'year', 'source', 'doi', 'cited_by'
    ]
    
    # Ne garder que les colonnes qui existent
    available_columns = [col for col in display_columns if col in df.columns]
    display_df = df[available_columns].copy()
    
    # Tronquer les titres longs pour l'affichage
    if 'title' in display_df.columns:
        display_df['title'] = display_df['title'].apply(
            lambda x: x[:100] + "..." if len(str(x)) > 100 else x
        )
    
    # Tronquer les auteurs longs
    if 'authors' in display_df.columns:
        display_df['authors'] = display_df['authors'].apply(
            lambda x: x[:50] + "..." if len(str(x)) > 50 else x
        )
    
    return display_df

def export_to_excel(df, filename):
    """Exporter DataFrame vers Excel avec formatage."""
    try:
        # Créer le répertoire de sortie
        output_dir = Path("data/outputs")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Chemin complet du fichier
        filepath = output_dir / filename
        
        # Exporter vers Excel avec formatage
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Feuille principale avec tous les résultats
            df.to_excel(writer, sheet_name='Résultats', index=False)
            
            # Feuille de statistiques
            if not df.empty:
                stats_data = {
                    'Métrique': [
                        'Total articles',
                        'Sources uniques', 
                        'Années couvertes',
                        'Articles avec DOI',
                        'Articles avec résumé',
                        'Citations totales'
                    ],
                    'Valeur': [
                        len(df),
                        df['source'].nunique() if 'source' in df.columns else 0,
                        f"{df['year'].min()}-{df['year'].max()}" if 'year' in df.columns else "N/A",
                        (df['doi'] != "").sum() if 'doi' in df.columns else 0,
                        (df['abstract'] != "").sum() if 'abstract' in df.columns else 0,
                        df['cited_by'].sum() if 'cited_by' in df.columns else 0
                    ]
                }
                stats_df = pd.DataFrame(stats_data)
                stats_df.to_excel(writer, sheet_name='Statistiques', index=False)
        
        return filepath
    except Exception as e:
        st.error(f"Erreur lors de l'export Excel: {e}")
        return None

def main():
    """Application principale."""
    st.set_page_config(
        page_title="Recherche Bibliographique",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 Recherche Bibliographique Automatisée")
    st.markdown("Recherchez et extrayez automatiquement des articles depuis PubMed, Scopus et autres bases de données")
    
    # Sidebar pour configuration
    st.sidebar.title("⚙️ Configuration")
    
    # Paramètres de recherche
    st.sidebar.subheader("Recherche")
    query = st.sidebar.text_area(
        "Requête de recherche",
        value="cognitive behavioral therapy depression",
        help="Utilisez des mots-clés en anglais, connecteurs AND/OR autorisés"
    )
    
    # Années
    col1, col2 = st.sidebar.columns(2)
    with col1:
        year_from = st.number_input("Année début", 2000, 2024, 2020)
    with col2:
        year_to = st.number_input("Année fin", 2000, 2024, 2024)
    
    # Nombre maximum de résultats
    max_results = st.sidebar.number_input(
        "Max résultats par source", 
        10, 1000, 100,
        help="Limite le nombre d'articles récupérés par base de données"
    )
    
    # Sélection des sources
    st.sidebar.subheader("Sources de données")
    
    # Vérifier la disponibilité des modules
    pubmed_available = pubmed is not None
    openalex_available = openalex is not None
    crossref_available = crossref is not None
    scopus_available = scopus is not None
    
    use_pubmed = st.sidebar.checkbox(
        f"📚 PubMed (gratuit)" + ("" if pubmed_available else " - ⚠️ Module non disponible"), 
        value=pubmed_available,
        disabled=not pubmed_available
    )
    use_openalex = st.sidebar.checkbox(
        f"🌐 OpenAlex (gratuit)" + ("" if openalex_available else " - ⚠️ Module non disponible"), 
        value=openalex_available,
        disabled=not openalex_available
    )
    use_crossref = st.sidebar.checkbox(
        f"📖 Crossref (gratuit)" + ("" if crossref_available else " - ⚠️ Module non disponible"), 
        value=False,
        disabled=not crossref_available
    )
    
    use_scopus = st.sidebar.checkbox(
        f"🔬 Scopus (nécessite clé API)" + ("" if scopus_available else " - ⚠️ Module non disponible"), 
        value=False,
        disabled=not scopus_available
    )
    scopus_api_key = ""
    if use_scopus and scopus_available:
        scopus_api_key = st.sidebar.text_input(
            "Clé API Scopus",
            type="password",
            help="Obtenez votre clé sur dev.elsevier.com"
        )
    
    # Afficher un avertissement si aucun module n'est disponible
    available_sources = sum([pubmed_available, openalex_available, crossref_available, scopus_available])
    if available_sources == 0:
        st.sidebar.error("⚠️ Aucun module de recherche disponible. Mode démonstration uniquement.")
    
    # Configuration export
    st.sidebar.subheader("📥 Export")
    export_filename = st.sidebar.text_input(
        "Nom du fichier Excel",
        value=f"recherche_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    )
    
    # Bouton de recherche principal
    if st.sidebar.button("🚀 Lancer la recherche", type="primary"):
        if not query.strip():
            st.error("Veuillez saisir une requête de recherche")
            return
        
        # Affichage des paramètres
        st.subheader("📋 Paramètres de recherche")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"**Requête:** {query}")
        with col2:
            st.info(f"**Période:** {year_from}-{year_to}")
        with col3:
            st.info(f"**Max/source:** {max_results}")
        
        # Initialiser les résultats
        all_dataframes = []
        source_names = []
        
        # Progress bar
        sources_to_search = []
        if use_pubmed: sources_to_search.append("PubMed")
        if use_openalex: sources_to_search.append("OpenAlex") 
        if use_crossref: sources_to_search.append("Crossref")
        if use_scopus and scopus_api_key: sources_to_search.append("Scopus")
        
        if not sources_to_search:
            st.warning("Veuillez sélectionner au moins une source de données")
            return
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Recherche PubMed
        if use_pubmed:
            status_text.text("🔍 Recherche sur PubMed...")
            progress_bar.progress(0.1)
            
            pubmed_df = search_pubmed_safe(query, year_from, year_to, max_results)
            if not pubmed_df.empty:
                all_dataframes.append(pubmed_df)
                source_names.append("pubmed")
                st.success(f"✅ PubMed: {len(pubmed_df)} articles trouvés")
            else:
                st.warning("⚠️ PubMed: Aucun résultat")
        
        # Recherche OpenAlex
        if use_openalex:
            status_text.text("🔍 Recherche sur OpenAlex...")
            progress_bar.progress(0.3)
            
            openalex_df = search_openalex_safe(query, year_from, year_to, max_results)
            if not openalex_df.empty:
                all_dataframes.append(openalex_df)
                source_names.append("openalex")
                st.success(f"✅ OpenAlex: {len(openalex_df)} articles trouvés")
            else:
                st.warning("⚠️ OpenAlex: Aucun résultat")
        
        # Recherche Crossref
        if use_crossref:
            status_text.text("🔍 Recherche sur Crossref...")
            progress_bar.progress(0.5)
            
            crossref_df = search_crossref_safe(query, year_from, year_to, max_results)
            if not crossref_df.empty:
                all_dataframes.append(crossref_df)
                source_names.append("crossref")
                st.success(f"✅ Crossref: {len(crossref_df)} articles trouvés")
            else:
                st.warning("⚠️ Crossref: Aucun résultat")
        
        # Recherche Scopus
        if use_scopus and scopus_api_key:
            status_text.text("🔍 Recherche sur Scopus...")
            progress_bar.progress(0.7)
            
            scopus_df = search_scopus_safe(query, year_from, year_to, max_results, scopus_api_key)
            if not scopus_df.empty:
                all_dataframes.append(scopus_df)
                source_names.append("scopus")
                st.success(f"✅ Scopus: {len(scopus_df)} articles trouvés")
            else:
                st.warning("⚠️ Scopus: Aucun résultat")
        
        # Fusion des résultats
        if all_dataframes:
            status_text.text("🔄 Fusion des résultats...")
            progress_bar.progress(0.9)
            
            try:
                combined_df = merge_dataframes(all_dataframes, source_names)
                st.session_state['results_df'] = combined_df
                
                progress_bar.progress(1.0)
                status_text.text("✅ Recherche terminée!")
                
                st.success(f"🎉 **Total: {len(combined_df)} articles trouvés**")
                
            except Exception as e:
                st.error(f"Erreur lors de la fusion: {e}")
                # Utiliser les données de démonstration en cas d'erreur
                st.session_state['results_df'] = create_demo_data()
        else:
            st.error("Aucun résultat trouvé dans aucune source")
            # Utiliser les données de démonstration
            st.session_state['results_df'] = create_demo_data()
            st.info("Affichage de données de démonstration")
    
    # Mode démonstration si pas de recherche
    elif 'results_df' not in st.session_state:
        st.info("👆 Configurez votre recherche dans la barre latérale et cliquez sur 'Lancer la recherche'")
        st.subheader("📊 Exemple de résultats")
        st.session_state['results_df'] = create_demo_data()
    
    # Affichage des résultats
    if 'results_df' in st.session_state and not st.session_state['results_df'].empty:
        df = st.session_state['results_df']
        
        st.subheader(f"📊 Résultats ({len(df)} articles)")
        
        # Statistiques rapides
        if len(df) > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total articles", len(df))
            with col2:
                sources_count = df['source'].nunique() if 'source' in df.columns else 0
                st.metric("Sources", sources_count)
            with col3:
                if 'year' in df.columns:
                    year_span = f"{df['year'].min()}-{df['year'].max()}"
                    st.metric("Années", year_span)
            with col4:
                if 'cited_by' in df.columns:
                    total_citations = df['cited_by'].sum()
                    st.metric("Citations", total_citations)
        
        # Filtres pour l'affichage
        st.subheader("🔍 Filtres d'affichage")
        
        filter_col1, filter_col2 = st.columns(2)
        
        with filter_col1:
            # Filtre par source
            if 'source' in df.columns:
                sources = ['Toutes'] + list(df['source'].unique())
                selected_source = st.selectbox("Source", sources)
                
                if selected_source != 'Toutes':
                    df = df[df['source'] == selected_source]
        
        with filter_col2:
            # Filtre par année
            if 'year' in df.columns and df['year'].notna().any():
                years = sorted(df['year'].dropna().unique())
                if len(years) > 1:
                    year_range = st.select_slider(
                        "Plage d'années",
                        options=years,
                        value=(min(years), max(years))
                    )
                    df = df[(df['year'] >= year_range[0]) & (df['year'] <= year_range[1])]
        
        # Tableau des résultats
        st.subheader("📋 Liste des articles")
        
        # Formater pour l'affichage
        display_df = format_dataframe_for_display(df)
        
        # Affichage avec sélection
        if not display_df.empty:
            selected_indices = st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                height=400
            )
        
        # Détails d'un article sélectionné
        if not df.empty:
            st.subheader("📖 Détails de l'article")
            article_idx = st.number_input(
                "Numéro d'article à afficher",
                min_value=1,
                max_value=len(df),
                value=1
            ) - 1
            
            if 0 <= article_idx < len(df):
                article = df.iloc[article_idx]
                
                # Affichage des détails
                st.markdown(f"**Titre:** {article.get('title', 'N/A')}")
                st.markdown(f"**Auteurs:** {article.get('authors', 'N/A')}")
                st.markdown(f"**Journal:** {article.get('journal', 'N/A')}")
                st.markdown(f"**Année:** {article.get('year', 'N/A')}")
                st.markdown(f"**Source:** {article.get('source', 'N/A')}")
                
                if article.get('doi'):
                    st.markdown(f"**DOI:** [https://doi.org/{article['doi']}](https://doi.org/{article['doi']})")
                
                if article.get('abstract'):
                    with st.expander("Résumé complet"):
                        st.write(article['abstract'])
        
        # Export Excel
        st.subheader("📥 Export Excel")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write(f"Prêt à exporter {len(df)} articles vers Excel")
        
        with col2:
            if st.button("📊 Exporter vers Excel", type="primary"):
                filepath = export_to_excel(df, export_filename)
                if filepath:
                    st.success(f"✅ Export réussi: {filepath}")
                    
                    # Bouton de téléchargement
                    try:
                        with open(filepath, "rb") as file:
                            st.download_button(
                                label="⬇️ Télécharger Excel",
                                data=file.read(),
                                file_name=export_filename,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                    except Exception as e:
                        st.error(f"Erreur téléchargement: {e}")

if __name__ == "__main__":
    main()
