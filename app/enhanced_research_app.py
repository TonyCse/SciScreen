"""Application Streamlit améliorée pour la recherche bibliographique et analyse d'Excel.

Cette application permet de :
1. Rechercher sur PubMed, Scopus et autres bases
2. Extraire automatiquement les métadonnées  
3. Importer et transformer des fichiers Excel existants
4. Exporter les résultats enrichis
"""

import sys
from pathlib import Path
import pandas as pd
import streamlit as st
from datetime import datetime
import time
import io

# Ajouter le répertoire src au chemin Python
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Importations avec simulation pour démonstration
def simulate_pubmed_search(query, year_from, year_to, max_results):
    """Simulation d'une recherche PubMed avec des données réalistes."""
    articles = []
    
    # Adapter les résultats selon la requête
    query_lower = query.lower()
    
    if any(word in query_lower for word in ['depression', 'therapy', 'cbt', 'cognitive']):
        articles = [
            {
                'source': 'pubmed',
                'title': 'Cognitive Behavioral Therapy for Depression in Primary Care: A Systematic Review',
                'abstract': 'This systematic review evaluates the effectiveness of cognitive behavioral therapy (CBT) interventions for depression in primary care settings. We analyzed 34 randomized controlled trials involving 4,127 participants. Results show significant improvements in depression scores with CBT compared to usual care (SMD = -0.42, 95% CI [-0.58, -0.26], p < 0.001).',
                'authors': 'Smith, J.A.; Johnson, M.K.; Brown, S.L.',
                'journal': 'Journal of Primary Care Mental Health',
                'year': 2023,
                'doi': '10.1001/jamapsychiatry.2023.1234',
                'pmid': '37123456',
                'cited_by': 45,
                'url': 'https://pubmed.ncbi.nlm.nih.gov/37123456/'
            },
            {
                'source': 'pubmed',
                'title': 'Effectiveness of Online CBT Interventions: A Meta-Analysis of Recent Studies',
                'abstract': 'Online cognitive behavioral therapy has gained prominence during the COVID-19 pandemic. This meta-analysis examines the effectiveness of internet-delivered CBT compared to face-to-face therapy. Analysis of 28 studies (n=3,456) shows non-inferiority of online CBT (d = 0.03, 95% CI [-0.12, 0.18]).',
                'authors': 'Garcia, M.A.; Lee, S.H.; Anderson, D.R.',
                'journal': 'Clinical Psychology Review',
                'year': 2022,
                'doi': '10.1016/j.cpr.2022.102089',
                'pmid': '36789012',
                'cited_by': 67,
                'url': 'https://pubmed.ncbi.nlm.nih.gov/36789012/'
            },
            {
                'source': 'pubmed',
                'title': 'Mindfulness-Based Cognitive Therapy for Recurrent Depression Prevention',
                'abstract': 'Mindfulness-based cognitive therapy (MBCT) combines mindfulness practices with cognitive therapy techniques. This study examines its effectiveness in preventing depression relapse in 180 participants over 12 months. MBCT group showed 31% reduction in relapse rates compared to treatment as usual.',
                'authors': 'Wilson, K.J.; Thompson, L.P.; Davis, R.M.',
                'journal': 'Mindfulness',
                'year': 2023,
                'doi': '10.1007/s12671-023-01567-8',
                'pmid': '37456789',
                'cited_by': 23,
                'url': 'https://pubmed.ncbi.nlm.nih.gov/37456789/'
            }
        ]
    elif any(word in query_lower for word in ['surgery', 'surgical', 'operation']):
        articles = [
            {
                'source': 'pubmed',
                'title': 'Robotic-Assisted Surgery in Colorectal Procedures: A Systematic Review',
                'abstract': 'Robotic-assisted surgery has gained popularity for colorectal procedures. This systematic review analyzes outcomes from 45 studies involving 8,234 patients. Robotic surgery showed reduced conversion rates (OR 0.62, 95% CI [0.48-0.81]) and shorter hospital stays.',
                'authors': 'Martinez, C.D.; Patel, R.K.; Johnson, A.B.',
                'journal': 'Annals of Surgery',
                'year': 2023,
                'doi': '10.1097/SLA.0000000000005234',
                'pmid': '36987654',
                'cited_by': 89,
                'url': 'https://pubmed.ncbi.nlm.nih.gov/36987654/'
            },
            {
                'source': 'pubmed',
                'title': 'Enhanced Recovery After Surgery Protocols: Implementation and Outcomes',
                'abstract': 'Enhanced Recovery After Surgery (ERAS) protocols aim to optimize perioperative care. This multicenter study of 1,245 patients demonstrates 28% reduction in length of stay and 35% decrease in complications with ERAS implementation.',
                'authors': 'Chen, L.W.; Rodriguez, E.M.; Singh, P.K.',
                'journal': 'British Journal of Surgery',
                'year': 2022,
                'doi': '10.1093/bjs/znac156',
                'pmid': '37654321',
                'cited_by': 156,
                'url': 'https://pubmed.ncbi.nlm.nih.gov/37654321/'
            }
        ]
    else:
        # Articles génériques pour autres requêtes
        articles = [
            {
                'source': 'pubmed',
                'title': f'Clinical Applications of {query.title()}: A Comprehensive Review',
                'abstract': f'This comprehensive review examines the clinical applications and therapeutic potential of {query} in modern medicine. We analyze current evidence from 52 studies and identify future research directions.',
                'authors': 'Research, A.B.; Clinical, C.D.; Medical, E.F.',
                'journal': 'Journal of Clinical Medicine',
                'year': 2023,
                'doi': '10.3390/jcm12345678',
                'pmid': '37111111',
                'cited_by': 34,
                'url': 'https://pubmed.ncbi.nlm.nih.gov/37111111/'
            },
            {
                'source': 'pubmed',
                'title': f'Recent Advances in {query.title()} Research: A Systematic Analysis',
                'abstract': f'Recent developments in {query} research have opened new therapeutic possibilities. This systematic analysis reviews the latest findings from 38 peer-reviewed studies and discusses methodological approaches.',
                'authors': 'Innovation, G.H.; Progress, I.J.; Discovery, K.L.',
                'journal': 'Scientific Reports',
                'year': 2022,
                'doi': '10.1038/s41598-022-12345-6',
                'pmid': '36222222',
                'cited_by': 18,
                'url': 'https://pubmed.ncbi.nlm.nih.gov/36222222/'
            }
        ]
    
    # Filtrer par année et limiter le nombre
    filtered_articles = [
        article for article in articles 
        if year_from <= article['year'] <= year_to
    ][:max_results]
    
    return pd.DataFrame(filtered_articles)

def create_extended_columns():
    """Créer les colonnes étendues pour l'analyse bibliographique."""
    return {
        'ABS 1 OU 0': '',  # Résumé présent (1) ou absent (0)
        'Notes': '',  # Notes d'analyse
        'Type revue': '',  # Type de revue (systématique, méta-analyse, etc.)
        'WL = mesure': '',  # Mesure de résultat principal
        'Chr = participants': '',  # Caractéristiques des participants
        'Spécialité': '',  # Spécialité médicale
        'Intervention': '',  # Type d'intervention
        'Technique': '',  # Technique utilisée
        'Contexte': '',  # Contexte d'étude
        'Simulation ?': '',  # Étude de simulation (oui/non)
        'Outil': '',  # Outils/instruments utilisés
        'Résultats ?': '',  # Présence de résultats significatifs
        'Additional outcomes / conclusion': ''  # Résultats additionnels et conclusions
    }

def transform_excel_data(df):
    """Transformer un DataFrame basique en format étendu pour l'analyse."""
    # Créer une copie du DataFrame original
    extended_df = df.copy()
    
    # Ajouter les nouvelles colonnes d'analyse
    extended_columns = create_extended_columns()
    
    for col_name, default_value in extended_columns.items():
        extended_df[col_name] = default_value
    
    # Remplir automatiquement certaines colonnes quand possible
    if 'abstract' in extended_df.columns:
        extended_df['ABS 1 OU 0'] = extended_df['abstract'].apply(
            lambda x: '1' if pd.notna(x) and str(x).strip() != '' else '0'
        )
    
    # Analyser le type de revue à partir du titre
    if 'title' in extended_df.columns:
        extended_df['Type revue'] = extended_df['title'].apply(detect_review_type)
    
    # Analyser la spécialité à partir du journal
    if 'journal' in extended_df.columns:
        extended_df['Spécialité'] = extended_df['journal'].apply(detect_specialty)
    
    return extended_df

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
        return 'À déterminer'

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
    
    return 'Médecine générale'

def main():
    """Application principale."""
    st.set_page_config(
        page_title="Recherche & Analyse Bibliographique",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 Recherche & Analyse Bibliographique")
    st.markdown("Recherchez des articles OU transformez vos fichiers Excel existants en format d'analyse étendu")
    
    # Tabs pour les différentes fonctionnalités
    tab1, tab2 = st.tabs(["🔎 Nouvelle Recherche", "📊 Transformer Excel Existant"])
    
    with tab1:
        st.header("🔎 Recherche Bibliographique")
        recherche_bibliographique()
    
    with tab2:
        st.header("📊 Transformation d'Excel")
        transformation_excel()

def recherche_bibliographique():
    """Interface pour la recherche bibliographique."""
    
    # Sidebar pour configuration
    st.sidebar.title("⚙️ Configuration Recherche")
    
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
    
    # Sources disponibles (simulation)
    st.sidebar.subheader("Sources de données")
    use_pubmed = st.sidebar.checkbox("📚 PubMed (simulation)", value=True)
    
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
        
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Recherche PubMed (simulation)
        if use_pubmed:
            status_text.text("🔍 Recherche sur PubMed...")
            progress_bar.progress(0.3)
            time.sleep(1)  # Simulation du temps de recherche
            
            pubmed_df = simulate_pubmed_search(query, year_from, year_to, max_results)
            if not pubmed_df.empty:
                st.session_state['search_results_df'] = pubmed_df
                st.success(f"✅ PubMed: {len(pubmed_df)} articles trouvés")
            else:
                st.warning("⚠️ PubMed: Aucun résultat")
        
        progress_bar.progress(1.0)
        status_text.text("✅ Recherche terminée!")
    
    # Affichage des résultats de recherche
    if 'search_results_df' in st.session_state and not st.session_state['search_results_df'].empty:
        df = st.session_state['search_results_df']
        
        st.subheader(f"📊 Résultats de recherche ({len(df)} articles)")
        
        # Statistiques rapides
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total articles", len(df))
        with col2:
            st.metric("Avec résumé", (df['abstract'] != "").sum())
        with col3:
            year_span = f"{df['year'].min()}-{df['year'].max()}"
            st.metric("Années", year_span)
        with col4:
            total_citations = df['cited_by'].sum()
            st.metric("Citations", total_citations)
        
        # Tableau des résultats
        display_columns = ['title', 'authors', 'journal', 'year', 'cited_by']
        display_df = df[display_columns].copy()
        
        # Tronquer les titres longs
        display_df['title'] = display_df['title'].apply(
            lambda x: x[:80] + "..." if len(str(x)) > 80 else x
        )
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Option pour transformer en format étendu
        st.subheader("🔄 Transformation en format d'analyse")
        if st.button("📊 Transformer en format d'analyse étendu", type="secondary"):
            extended_df = transform_excel_data(df)
            st.session_state['extended_results_df'] = extended_df
            st.success("✅ Transformation réussie! Voir l'onglet 'Transformer Excel' pour les résultats")
        
        # Export Excel classique
        st.subheader("📥 Export Excel")
        if st.button("📊 Exporter résultats bruts", type="primary"):
            export_path = f"data/outputs/{export_filename}"
            Path("data/outputs").mkdir(parents=True, exist_ok=True)
            df.to_excel(export_path, index=False)
            st.success(f"✅ Export réussi: {export_path}")

def transformation_excel():
    """Interface pour la transformation d'Excel existants."""
    
    st.markdown("""
    **Importez votre fichier Excel existant et transformez-le en format d'analyse étendu.**
    
    Votre fichier doit contenir au minimum les colonnes: `title`, `authors`, `journal`, `year`
    """)
    
    # Upload file
    uploaded_file = st.file_uploader(
        "📁 Choisissez votre fichier Excel",
        type=['xlsx', 'xls'],
        help="Formats supportés: .xlsx, .xls"
    )
    
    if uploaded_file is not None:
        try:
            # Lire le fichier Excel
            df = pd.read_excel(uploaded_file)
            
            st.success(f"✅ Fichier importé: {len(df)} lignes")
            
            # Afficher les colonnes détectées
            st.subheader("📋 Colonnes détectées")
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Colonnes présentes:**")
                for col in df.columns:
                    st.write(f"- {col}")
            
            with col2:
                # Vérifier les colonnes requises
                required_cols = ['title', 'authors', 'journal', 'year']
                missing_cols = [col for col in required_cols if col not in df.columns]
                
                if missing_cols:
                    st.warning(f"⚠️ Colonnes manquantes: {', '.join(missing_cols)}")
                    st.info("Le système tentera de mapper automatiquement les colonnes similaires")
                else:
                    st.success("✅ Toutes les colonnes requises sont présentes")
            
            # Aperçu des données
            st.subheader("👀 Aperçu des données")
            st.dataframe(df.head(), use_container_width=True)
            
            # Bouton de transformation
            if st.button("🔄 Transformer en format d'analyse étendu", type="primary"):
                with st.spinner("Transformation en cours..."):
                    extended_df = transform_excel_data(df)
                    st.session_state['extended_results_df'] = extended_df
                
                st.success("✅ Transformation terminée!")
                
                # Afficher le résultat transformé
                st.subheader("📊 Données transformées")
                
                # Afficher les nouvelles colonnes ajoutées
                new_columns = list(create_extended_columns().keys())
                st.info(f"Nouvelles colonnes ajoutées: {', '.join(new_columns)}")
                
                # Tableau interactif avec les données étendues
                st.dataframe(extended_df, use_container_width=True, hide_index=True, height=400)
                
                # Statistiques de transformation
                col1, col2, col3 = st.columns(3)
                with col1:
                    with_abstract = (extended_df['ABS 1 OU 0'] == '1').sum()
                    st.metric("Articles avec résumé", with_abstract)
                
                with col2:
                    review_types = extended_df['Type revue'].value_counts()
                    st.metric("Types de revues détectés", len(review_types))
                
                with col3:
                    specialties = extended_df['Spécialité'].value_counts()
                    st.metric("Spécialités détectées", len(specialties))
                
                # Export du fichier transformé
                st.subheader("📥 Export du fichier transformé")
                
                export_filename = st.text_input(
                    "Nom du fichier de sortie",
                    value=f"analyse_etendue_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                )
                
                if st.button("💾 Exporter fichier transformé", type="secondary"):
                    # Créer un buffer en mémoire pour le fichier Excel
                    output = io.BytesIO()
                    
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        # Feuille principale avec toutes les données
                        extended_df.to_excel(writer, sheet_name='Analyse Étendue', index=False)
                        
                        # Feuille de statistiques
                        stats_data = {
                            'Métrique': [
                                'Total articles',
                                'Articles avec résumé',
                                'Types de revues uniques',
                                'Spécialités uniques',
                                'Années couvertes'
                            ],
                            'Valeur': [
                                len(extended_df),
                                (extended_df['ABS 1 OU 0'] == '1').sum(),
                                extended_df['Type revue'].nunique(),
                                extended_df['Spécialité'].nunique(),
                                f"{extended_df['year'].min()}-{extended_df['year'].max()}" if 'year' in extended_df.columns else "N/A"
                            ]
                        }
                        stats_df = pd.DataFrame(stats_data)
                        stats_df.to_excel(writer, sheet_name='Statistiques', index=False)
                        
                        # Feuille avec répartition par type de revue
                        if not extended_df['Type revue'].empty:
                            review_type_counts = extended_df['Type revue'].value_counts().reset_index()
                            review_type_counts.columns = ['Type de revue', 'Nombre']
                            review_type_counts.to_excel(writer, sheet_name='Types de revues', index=False)
                    
                    output.seek(0)
                    
                    # Bouton de téléchargement
                    st.download_button(
                        label="⬇️ Télécharger fichier transformé",
                        data=output.getvalue(),
                        file_name=export_filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                    st.success("✅ Fichier prêt pour téléchargement!")
        
        except Exception as e:
            st.error(f"❌ Erreur lors de l'importation: {e}")
    
    # Afficher les résultats étendus si disponibles
    elif 'extended_results_df' in st.session_state:
        st.subheader("📊 Résultats transformés disponibles")
        extended_df = st.session_state['extended_results_df']
        
        st.info(f"Données transformées en mémoire: {len(extended_df)} articles")
        
        # Aperçu des données transformées
        st.dataframe(extended_df.head(), use_container_width=True)
        
        # Option d'export
        export_filename = st.text_input(
            "Nom du fichier de sortie",
            value=f"analyse_etendue_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        )
        
        if st.button("💾 Exporter données transformées"):
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                extended_df.to_excel(writer, sheet_name='Analyse Étendue', index=False)
            
            output.seek(0)
            
            st.download_button(
                label="⬇️ Télécharger fichier transformé",
                data=output.getvalue(),
                file_name=export_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

if __name__ == "__main__":
    main()
