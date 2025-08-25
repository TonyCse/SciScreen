"""Version simplifiée de l'application Streamlit pour démonstration.

Cette version fonctionne sans dépendances externes complexes.
"""

import pandas as pd
import streamlit as st
from pathlib import Path

# Configuration simple
OUTPUT_DIR = Path("data/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_demo_data():
    """Charger des données de démonstration."""
    demo_papers = [
        {
            "title": "Cognitive Behavioral Therapy for Depression: A Systematic Review",
            "abstract": "This systematic review examines the effectiveness of cognitive behavioral therapy (CBT) in treating depression. We analyzed 45 randomized controlled trials involving 3,200 participants.",
            "authors": "Smith, J.A.; Johnson, M.K.; Brown, S.L.",
            "journal": "Journal of Clinical Psychology",
            "year": 2023,
            "source": "openalex",
            "ai_label": 1,
            "confidence": 0.92,
            "reason": "High relevance to CBT and depression",
            "doi": "10.1000/example1",
            "oa_status": "gold"
        },
        {
            "title": "Machine Learning Applications in Mental Health Screening",
            "abstract": "Recent advances in machine learning have opened new possibilities for mental health screening and diagnosis. This paper reviews current applications of ML techniques.",
            "authors": "Davis, R.M.; Wilson, K.J.; Thompson, L.P.",
            "journal": "Journal of Medical Informatics",
            "year": 2022,
            "source": "crossref",
            "ai_label": 0,
            "confidence": 0.23,
            "reason": "Limited relevance to therapy",
            "doi": "10.1000/example2",
            "oa_status": "closed"
        },
        {
            "title": "Effectiveness of Online CBT Interventions: A Meta-Analysis",
            "abstract": "The COVID-19 pandemic has accelerated the adoption of online therapy interventions. This meta-analysis evaluates the effectiveness of internet-delivered cognitive behavioral therapy.",
            "authors": "Garcia, M.A.; Lee, S.H.; Anderson, D.R.",
            "journal": "Clinical Psychology Review",
            "year": 2021,
            "source": "pubmed",
            "ai_label": 1,
            "confidence": 0.89,
            "reason": "Directly relevant to CBT effectiveness",
            "doi": "10.1000/example3",
            "oa_status": "green"
        },
        {
            "title": "Depression Treatment Outcomes in Primary Care Settings",
            "abstract": "This longitudinal study follows 500 patients receiving depression treatment in primary care settings over 12 months.",
            "authors": "Miller, P.K.; Jones, A.B.; White, C.D.",
            "journal": "Primary Care Mental Health",
            "year": 2023,
            "source": "openalex",
            "ai_label": 1,
            "confidence": 0.76,
            "reason": "Relevant to depression treatment",
            "doi": "10.1000/example4",
            "oa_status": "hybrid"
        },
        {
            "title": "Neuroscience Basis of Cognitive Behavioral Therapy",
            "abstract": "Understanding the neural mechanisms underlying CBT can help optimize treatment protocols. This review synthesizes neuroimaging studies.",
            "authors": "Neural, B.R.; Cortex, F.L.; Synapse, N.T.",
            "journal": "Nature Neuroscience",
            "year": 2023,
            "source": "pubmed",
            "ai_label": 1,
            "confidence": 0.85,
            "reason": "CBT mechanisms research",
            "doi": "10.1000/example6",
            "oa_status": "closed"
        }
    ]
    
    return pd.DataFrame(demo_papers)

def display_paper_details(paper):
    """Afficher les détails d'un article."""
    st.subheader(paper.get('title', 'Sans titre'))
    
    # Informations de base
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write(f"**Année:** {paper.get('year', 'Inconnue')}")
        st.write(f"**Source:** {paper.get('source', 'Inconnue')}")
    
    with col2:
        st.write(f"**Journal:** {paper.get('journal', 'Inconnu')}")
        oa_status = paper.get('oa_status', 'unknown')
        if oa_status in ['gold', 'green', 'hybrid']:
            st.write(f"**Accès:** 🟢 {oa_status.title()}")
        else:
            st.write(f"**Accès:** 🔴 {oa_status.title()}")
    
    with col3:
        confidence = paper.get('confidence', 0)
        st.write(f"**Confiance IA:** {confidence:.2f}")
        
        if confidence >= 0.7:
            st.success("✅ IA recommande: Inclure")
        elif confidence >= 0.3:
            st.warning("🤷 IA recommande: Incertain")
        else:
            st.error("❌ IA recommande: Exclure")
        
        if paper.get('reason'):
            st.write(f"**Raison:** {paper['reason']}")
    
    # Auteurs
    if paper.get('authors'):
        st.write(f"**Auteurs:** {paper['authors']}")
    
    # Résumé
    if paper.get('abstract'):
        with st.expander("Résumé", expanded=True):
            st.write(paper['abstract'])
    
    # Liens
    if paper.get('doi'):
        st.write(f"**DOI:** [https://doi.org/{paper['doi']}](https://doi.org/{paper['doi']})")

def main():
    """Application Streamlit principale."""
    st.set_page_config(
        page_title="Literature Review Screening",
        page_icon="📚",
        layout="wide"
    )
    
    st.title("📚 Literature Review Paper Screening")
    st.markdown("Interface de tri manuel pour articles de revue de littérature")
    
    # Initialiser les données
    if 'df' not in st.session_state:
        st.session_state.df = load_demo_data()
    
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0
    
    if 'decisions' not in st.session_state:
        st.session_state.decisions = {}
    
    df = st.session_state.df
    
    # Sidebar pour filtres
    st.sidebar.title("Filtres")
    
    # Filtre par source
    sources = df['source'].unique()
    selected_sources = st.sidebar.multiselect("Sources", sources, default=list(sources))
    
    # Filtre par confiance IA
    min_confidence = st.sidebar.slider("Confiance IA minimale", 0.0, 1.0, 0.0, 0.1)
    
    # Appliquer filtres
    filtered_df = df[
        (df['source'].isin(selected_sources)) &
        (df['confidence'] >= min_confidence)
    ].reset_index(drop=True)
    
    if filtered_df.empty:
        st.warning("Aucun article ne correspond aux filtres sélectionnés.")
        return
    
    # Navigation
    total_papers = len(filtered_df)
    current_idx = st.session_state.current_index
    
    if current_idx >= total_papers:
        st.session_state.current_index = 0
        current_idx = 0
    
    # Contrôles de navigation
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        if st.button("⏮️ Premier"):
            st.session_state.current_index = 0
            st.rerun()
    
    with col2:
        if st.button("⏪ Précédent") and current_idx > 0:
            st.session_state.current_index = current_idx - 1
            st.rerun()
    
    with col3:
        new_index = st.number_input(
            f"Article (1-{total_papers})",
            min_value=1,
            max_value=total_papers,
            value=current_idx + 1
        ) - 1
        if new_index != current_idx:
            st.session_state.current_index = new_index
            st.rerun()
    
    with col4:
        if st.button("⏩ Suivant") and current_idx < total_papers - 1:
            st.session_state.current_index = current_idx + 1
            st.rerun()
    
    with col5:
        if st.button("⏭️ Dernier"):
            st.session_state.current_index = total_papers - 1
            st.rerun()
    
    # Barre de progression
    progress = (current_idx + 1) / total_papers
    st.progress(progress)
    st.write(f"Article {current_idx + 1} sur {total_papers} ({progress:.1%})")
    
    # Afficher l'article actuel
    current_paper = filtered_df.iloc[current_idx]
    paper_id = current_paper.get('doi', current_idx)
    
    display_paper_details(current_paper)
    
    # Boutons de décision
    st.markdown("---")
    st.subheader("Votre décision")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✅ Inclure", type="primary", use_container_width=True):
            st.session_state.decisions[paper_id] = "include"
            if current_idx < total_papers - 1:
                st.session_state.current_index = current_idx + 1
            st.success("✅ Article inclus !")
            st.rerun()
    
    with col2:
        if st.button("❌ Exclure", type="secondary", use_container_width=True):
            st.session_state.decisions[paper_id] = "exclude"
            if current_idx < total_papers - 1:
                st.session_state.current_index = current_idx + 1
            st.error("❌ Article exclu !")
            st.rerun()
    
    with col3:
        if st.button("🤷 Incertain", use_container_width=True):
            st.session_state.decisions[paper_id] = "uncertain"
            if current_idx < total_papers - 1:
                st.session_state.current_index = current_idx + 1
            st.warning("🤷 À décider plus tard !")
            st.rerun()
    
    # Afficher la décision actuelle
    current_decision = st.session_state.decisions.get(paper_id)
    if current_decision:
        if current_decision == "include":
            st.success("✅ Décision actuelle: Inclure")
        elif current_decision == "exclude":
            st.error("❌ Décision actuelle: Exclure")
        else:
            st.warning("🤷 Décision actuelle: Incertain")
    
    # Statistiques dans la sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("Statistiques")
    
    decisions = st.session_state.decisions
    include_count = sum(1 for d in decisions.values() if d == "include")
    exclude_count = sum(1 for d in decisions.values() if d == "exclude")
    uncertain_count = sum(1 for d in decisions.values() if d == "uncertain")
    
    st.sidebar.metric("Décisions prises", len(decisions))
    st.sidebar.metric("Inclus", include_count)
    st.sidebar.metric("Exclus", exclude_count)
    st.sidebar.metric("Incertains", uncertain_count)
    
    # Export des décisions
    if decisions:
        st.sidebar.markdown("---")
        st.sidebar.subheader("Export")
        
        decisions_df = pd.DataFrame([
            {"paper_id": pid, "decision": decision}
            for pid, decision in decisions.items()
        ])
        
        csv_data = decisions_df.to_csv(index=False)
        st.sidebar.download_button(
            label="📥 Télécharger décisions CSV",
            data=csv_data,
            file_name="screening_decisions.csv",
            mime="text/csv"
        )
        
        if st.sidebar.button("💾 Sauvegarder décisions"):
            decisions_file = OUTPUT_DIR / "decisions.csv"
            decisions_df.to_csv(decisions_file, index=False)
            st.sidebar.success(f"✅ Sauvegardé: {decisions_file}")

if __name__ == "__main__":
    main()
