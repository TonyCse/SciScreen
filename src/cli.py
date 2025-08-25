"""Command Line Interface for the Literature Review Pipeline.

This module provides the main CLI commands for running the literature
review pipeline, including harvesting, processing, screening, and reporting.
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .config import config
from .harvest import crossref, openalex, pubmed, unpaywall
from .pipeline import deduplicate, enrich, filter_rules, normalize, prisma, report, scoring
from .utils_io import load_dataframe, merge_dataframes, save_dataframe
from .zotero.zotero_client import push_papers_to_zotero

# Setup logging
logger = config.setup_logging()


class LiteratureReviewPipeline:
    """Main pipeline orchestrator."""
    
    def __init__(self):
        """Initialize the pipeline."""
        self.metrics = {
            'start_time': time.time(),
            'harvest': {},
            'normalize': {},
            'deduplicate': {},
            'filter': {},
            'enrich': {},
            'scoring': {},
            'screening': {},
            'zotero': {},
            'final_included': 0
        }
        
        self.query_info = {}
    
    def harvest_papers(
        self,
        query: str,
        year_from: int = 2015,
        year_to: int = 2025,
        langs: Optional[List[str]] = None,
        top_n: int = 2000
    ) -> pd.DataFrame:
        """Harvest papers from multiple sources.
        
        Args:
            query: Search query
            year_from: Start year
            year_to: End year
            langs: Allowed languages
            top_n: Maximum papers per source
            
        Returns:
            Combined DataFrame of harvested papers
        """
        logger.info(f"Starting harvest with query: '{query}' ({year_from}-{year_to})")
        
        # Store query info for reporting
        self.query_info = {
            'query': query,
            'year_from': year_from,
            'year_to': year_to,
            'langs': langs or [],
            'top_n': top_n,
            'timestamp': datetime.now().isoformat()
        }
        
        dataframes = []
        source_names = []
        
        try:
            # OpenAlex
            logger.info("Harvesting from OpenAlex...")
            openalex_df = openalex.get_works(
                query=query,
                year_from=year_from,
                year_to=year_to,
                max_results=top_n
            )
            if not openalex_df.empty:
                dataframes.append(openalex_df)
                source_names.append('openalex')
                self.metrics['harvest']['openalex'] = len(openalex_df)
                logger.info(f"OpenAlex: {len(openalex_df)} papers harvested")
            
        except Exception as e:
            logger.error(f"Error harvesting from OpenAlex: {e}")
            self.metrics['harvest']['openalex'] = 0
        
        try:
            # Crossref
            logger.info("Harvesting from Crossref...")
            crossref_df = crossref.search_works(
                query=query,
                year_from=year_from,
                year_to=year_to,
                max_results=top_n
            )
            if not crossref_df.empty:
                dataframes.append(crossref_df)
                source_names.append('crossref')
                self.metrics['harvest']['crossref'] = len(crossref_df)
                logger.info(f"Crossref: {len(crossref_df)} papers harvested")
            
        except Exception as e:
            logger.error(f"Error harvesting from Crossref: {e}")
            self.metrics['harvest']['crossref'] = 0
        
        try:
            # PubMed
            logger.info("Harvesting from PubMed...")
            pubmed_df = pubmed.search_and_fetch(
                query=query,
                year_from=year_from,
                year_to=year_to,
                max_results=top_n
            )
            if not pubmed_df.empty:
                dataframes.append(pubmed_df)
                source_names.append('pubmed')
                self.metrics['harvest']['pubmed'] = len(pubmed_df)
                logger.info(f"PubMed: {len(pubmed_df)} papers harvested")
            
        except Exception as e:
            logger.error(f"Error harvesting from PubMed: {e}")
            self.metrics['harvest']['pubmed'] = 0
        
        # Merge all dataframes
        if dataframes:
            combined_df = merge_dataframes(dataframes, source_names)
            logger.info(f"Total harvested: {len(combined_df)} papers from {len(dataframes)} sources")
            
            # Save combined raw data
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            raw_file = config.data_dir / "raw" / f"combined_harvest_{timestamp}.csv"
            save_dataframe(combined_df, raw_file)
            
            return combined_df
        else:
            logger.warning("No papers harvested from any source")
            return pd.DataFrame()
    
    def process_papers(
        self,
        df: pd.DataFrame,
        allow_preprints: bool = True,
        use_crossref: bool = True,
        use_unpaywall: bool = True
    ) -> pd.DataFrame:
        """Process harvested papers through the complete pipeline.
        
        Args:
            df: Harvested papers DataFrame
            allow_preprints: Whether to allow preprints
            use_crossref: Whether to use Crossref for enrichment
            use_unpaywall: Whether to use Unpaywall for enrichment
            
        Returns:
            Processed DataFrame ready for screening
        """
        if df.empty:
            logger.warning("No papers to process")
            return df
        
        logger.info(f"Processing {len(df)} harvested papers...")
        
        # Step 1: Normalize
        logger.info("Step 1: Normalizing data...")
        normalized_df = normalize.normalize_dataframe(df)
        self.metrics['normalize'] = {'final_count': len(normalized_df)}
        
        # Step 2: Deduplicate
        logger.info("Step 2: Removing duplicates...")
        deduplicated_df, dedup_metrics = deduplicate.deduplicate_dataframe(normalized_df)
        self.metrics['deduplicate'] = dedup_metrics
        
        # Step 3: Filter
        logger.info("Step 3: Applying filters...")
        filtered_df, filter_metrics = filter_rules.apply_filter_rules(
            deduplicated_df,
            langs=self.query_info.get('langs'),
            year_from=self.query_info.get('year_from'),
            year_to=self.query_info.get('year_to'),
            allow_preprints=allow_preprints,
            require_essential_fields=True
        )
        self.metrics['filter'] = filter_metrics
        
        # Step 4: Enrich
        logger.info("Step 4: Enriching metadata...")
        enriched_df = enrich.enrich_dataframe(
            filtered_df,
            use_crossref=use_crossref,
            use_unpaywall=use_unpaywall
        )
        self.metrics['enrich'] = {'final_count': len(enriched_df)}
        
        # Step 5: Score
        logger.info("Step 5: Scoring papers...")
        scored_df = scoring.score_papers(enriched_df, self.query_info.get('query', ''))
        self.metrics['scoring'] = {'final_count': len(scored_df)}
        
        # Save processed data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        processed_file = config.data_dir / "processed" / f"processed_papers_{timestamp}.csv"
        save_dataframe(scored_df, processed_file)
        
        logger.info(f"Processing completed: {len(df)} → {len(scored_df)} papers")
        
        return scored_df
    
    def prepare_screening_file(self, df: pd.DataFrame) -> bool:
        """Prepare Excel file for manual screening.
        
        Args:
            df: Processed papers DataFrame
            
        Returns:
            True if successful, False otherwise
        """
        if df.empty:
            logger.warning("No papers to prepare for screening")
            return False
        
        try:
            output_path = config.outputs_dir / "to_screen.xlsx"
            scoring.prepare_screening_excel(df, output_path)
            logger.info(f"Screening file prepared: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error preparing screening file: {e}")
            return False
    
    def load_screening_decisions(self) -> pd.DataFrame:
        """Load manual screening decisions.
        
        Returns:
            DataFrame with screening decisions
        """
        decisions_file = config.outputs_dir / "decisions.xlsx"
        
        if not decisions_file.exists():
            logger.warning(f"No screening decisions found at {decisions_file}")
            return pd.DataFrame()
        
        try:
            decisions_df = load_dataframe(decisions_file)
            logger.info(f"Loaded {len(decisions_df)} screening decisions")
            return decisions_df
        except Exception as e:
            logger.error(f"Error loading screening decisions: {e}")
            return pd.DataFrame()
    
    def apply_screening_decisions(
        self,
        df: pd.DataFrame,
        decisions_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Apply manual screening decisions to papers.
        
        Args:
            df: Papers DataFrame
            decisions_df: Screening decisions DataFrame
            
        Returns:
            DataFrame with only included papers
        """
        if df.empty or decisions_df.empty:
            logger.warning("Cannot apply screening decisions: missing data")
            return df
        
        # Get included papers
        included_decisions = decisions_df[decisions_df['decision'] == 'include']
        included_ids = set(included_decisions['paper_id'].tolist())
        
        # Filter DataFrame
        # Try to match by DOI first, then by other IDs
        included_df = pd.DataFrame()
        
        for _, row in df.iterrows():
            paper_id = row.get('doi', row.get('id', ''))
            if paper_id in included_ids:
                included_df = pd.concat([included_df, row.to_frame().T], ignore_index=True)
        
        logger.info(f"Applied screening decisions: {len(df)} → {len(included_df)} papers included")
        
        # Update metrics
        self.metrics['screening'] = {
            'total_screened': len(df),
            'included_count': len(included_df),
            'excluded_count': len(df) - len(included_df)
        }
        
        return included_df
    
    def push_to_zotero(
        self,
        df: pd.DataFrame,
        collection_name: str,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Push papers to Zotero collection.
        
        Args:
            df: Papers to push
            collection_name: Name of Zotero collection
            tags: Optional tags to add
            
        Returns:
            True if successful, False otherwise
        """
        if df.empty:
            logger.warning("No papers to push to Zotero")
            return False
        
        try:
            # Add pipeline tags
            default_tags = [
                f"lit-review-{datetime.now().strftime('%Y-%m-%d')}",
                "automated-import"
            ]
            
            if tags:
                default_tags.extend(tags)
            
            # Push to Zotero
            results = push_papers_to_zotero(df, collection_name, default_tags)
            
            self.metrics['zotero'] = results
            
            success_rate = results['successful'] / (results['successful'] + results['failed']) * 100 if (results['successful'] + results['failed']) > 0 else 0
            logger.info(f"Zotero push completed: {results['successful']} successful ({success_rate:.1f}%)")
            
            return results['successful'] > 0
            
        except Exception as e:
            logger.error(f"Error pushing to Zotero: {e}")
            return False
    
    def generate_reports(self, df: pd.DataFrame) -> bool:
        """Generate PRISMA diagram and final report.
        
        Args:
            df: Final included papers DataFrame
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update final metrics
            self.metrics['final_included'] = len(df)
            self.metrics['end_time'] = time.time()
            self.metrics['total_duration'] = self.metrics['end_time'] - self.metrics['start_time']
            
            # Generate PRISMA diagram
            logger.info("Generating PRISMA diagram...")
            prisma_path = config.outputs_dir / "prisma.png"
            prisma.generate_prisma_diagram(
                self.metrics,
                prisma_path,
                f"PRISMA Flow Diagram - {config.project_name}"
            )
            
            # Generate report
            logger.info("Generating final report...")
            report_path = config.outputs_dir / "report.md"
            report.generate_report(
                df,
                self.metrics,
                self.query_info,
                report_path,
                "markdown"
            )
            
            # Also generate HTML version
            html_path = config.outputs_dir / "report.html"
            report.generate_report(
                df,
                self.metrics,
                self.query_info,
                html_path,
                "html"
            )
            
            logger.info(f"Reports generated: {report_path}, {html_path}, {prisma_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating reports: {e}")
            return False


def cmd_harvest(args):
    """Handle harvest command."""
    pipeline = LiteratureReviewPipeline()
    
    # Parse languages
    langs = [lang.strip() for lang in args.langs.split(',')] if args.langs else None
    
    # Run harvest
    df = pipeline.harvest_papers(
        query=args.query,
        year_from=args.year_from,
        year_to=args.year_to,
        langs=langs,
        top_n=args.top_n
    )
    
    if df.empty:
        logger.error("No papers harvested")
        return False
    
    logger.info(f"Harvest completed: {len(df)} papers")
    return True


def cmd_process(args):
    """Handle process command."""
    pipeline = LiteratureReviewPipeline()
    
    # Load latest harvest data
    raw_dir = config.data_dir / "raw"
    harvest_files = list(raw_dir.glob("combined_harvest_*.csv"))
    
    if not harvest_files:
        logger.error("No harvest files found. Run 'harvest' command first.")
        return False
    
    # Load most recent harvest
    latest_file = max(harvest_files, key=lambda x: x.stat().st_mtime)
    logger.info(f"Loading harvest data from {latest_file}")
    
    try:
        df = load_dataframe(latest_file)
    except Exception as e:
        logger.error(f"Error loading harvest data: {e}")
        return False
    
    # Process papers
    processed_df = pipeline.process_papers(
        df,
        allow_preprints=args.allow_preprints,
        use_crossref=True,
        use_unpaywall=True
    )
    
    if processed_df.empty:
        logger.error("No papers after processing")
        return False
    
    # Prepare screening file
    if not pipeline.prepare_screening_file(processed_df):
        logger.error("Failed to prepare screening file")
        return False
    
    logger.info(f"Processing completed: {len(processed_df)} papers ready for screening")
    return True


def cmd_screen(args):
    """Handle screen command (launches Streamlit)."""
    try:
        import subprocess
        
        # Launch Streamlit app
        streamlit_path = Path(__file__).parent.parent / "app" / "streamlit_app.py"
        
        cmd = ["streamlit", "run", str(streamlit_path)]
        subprocess.run(cmd)
        
        return True
        
    except Exception as e:
        logger.error(f"Error launching Streamlit app: {e}")
        return False


def cmd_zotero_push(args):
    """Handle zotero-push command."""
    pipeline = LiteratureReviewPipeline()
    
    # Load screening decisions
    decisions_df = pipeline.load_screening_decisions()
    
    if decisions_df.empty:
        logger.error("No screening decisions found. Complete screening first.")
        return False
    
    # Load processed papers
    processed_dir = config.data_dir / "processed"
    processed_files = list(processed_dir.glob("processed_papers_*.csv"))
    
    if not processed_files:
        logger.error("No processed papers found. Run 'process' command first.")
        return False
    
    # Load most recent processed file
    latest_file = max(processed_files, key=lambda x: x.stat().st_mtime)
    logger.info(f"Loading processed papers from {latest_file}")
    
    try:
        processed_df = load_dataframe(latest_file)
    except Exception as e:
        logger.error(f"Error loading processed papers: {e}")
        return False
    
    # Apply screening decisions
    included_df = pipeline.apply_screening_decisions(processed_df, decisions_df)
    
    if included_df.empty:
        logger.error("No papers to push to Zotero")
        return False
    
    # Push to Zotero
    success = pipeline.push_to_zotero(
        included_df,
        args.collection,
        tags=args.tags.split(',') if args.tags else None
    )
    
    if success:
        logger.info("Papers successfully pushed to Zotero")
        return True
    else:
        logger.error("Failed to push papers to Zotero")
        return False


def cmd_report(args):
    """Handle report command."""
    pipeline = LiteratureReviewPipeline()
    
    # Load final included papers
    # Try to load from various sources
    df = pd.DataFrame()
    
    # First try screening decisions
    decisions_df = pipeline.load_screening_decisions()
    
    if not decisions_df.empty:
        # Load processed papers and apply decisions
        processed_dir = config.data_dir / "processed"
        processed_files = list(processed_dir.glob("processed_papers_*.csv"))
        
        if processed_files:
            latest_file = max(processed_files, key=lambda x: x.stat().st_mtime)
            processed_df = load_dataframe(latest_file)
            df = pipeline.apply_screening_decisions(processed_df, decisions_df)
    
    # If no screening decisions, use all processed papers
    if df.empty:
        processed_dir = config.data_dir / "processed"
        processed_files = list(processed_dir.glob("processed_papers_*.csv"))
        
        if processed_files:
            latest_file = max(processed_files, key=lambda x: x.stat().st_mtime)
            df = load_dataframe(latest_file)
    
    if df.empty:
        logger.error("No papers found for reporting. Run the pipeline first.")
        return False
    
    # Generate reports
    success = pipeline.generate_reports(df)
    
    if success:
        logger.info("Reports generated successfully")
        return True
    else:
        logger.error("Failed to generate reports")
        return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Literature Review Pipeline CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Complete pipeline
  python -m src.cli harvest --query "machine learning" --year-from 2020
  python -m src.cli process --allow-preprints true
  python -m src.cli screen
  python -m src.cli zotero-push --collection "ML Review"
  python -m src.cli report

  # Individual steps
  python -m src.cli harvest --query "deep learning AND healthcare" --langs en,fr
  python -m src.cli process
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Harvest command
    harvest_parser = subparsers.add_parser('harvest', help='Harvest papers from APIs')
    harvest_parser.add_argument('--query', '-q', required=True, help='Search query')
    harvest_parser.add_argument('--year-from', type=int, default=2015, help='Start year')
    harvest_parser.add_argument('--year-to', type=int, default=2025, help='End year')
    harvest_parser.add_argument('--langs', help='Comma-separated language codes (e.g., en,fr)')
    harvest_parser.add_argument('--top-n', type=int, default=2000, help='Max papers per source')
    harvest_parser.set_defaults(func=cmd_harvest)
    
    # Process command
    process_parser = subparsers.add_parser('process', help='Process harvested papers')
    process_parser.add_argument('--allow-preprints', type=bool, default=True, help='Allow preprints')
    process_parser.set_defaults(func=cmd_process)
    
    # Screen command
    screen_parser = subparsers.add_parser('screen', help='Launch screening interface')
    screen_parser.set_defaults(func=cmd_screen)
    
    # Zotero push command
    zotero_parser = subparsers.add_parser('zotero-push', help='Push papers to Zotero')
    zotero_parser.add_argument('--collection', '-c', required=True, help='Zotero collection name')
    zotero_parser.add_argument('--tags', help='Comma-separated tags to add')
    zotero_parser.set_defaults(func=cmd_zotero_push)
    
    # Report command
    report_parser = subparsers.add_parser('report', help='Generate PRISMA and reports')
    report_parser.set_defaults(func=cmd_report)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Check configuration
    missing_creds = config.get_missing_credentials()
    if missing_creds:
        logger.warning(f"Missing credentials: {missing_creds}")
        logger.info("Some features may not work. Configure credentials in .env file.")
    
    # Run command
    try:
        success = args.func(args)
        return 0 if success else 1
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
