"""Streamlit app for manual paper screening.

This app provides an interface for researchers to manually screen
papers that have been automatically scored by the pipeline.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Add the src directory to the Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from config import config
from utils_io import load_dataframe, save_dataframe

logger = logging.getLogger(__name__)


def load_screening_data() -> pd.DataFrame:
    """Load screening data from Excel file.
    
    Returns:
        DataFrame with papers to screen
    """
    screening_file = config.outputs_dir / "to_screen.xlsx"
    
    if not screening_file.exists():
        st.error(f"Screening file not found: {screening_file}")
        st.info("Please run the pipeline first to generate papers for screening.")
        return pd.DataFrame()
    
    try:
        df = pd.read_excel(screening_file)
        logger.info(f"Loaded {len(df)} papers for screening")
        return df
    except Exception as e:
        st.error(f"Error loading screening file: {e}")
        return pd.DataFrame()


def save_decisions(decisions_df: pd.DataFrame) -> bool:
    """Save screening decisions to file.
    
    Args:
        decisions_df: DataFrame with decisions
        
    Returns:
        True if successful, False otherwise
    """
    try:
        decisions_file = config.outputs_dir / "decisions.xlsx"
        decisions_file.parent.mkdir(parents=True, exist_ok=True)
        
        save_dataframe(decisions_df, decisions_file)
        logger.info(f"Saved {len(decisions_df)} decisions to {decisions_file}")
        return True
    except Exception as e:
        st.error(f"Error saving decisions: {e}")
        return False


def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0
    
    if 'decisions' not in st.session_state:
        st.session_state.decisions = {}
    
    if 'notes' not in st.session_state:
        st.session_state.notes = {}
    
    if 'df' not in st.session_state:
        st.session_state.df = pd.DataFrame()
    
    if 'filtered_df' not in st.session_state:
        st.session_state.filtered_df = pd.DataFrame()


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Apply filters to the DataFrame based on sidebar controls.
    
    Args:
        df: Input DataFrame
        
    Returns:
        Filtered DataFrame
    """
    if df.empty:
        return df
    
    filtered_df = df.copy()
    
    # Year filter
    if 'year' in df.columns:
        years = df['year'].dropna().unique()
        if len(years) > 0:
            min_year, max_year = int(min(years)), int(max(years))
            year_range = st.sidebar.slider(
                "Publication Year Range",
                min_value=min_year,
                max_value=max_year,
                value=(min_year, max_year)
            )
            filtered_df = filtered_df[
                (filtered_df['year'].isna()) | 
                (filtered_df['year'].between(year_range[0], year_range[1]))
            ]
    
    # Source filter
    if 'source' in df.columns:
        sources = df['source'].unique()
        selected_sources = st.sidebar.multiselect(
            "Sources",
            options=sources,
            default=list(sources)
        )
        if selected_sources:
            filtered_df = filtered_df[filtered_df['source'].isin(selected_sources)]
    
    # Document type filter
    if 'doc_type' in df.columns:
        doc_types = df['doc_type'].unique()
        selected_types = st.sidebar.multiselect(
            "Document Types",
            options=doc_types,
            default=list(doc_types)
        )
        if selected_types:
            filtered_df = filtered_df[filtered_df['doc_type'].isin(selected_types)]
    
    # Confidence filter
    if 'confidence' in df.columns:
        min_confidence = st.sidebar.slider(
            "Minimum AI Confidence",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.1
        )
        filtered_df = filtered_df[
            (filtered_df['confidence'].isna()) | 
            (filtered_df['confidence'] >= min_confidence)
        ]
    
    # Open Access filter
    if 'oa_status' in df.columns:
        oa_filter = st.sidebar.selectbox(
            "Open Access Status",
            options=["All", "Open Access Only", "Closed Access Only"]
        )
        if oa_filter == "Open Access Only":
            filtered_df = filtered_df[
                filtered_df['oa_status'].isin(['gold', 'green', 'hybrid'])
            ]
        elif oa_filter == "Closed Access Only":
            filtered_df = filtered_df[
                filtered_df['oa_status'].isin(['closed', 'unknown'])
            ]
    
    # AI recommendation filter
    if 'ai_label' in df.columns:
        ai_filter = st.sidebar.selectbox(
            "AI Recommendation",
            options=["All", "Include", "Exclude"]
        )
        if ai_filter == "Include":
            filtered_df = filtered_df[filtered_df['ai_label'] == 1]
        elif ai_filter == "Exclude":
            filtered_df = filtered_df[filtered_df['ai_label'] == 0]
    
    return filtered_df


def display_paper_details(paper: pd.Series):
    """Display detailed information about a paper.
    
    Args:
        paper: Paper data as pandas Series
    """
    # Title
    st.subheader(paper.get('title', 'No title'))
    
    # Basic info in columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write(f"**Year:** {paper.get('year', 'Unknown')}")
        st.write(f"**Source:** {paper.get('source', 'Unknown')}")
    
    with col2:
        st.write(f"**Type:** {paper.get('doc_type', 'Unknown')}")
        if paper.get('oa_status'):
            oa_status = paper['oa_status']
            if oa_status in ['gold', 'green', 'hybrid']:
                st.write(f"**Access:** 🟢 {oa_status.title()}")
            else:
                st.write(f"**Access:** 🔴 {oa_status.title()}")
    
    with col3:
        if 'confidence' in paper and not pd.isna(paper['confidence']):
            confidence = paper['confidence']
            st.write(f"**AI Confidence:** {confidence:.2f}")
            
            # Color code confidence
            if confidence >= 0.7:
                st.success(f"AI Recommendation: Include")
            elif confidence >= 0.3:
                st.warning(f"AI Recommendation: Uncertain")
            else:
                st.error(f"AI Recommendation: Exclude")
        
        if paper.get('reason'):
            st.write(f"**AI Reason:** {paper['reason']}")
    
    # Authors
    if paper.get('authors'):
        st.write(f"**Authors:** {paper['authors']}")
    
    # Journal
    if paper.get('journal'):
        st.write(f"**Journal:** {paper['journal']}")
    
    # Abstract
    if paper.get('abstract'):
        with st.expander("Abstract", expanded=True):
            st.write(paper['abstract'])
    
    # Links
    links = []
    if paper.get('doi'):
        links.append(f"[DOI](https://doi.org/{paper['doi']})")
    if paper.get('url'):
        links.append(f"[Source]({paper['url']})")
    if paper.get('pdf_url'):
        links.append(f"[PDF]({paper['pdf_url']})")
    
    if links:
        st.write(f"**Links:** {' | '.join(links)}")


def display_screening_interface():
    """Display the main screening interface."""
    df = st.session_state.filtered_df
    
    if df.empty:
        st.warning("No papers to screen with current filters.")
        return
    
    # Progress info
    total_papers = len(df)
    current_idx = st.session_state.current_index
    
    if current_idx >= total_papers:
        st.session_state.current_index = 0
        current_idx = 0
    
    # Navigation
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        if st.button("⏮️ First"):
            st.session_state.current_index = 0
            st.rerun()
    
    with col2:
        if st.button("⏪ Previous") and current_idx > 0:
            st.session_state.current_index = current_idx - 1
            st.rerun()
    
    with col3:
        # Jump to paper
        new_index = st.number_input(
            f"Paper (1-{total_papers})",
            min_value=1,
            max_value=total_papers,
            value=current_idx + 1
        ) - 1
        if new_index != current_idx:
            st.session_state.current_index = new_index
            st.rerun()
    
    with col4:
        if st.button("⏩ Next") and current_idx < total_papers - 1:
            st.session_state.current_index = current_idx + 1
            st.rerun()
    
    with col5:
        if st.button("⏭️ Last"):
            st.session_state.current_index = total_papers - 1
            st.rerun()
    
    # Progress bar
    progress = (current_idx + 1) / total_papers
    st.progress(progress)
    st.write(f"Paper {current_idx + 1} of {total_papers} ({progress:.1%})")
    
    # Get current paper
    current_paper = df.iloc[current_idx]
    paper_id = current_paper.get('doi', current_paper.get('id', current_idx))
    
    # Display paper details
    display_paper_details(current_paper)
    
    # Decision buttons
    st.markdown("---")
    st.subheader("Your Decision")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✅ Include", type="primary", use_container_width=True):
            st.session_state.decisions[paper_id] = "include"
            if current_idx < total_papers - 1:
                st.session_state.current_index = current_idx + 1
            st.rerun()
    
    with col2:
        if st.button("❌ Exclude", type="secondary", use_container_width=True):
            st.session_state.decisions[paper_id] = "exclude"
            if current_idx < total_papers - 1:
                st.session_state.current_index = current_idx + 1
            st.rerun()
    
    with col3:
        if st.button("🤷 Uncertain", use_container_width=True):
            st.session_state.decisions[paper_id] = "uncertain"
            if current_idx < total_papers - 1:
                st.session_state.current_index = current_idx + 1
            st.rerun()
    
    # Notes
    current_note = st.session_state.notes.get(paper_id, "")
    note = st.text_area("Notes (optional)", value=current_note, key=f"note_{paper_id}")
    st.session_state.notes[paper_id] = note
    
    # Show current decision
    current_decision = st.session_state.decisions.get(paper_id)
    if current_decision:
        if current_decision == "include":
            st.success(f"✅ Decision: Include")
        elif current_decision == "exclude":
            st.error(f"❌ Decision: Exclude")
        else:
            st.warning(f"🤷 Decision: Uncertain")


def display_summary_stats():
    """Display summary statistics of decisions."""
    decisions = st.session_state.decisions
    total_decisions = len(decisions)
    
    if total_decisions == 0:
        st.info("No decisions made yet.")
        return
    
    # Count decisions
    include_count = sum(1 for d in decisions.values() if d == "include")
    exclude_count = sum(1 for d in decisions.values() if d == "exclude")
    uncertain_count = sum(1 for d in decisions.values() if d == "uncertain")
    
    # Display stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Decisions", total_decisions)
    
    with col2:
        st.metric("Include", include_count)
    
    with col3:
        st.metric("Exclude", exclude_count)
    
    with col4:
        st.metric("Uncertain", uncertain_count)
    
    # Progress
    total_papers = len(st.session_state.filtered_df)
    if total_papers > 0:
        completion_rate = total_decisions / total_papers
        st.write(f"**Completion:** {completion_rate:.1%} ({total_decisions}/{total_papers})")


def export_decisions():
    """Export screening decisions to file."""
    decisions = st.session_state.decisions
    notes = st.session_state.notes
    
    if not decisions:
        st.warning("No decisions to export.")
        return
    
    # Create decisions DataFrame
    decisions_data = []
    for paper_id, decision in decisions.items():
        decisions_data.append({
            'paper_id': paper_id,
            'decision': decision,
            'note': notes.get(paper_id, ''),
            'timestamp': datetime.now().isoformat(),
            'screener': 'manual'  # Could be made configurable
        })
    
    decisions_df = pd.DataFrame(decisions_data)
    
    # Save to file
    if save_decisions(decisions_df):
        st.success(f"✅ Exported {len(decisions_data)} decisions!")
        
        # Download button
        csv_data = decisions_df.to_csv(index=False)
        st.download_button(
            label="Download Decisions CSV",
            data=csv_data,
            file_name=f"screening_decisions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )


def main():
    """Main Streamlit app."""
    st.set_page_config(
        page_title="Literature Review Screening",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("📚 Literature Review Paper Screening")
    st.markdown("Manual screening interface for literature review papers")
    
    # Initialize session state
    initialize_session_state()
    
    # Load data
    if st.session_state.df.empty:
        st.session_state.df = load_screening_data()
    
    if st.session_state.df.empty:
        st.stop()
    
    # Sidebar
    st.sidebar.title("Filters & Controls")
    
    # Apply filters
    st.session_state.filtered_df = apply_filters(st.session_state.df)
    
    # Reset index if filtered data changed
    if len(st.session_state.filtered_df) != len(st.session_state.df):
        st.session_state.current_index = 0
    
    # Main interface
    tab1, tab2, tab3 = st.tabs(["📖 Screen Papers", "📊 Summary", "💾 Export"])
    
    with tab1:
        display_screening_interface()
    
    with tab2:
        st.subheader("Screening Progress")
        display_summary_stats()
        
        # Show decisions table
        if st.session_state.decisions:
            st.subheader("Recent Decisions")
            decisions_list = []
            for paper_id, decision in list(st.session_state.decisions.items())[-10:]:
                decisions_list.append({
                    'Paper ID': paper_id,
                    'Decision': decision,
                    'Note': st.session_state.notes.get(paper_id, '')[:50] + '...' if len(st.session_state.notes.get(paper_id, '')) > 50 else st.session_state.notes.get(paper_id, '')
                })
            
            if decisions_list:
                st.dataframe(pd.DataFrame(decisions_list), use_container_width=True)
    
    with tab3:
        st.subheader("Export Decisions")
        export_decisions()
    
    # Auto-save every few decisions
    if len(st.session_state.decisions) > 0 and len(st.session_state.decisions) % 10 == 0:
        # Create temp save
        decisions_data = []
        for paper_id, decision in st.session_state.decisions.items():
            decisions_data.append({
                'paper_id': paper_id,
                'decision': decision,
                'note': st.session_state.notes.get(paper_id, ''),
                'timestamp': datetime.now().isoformat()
            })
        
        temp_df = pd.DataFrame(decisions_data)
        temp_file = config.outputs_dir / "screening_progress.csv"
        save_dataframe(temp_df, temp_file)


if __name__ == "__main__":
    main()
