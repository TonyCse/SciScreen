"""Report generation module for the Literature Review Pipeline.

This module creates comprehensive reports summarizing the literature
review process, findings, and statistics.
"""

import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from ..config import config
from .prisma import generate_prisma_summary

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generator for literature review reports."""
    
    def __init__(self):
        """Initialize report generator."""
        self.metrics = {}
        self.df = pd.DataFrame()
        self.query_info = {}
    
    def set_data(
        self,
        df: pd.DataFrame,
        pipeline_metrics: Dict,
        query_info: Optional[Dict] = None
    ) -> None:
        """Set data for report generation.
        
        Args:
            df: Final DataFrame of included papers
            pipeline_metrics: Metrics from pipeline execution
            query_info: Information about search queries and parameters
        """
        self.df = df.copy() if not df.empty else pd.DataFrame()
        self.metrics = pipeline_metrics.copy()
        self.query_info = query_info or {}
        
        logger.info(f"Report data set: {len(self.df)} papers, {len(self.metrics)} metric groups")
    
    def generate_summary_statistics(self) -> Dict:
        """Generate summary statistics from the data.
        
        Returns:
            Dictionary with summary statistics
        """
        stats = {}
        
        if self.df.empty:
            return stats
        
        # Basic counts
        stats['total_papers'] = len(self.df)
        
        # By year
        if 'year' in self.df.columns:
            year_counts = self.df['year'].value_counts().sort_index()
            stats['papers_by_year'] = year_counts.to_dict()
            stats['year_range'] = f"{year_counts.index.min()}-{year_counts.index.max()}"
            stats['most_productive_year'] = year_counts.idxmax()
            stats['most_productive_year_count'] = year_counts.max()
        
        # By source
        if 'source' in self.df.columns:
            source_counts = self.df['source'].value_counts()
            stats['papers_by_source'] = source_counts.to_dict()
            stats['primary_source'] = source_counts.idxmax()
            stats['primary_source_count'] = source_counts.max()
        
        # By document type
        if 'doc_type' in self.df.columns:
            type_counts = self.df['doc_type'].value_counts()
            stats['papers_by_type'] = type_counts.to_dict()
            stats['most_common_type'] = type_counts.idxmax()
            stats['most_common_type_count'] = type_counts.max()
        
        # By journal
        if 'journal' in self.df.columns:
            journal_counts = self.df['journal'].value_counts().head(10)
            stats['top_journals'] = journal_counts.to_dict()
            stats['unique_journals'] = self.df['journal'].nunique()
        
        # Open access
        if 'oa_status' in self.df.columns:
            oa_counts = self.df['oa_status'].value_counts()
            stats['papers_by_oa_status'] = oa_counts.to_dict()
            
            open_access_papers = self.df[self.df['oa_status'].isin(['gold', 'green', 'hybrid'])]
            stats['open_access_count'] = len(open_access_papers)
            stats['open_access_percentage'] = (len(open_access_papers) / len(self.df)) * 100
        
        # Languages
        if 'lang' in self.df.columns:
            lang_counts = self.df['lang'].value_counts()
            stats['papers_by_language'] = lang_counts.to_dict()
        
        # Citations
        if 'cited_by' in self.df.columns:
            citations = self.df['cited_by'].fillna(0)
            stats['total_citations'] = citations.sum()
            stats['avg_citations'] = citations.mean()
            stats['median_citations'] = citations.median()
            stats['max_citations'] = citations.max()
            
            # Most cited papers
            most_cited = self.df.nlargest(5, 'cited_by')[['title', 'cited_by', 'authors']]
            stats['most_cited_papers'] = most_cited.to_dict('records')
        
        # Authors
        if 'authors' in self.df.columns:
            all_authors = []
            for authors_str in self.df['authors'].fillna(''):
                if authors_str:
                    # Split and clean author names
                    authors = [a.strip() for a in authors_str.split(';') if a.strip()]
                    all_authors.extend(authors)
            
            if all_authors:
                author_counts = Counter(all_authors)
                stats['unique_authors'] = len(author_counts)
                stats['total_author_instances'] = len(all_authors)
                stats['avg_authors_per_paper'] = len(all_authors) / len(self.df)
                
                # Most prolific authors
                top_authors = dict(author_counts.most_common(10))
                stats['most_prolific_authors'] = top_authors
        
        return stats
    
    def generate_methodology_section(self) -> str:
        """Generate methodology section for the report.
        
        Returns:
            Methodology section text
        """
        methodology = []
        
        methodology.append("## Methodology")
        methodology.append("")
        
        # Search strategy
        methodology.append("### Search Strategy")
        methodology.append("")
        
        if self.query_info:
            query = self.query_info.get('query', 'Not specified')
            methodology.append(f"**Search Query:** `{query}`")
            methodology.append("")
            
            year_from = self.query_info.get('year_from', 'Not specified')
            year_to = self.query_info.get('year_to', 'Not specified')
            methodology.append(f"**Publication Year Range:** {year_from} - {year_to}")
            methodology.append("")
            
            langs = self.query_info.get('langs', [])
            if langs:
                methodology.append(f"**Languages:** {', '.join(langs)}")
                methodology.append("")
        
        # Databases
        methodology.append("### Databases Searched")
        methodology.append("")
        methodology.append("The following databases were systematically searched:")
        methodology.append("- **OpenAlex:** Comprehensive bibliographic database")
        methodology.append("- **Crossref:** Academic publications metadata")
        methodology.append("- **PubMed:** Biomedical literature database")
        methodology.append("")
        
        # Data processing
        methodology.append("### Data Processing")
        methodology.append("")
        methodology.append("The retrieved records were processed through the following steps:")
        methodology.append("1. **Normalization:** Standardization of metadata fields")
        methodology.append("2. **Deduplication:** Removal of duplicate records using DOI/PMID and fuzzy title matching")
        methodology.append("3. **Filtering:** Application of inclusion/exclusion criteria")
        methodology.append("4. **Enrichment:** Enhancement with open access information from Unpaywall")
        methodology.append("5. **Screening:** Manual or AI-assisted relevance assessment")
        methodology.append("")
        
        # Inclusion criteria
        methodology.append("### Inclusion/Exclusion Criteria")
        methodology.append("")
        
        if self.query_info:
            allow_preprints = self.query_info.get('allow_preprints', True)
            if not allow_preprints:
                methodology.append("- Preprints were excluded")
            
            langs = self.query_info.get('langs', [])
            if langs:
                methodology.append(f"- Only papers in the following languages: {', '.join(langs)}")
            
            methodology.append("- Papers must have a title and either an abstract, DOI, or PMID")
        
        methodology.append("")
        
        return "\n".join(methodology)
    
    def generate_results_section(self, stats: Dict) -> str:
        """Generate results section for the report.
        
        Args:
            stats: Summary statistics dictionary
            
        Returns:
            Results section text
        """
        results = []
        
        results.append("## Results")
        results.append("")
        
        # Overview
        results.append("### Overview")
        results.append("")
        
        total_papers = stats.get('total_papers', 0)
        results.append(f"A total of **{total_papers:,} papers** were included in the final literature review.")
        results.append("")
        
        # Temporal distribution
        if 'papers_by_year' in stats:
            results.append("### Temporal Distribution")
            results.append("")
            
            year_range = stats.get('year_range', 'Unknown')
            results.append(f"The included papers span from **{year_range}**.")
            
            most_productive_year = stats.get('most_productive_year')
            most_productive_year_count = stats.get('most_productive_year_count')
            if most_productive_year and most_productive_year_count:
                results.append(f"The most productive year was **{most_productive_year}** with {most_productive_year_count} papers.")
            
            results.append("")
            
            # Year breakdown
            papers_by_year = stats['papers_by_year']
            if len(papers_by_year) <= 10:
                results.append("**Papers by year:**")
                for year, count in sorted(papers_by_year.items()):
                    results.append(f"- {year}: {count} papers")
                results.append("")
        
        # Sources
        if 'papers_by_source' in stats:
            results.append("### Data Sources")
            results.append("")
            
            papers_by_source = stats['papers_by_source']
            results.append("**Papers by source:**")
            for source, count in papers_by_source.items():
                percentage = (count / total_papers) * 100
                results.append(f"- {source.title()}: {count} papers ({percentage:.1f}%)")
            results.append("")
        
        # Document types
        if 'papers_by_type' in stats:
            results.append("### Document Types")
            results.append("")
            
            papers_by_type = stats['papers_by_type']
            results.append("**Papers by document type:**")
            for doc_type, count in papers_by_type.items():
                percentage = (count / total_papers) * 100
                results.append(f"- {doc_type.replace('-', ' ').title()}: {count} papers ({percentage:.1f}%)")
            results.append("")
        
        # Open Access
        if 'open_access_percentage' in stats:
            results.append("### Open Access Availability")
            results.append("")
            
            oa_percentage = stats['open_access_percentage']
            oa_count = stats['open_access_count']
            results.append(f"**{oa_count} papers ({oa_percentage:.1f}%)** are available as open access.")
            results.append("")
            
            if 'papers_by_oa_status' in stats:
                oa_breakdown = stats['papers_by_oa_status']
                results.append("**Open access breakdown:**")
                for oa_type, count in oa_breakdown.items():
                    if oa_type in ['gold', 'green', 'hybrid']:
                        results.append(f"- {oa_type.title()}: {count} papers")
                results.append("")
        
        # Top journals
        if 'top_journals' in stats:
            results.append("### Top Journals")
            results.append("")
            
            unique_journals = stats.get('unique_journals', 0)
            results.append(f"Papers were published in **{unique_journals}** different journals.")
            results.append("")
            
            top_journals = stats['top_journals']
            results.append("**Top 10 journals by number of papers:**")
            for i, (journal, count) in enumerate(top_journals.items(), 1):
                percentage = (count / total_papers) * 100
                results.append(f"{i}. {journal}: {count} papers ({percentage:.1f}%)")
            results.append("")
        
        # Authors
        if 'unique_authors' in stats:
            results.append("### Author Statistics")
            results.append("")
            
            unique_authors = stats['unique_authors']
            avg_authors = stats.get('avg_authors_per_paper', 0)
            results.append(f"**{unique_authors:,} unique authors** contributed to the included papers.")
            results.append(f"Average number of authors per paper: **{avg_authors:.1f}**")
            results.append("")
            
            if 'most_prolific_authors' in stats:
                prolific_authors = stats['most_prolific_authors']
                results.append("**Most prolific authors:**")
                for i, (author, count) in enumerate(list(prolific_authors.items())[:10], 1):
                    results.append(f"{i}. {author}: {count} papers")
                results.append("")
        
        # Citations
        if 'total_citations' in stats:
            results.append("### Citation Analysis")
            results.append("")
            
            total_citations = stats['total_citations']
            avg_citations = stats['avg_citations']
            median_citations = stats['median_citations']
            max_citations = stats['max_citations']
            
            results.append(f"**Total citations:** {total_citations:,}")
            results.append(f"**Average citations per paper:** {avg_citations:.1f}")
            results.append(f"**Median citations:** {median_citations:.0f}")
            results.append(f"**Maximum citations:** {max_citations:.0f}")
            results.append("")
            
            if 'most_cited_papers' in stats:
                most_cited = stats['most_cited_papers']
                results.append("**Most cited papers:**")
                for i, paper in enumerate(most_cited, 1):
                    title = paper['title'][:100] + "..." if len(paper['title']) > 100 else paper['title']
                    citations = paper['cited_by']
                    authors = paper['authors'][:50] + "..." if len(paper['authors']) > 50 else paper['authors']
                    results.append(f"{i}. {title} ({citations} citations)")
                    results.append(f"   Authors: {authors}")
                    results.append("")
        
        return "\n".join(results)
    
    def generate_prisma_section(self) -> str:
        """Generate PRISMA section for the report.
        
        Returns:
            PRISMA section text
        """
        prisma_section = []
        
        prisma_section.append("## PRISMA Flow")
        prisma_section.append("")
        prisma_section.append("The following PRISMA flow diagram shows the selection process:")
        prisma_section.append("")
        
        # Generate PRISMA summary
        try:
            prisma_summary = generate_prisma_summary(self.metrics)
            prisma_section.append("```")
            prisma_section.append(prisma_summary)
            prisma_section.append("```")
        except Exception as e:
            logger.error(f"Error generating PRISMA summary: {e}")
            prisma_section.append("*PRISMA summary could not be generated*")
        
        prisma_section.append("")
        
        return "\n".join(prisma_section)
    
    def generate_full_report(self) -> str:
        """Generate the complete literature review report.
        
        Returns:
            Complete report text in Markdown format
        """
        report = []
        
        # Header
        project_name = config.project_name
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report.append(f"# Literature Review Report: {project_name}")
        report.append("")
        report.append(f"**Generated:** {timestamp}")
        report.append(f"**Pipeline Version:** 1.0")
        report.append("")
        
        # Executive Summary
        stats = self.generate_summary_statistics()
        total_papers = stats.get('total_papers', 0)
        
        report.append("## Executive Summary")
        report.append("")
        report.append(f"This literature review identified and analyzed **{total_papers:,} relevant papers** ")
        
        if 'year_range' in stats:
            report.append(f"published between {stats['year_range']}. ")
        
        if 'papers_by_source' in stats:
            sources = list(stats['papers_by_source'].keys())
            report.append(f"Papers were retrieved from {len(sources)} databases: {', '.join(sources)}.")
        
        report.append("")
        
        # Methodology
        report.append(self.generate_methodology_section())
        
        # PRISMA Flow
        report.append(self.generate_prisma_section())
        
        # Results
        report.append(self.generate_results_section(stats))
        
        # Limitations
        report.append("## Limitations")
        report.append("")
        report.append("This literature review has the following limitations:")
        report.append("- Search was limited to the specified databases and may not capture all relevant literature")
        report.append("- Automated processing may have introduced biases in selection or classification")
        report.append("- Citation counts are based on available data and may not reflect current impact")
        report.append("- Language restrictions may have excluded relevant non-English publications")
        report.append("")
        
        # Conclusion
        report.append("## Conclusion")
        report.append("")
        report.append(f"This systematic literature review successfully identified {total_papers:,} relevant papers ")
        report.append("using an automated pipeline that combines multiple databases and processing techniques. ")
        report.append("The results provide a comprehensive overview of the current state of research in the specified domain.")
        report.append("")
        
        # Appendix
        report.append("## Technical Details")
        report.append("")
        report.append("### Pipeline Metrics")
        report.append("")
        report.append("```json")
        report.append(str(self.metrics))
        report.append("```")
        report.append("")
        
        return "\n".join(report)
    
    def save_report(self, output_path: Path, format_type: str = "markdown") -> bool:
        """Save the report to file.
        
        Args:
            output_path: Path to save the report
            format_type: Format type ('markdown' or 'html')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if format_type.lower() == "markdown":
                report_text = self.generate_full_report()
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(report_text)
            
            elif format_type.lower() == "html":
                # Convert markdown to HTML (basic conversion)
                report_text = self.generate_full_report()
                html_content = self._markdown_to_html(report_text)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
            
            else:
                raise ValueError(f"Unsupported format: {format_type}")
            
            logger.info(f"Report saved to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving report: {e}")
            return False
    
    def _markdown_to_html(self, markdown_text: str) -> str:
        """Basic markdown to HTML conversion.
        
        Args:
            markdown_text: Markdown text
            
        Returns:
            HTML text
        """
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Literature Review Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1, h2, h3 {{ color: #333; }}
        pre {{ background-color: #f4f4f4; padding: 10px; border-radius: 5px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
<pre>
{markdown_text}
</pre>
</body>
</html>"""
        return html


def generate_report(
    df: pd.DataFrame,
    pipeline_metrics: Dict,
    query_info: Optional[Dict] = None,
    output_path: Optional[Path] = None,
    format_type: str = "markdown"
) -> bool:
    """Generate literature review report.
    
    Args:
        df: Final DataFrame of included papers
        pipeline_metrics: Metrics from pipeline execution
        query_info: Information about search queries and parameters
        output_path: Path to save report (defaults to outputs/report.md)
        format_type: Format type ('markdown' or 'html')
        
    Returns:
        True if successful, False otherwise
    """
    if output_path is None:
        ext = "md" if format_type.lower() == "markdown" else "html"
        output_path = config.outputs_dir / f"report.{ext}"
    
    generator = ReportGenerator()
    generator.set_data(df, pipeline_metrics, query_info)
    
    return generator.save_report(output_path, format_type)
