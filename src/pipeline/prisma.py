"""PRISMA diagram generation module for the Literature Review Pipeline.

This module creates PRISMA flow diagrams showing the paper selection process
according to PRISMA 2020 guidelines.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch

from ..config import config

logger = logging.getLogger(__name__)


class PRISMAGenerator:
    """Generator for PRISMA flow diagrams."""
    
    def __init__(self):
        """Initialize PRISMA generator."""
        self.metrics = {}
        self.fig = None
        self.ax = None
        
        # PRISMA box styling
        self.box_style = {
            'boxstyle': 'round,pad=0.5',
            'facecolor': 'lightblue',
            'edgecolor': 'black',
            'linewidth': 1.5
        }
        
        self.excluded_box_style = {
            'boxstyle': 'round,pad=0.5',
            'facecolor': 'lightcoral',
            'edgecolor': 'black',
            'linewidth': 1.5
        }
        
        self.text_style = {
            'ha': 'center',
            'va': 'center',
            'fontsize': 10,
            'weight': 'bold'
        }
    
    def set_metrics(self, pipeline_metrics: Dict) -> None:
        """Set metrics from pipeline execution.
        
        Args:
            pipeline_metrics: Dictionary containing metrics from each pipeline stage
        """
        self.metrics = pipeline_metrics.copy()
        logger.info(f"PRISMA metrics set: {self.metrics}")
    
    def calculate_flow_numbers(self) -> Dict[str, int]:
        """Calculate numbers for each step of the PRISMA flow.
        
        Returns:
            Dictionary with calculated flow numbers
        """
        flow = {}
        
        # Identification
        flow['openalex_identified'] = self.metrics.get('harvest', {}).get('openalex', 0)
        flow['crossref_identified'] = self.metrics.get('harvest', {}).get('crossref', 0)
        flow['pubmed_identified'] = self.metrics.get('harvest', {}).get('pubmed', 0)
        flow['total_identified'] = flow['openalex_identified'] + flow['crossref_identified'] + flow['pubmed_identified']
        
        # After merging sources
        flow['after_merge'] = self.metrics.get('normalize', {}).get('final_count', flow['total_identified'])
        
        # Deduplication
        dedup_metrics = self.metrics.get('deduplicate', {})
        flow['duplicates_removed'] = dedup_metrics.get('exact_duplicates_removed', 0) + dedup_metrics.get('fuzzy_duplicates_removed', 0)
        flow['after_deduplication'] = dedup_metrics.get('final_count', flow['after_merge'])
        
        # Filtering
        filter_metrics = self.metrics.get('filter', {})
        flow['excluded_by_rules'] = sum(filter_metrics.get('excluded_by_rule', {}).values())
        flow['after_filtering'] = filter_metrics.get('final_count', flow['after_deduplication'])
        
        # Screening (manual decisions)
        screening_metrics = self.metrics.get('screening', {})
        flow['screened'] = screening_metrics.get('total_screened', flow['after_filtering'])
        flow['excluded_by_screening'] = screening_metrics.get('excluded_count', 0)
        flow['included_after_screening'] = screening_metrics.get('included_count', flow['after_filtering'])
        
        # Final inclusion
        flow['final_included'] = self.metrics.get('final_included', flow['included_after_screening'])
        
        return flow
    
    def create_prisma_diagram(self, output_path: Path, title: str = "PRISMA Flow Diagram") -> bool:
        """Create PRISMA flow diagram.
        
        Args:
            output_path: Path to save the diagram
            title: Title for the diagram
            
        Returns:
            True if successful, False otherwise
        """
        try:
            flow = self.calculate_flow_numbers()
            
            # Create figure
            self.fig, self.ax = plt.subplots(1, 1, figsize=(12, 16))
            self.ax.set_xlim(0, 10)
            self.ax.set_ylim(0, 20)
            self.ax.axis('off')
            
            # Title
            self.ax.text(5, 19, title, ha='center', va='center', fontsize=16, weight='bold')
            
            # Identification section
            self._add_section_header(5, 17.5, "Identification")
            
            # Individual sources
            self._add_box(2, 16.5, f"OpenAlex\n(n = {flow['openalex_identified']:,})")
            self._add_box(5, 16.5, f"Crossref\n(n = {flow['crossref_identified']:,})")
            self._add_box(8, 16.5, f"PubMed\n(n = {flow['pubmed_identified']:,})")
            
            # Total identified
            self._add_box(5, 15, f"Records identified through\ndatabase searching\n(n = {flow['total_identified']:,})")
            
            # Arrows from sources to total
            self._add_arrow(2, 16, 4.2, 15.5)
            self._add_arrow(5, 16, 5, 15.5)
            self._add_arrow(8, 16, 5.8, 15.5)
            
            # Screening section
            self._add_section_header(5, 13.5, "Screening")
            
            # After merge
            self._add_box(5, 12.5, f"Records after merging\n(n = {flow['after_merge']:,})")
            self._add_arrow(5, 14.5, 5, 13)
            
            # Duplicates removed
            if flow['duplicates_removed'] > 0:
                self._add_excluded_box(8.5, 11.5, f"Duplicates removed\n(n = {flow['duplicates_removed']:,})")
                self._add_arrow(6, 12.5, 8, 11.8, style='dashed')
            
            # After deduplication
            self._add_box(5, 11, f"Records screened\n(n = {flow['after_deduplication']:,})")
            self._add_arrow(5, 12, 5, 11.5)
            
            # Excluded by rules
            if flow['excluded_by_rules'] > 0:
                self._add_excluded_box(8.5, 10, f"Records excluded by\nautomated rules\n(n = {flow['excluded_by_rules']:,})")
                self._add_arrow(6, 11, 8, 10.3, style='dashed')
            
            # Eligibility section
            self._add_section_header(5, 9, "Eligibility")
            
            # After filtering
            self._add_box(5, 8, f"Records assessed\nfor eligibility\n(n = {flow['after_filtering']:,})")
            self._add_arrow(5, 10.5, 5, 8.5)
            
            # Excluded by screening
            if flow['excluded_by_screening'] > 0:
                self._add_excluded_box(8.5, 7, f"Records excluded after\nmanual screening\n(n = {flow['excluded_by_screening']:,})")
                self._add_arrow(6, 8, 8, 7.3, style='dashed')
            
            # Included section
            self._add_section_header(5, 6, "Included")
            
            # Final included
            self._add_box(5, 5, f"Studies included in\nliterature review\n(n = {flow['final_included']:,})", 
                         style='success')
            self._add_arrow(5, 7.5, 5, 5.5)
            
            # Add date
            self.ax.text(9, 0.5, f"Generated: {config.project_name}\n{output_path.name}", 
                        ha='right', va='bottom', fontsize=8, style='italic')
            
            # Save figure
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=300, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            
            logger.info(f"PRISMA diagram saved to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating PRISMA diagram: {e}")
            return False
        finally:
            if self.fig:
                plt.close(self.fig)
    
    def _add_section_header(self, x: float, y: float, text: str) -> None:
        """Add section header text.
        
        Args:
            x: X coordinate
            y: Y coordinate  
            text: Header text
        """
        self.ax.text(x, y, text, ha='center', va='center', 
                    fontsize=14, weight='bold', style='italic')
    
    def _add_box(self, x: float, y: float, text: str, style: str = 'normal') -> None:
        """Add a box to the diagram.
        
        Args:
            x: X coordinate of box center
            y: Y coordinate of box center
            text: Text to display in box
            style: Box style ('normal', 'excluded', 'success')
        """
        # Choose style
        if style == 'excluded':
            box_style = self.excluded_box_style
        elif style == 'success':
            box_style = self.box_style.copy()
            box_style['facecolor'] = 'lightgreen'
        else:
            box_style = self.box_style
        
        # Create box
        bbox = FancyBboxPatch((x-1.2, y-0.4), 2.4, 0.8, **box_style)
        self.ax.add_patch(bbox)
        
        # Add text
        self.ax.text(x, y, text, **self.text_style)
    
    def _add_excluded_box(self, x: float, y: float, text: str) -> None:
        """Add an exclusion box.
        
        Args:
            x: X coordinate of box center
            y: Y coordinate of box center
            text: Text to display in box
        """
        self._add_box(x, y, text, style='excluded')
    
    def _add_arrow(self, x1: float, y1: float, x2: float, y2: float, style: str = 'solid') -> None:
        """Add arrow between points.
        
        Args:
            x1: Start X coordinate
            y1: Start Y coordinate
            x2: End X coordinate
            y2: End Y coordinate
            style: Arrow style ('solid' or 'dashed')
        """
        if style == 'dashed':
            linestyle = '--'
            color = 'red'
        else:
            linestyle = '-'
            color = 'black'
        
        self.ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                        arrowprops=dict(arrowstyle='->', lw=1.5, 
                                      color=color, linestyle=linestyle))
    
    def generate_prisma_text_summary(self) -> str:
        """Generate text summary of PRISMA flow.
        
        Returns:
            Text summary of the selection process
        """
        flow = self.calculate_flow_numbers()
        
        summary = []
        summary.append("PRISMA Flow Summary")
        summary.append("=" * 20)
        summary.append("")
        
        summary.append("Identification:")
        summary.append(f"  - OpenAlex: {flow['openalex_identified']:,} records")
        summary.append(f"  - Crossref: {flow['crossref_identified']:,} records")
        summary.append(f"  - PubMed: {flow['pubmed_identified']:,} records")
        summary.append(f"  - Total identified: {flow['total_identified']:,} records")
        summary.append("")
        
        summary.append("Screening:")
        summary.append(f"  - After merging sources: {flow['after_merge']:,} records")
        if flow['duplicates_removed'] > 0:
            summary.append(f"  - Duplicates removed: {flow['duplicates_removed']:,} records")
        summary.append(f"  - After deduplication: {flow['after_deduplication']:,} records")
        if flow['excluded_by_rules'] > 0:
            summary.append(f"  - Excluded by automated rules: {flow['excluded_by_rules']:,} records")
        summary.append(f"  - Available for manual screening: {flow['after_filtering']:,} records")
        summary.append("")
        
        summary.append("Eligibility:")
        if flow['excluded_by_screening'] > 0:
            summary.append(f"  - Excluded after manual screening: {flow['excluded_by_screening']:,} records")
        summary.append(f"  - Final included studies: {flow['final_included']:,} records")
        
        # Calculate percentages
        if flow['total_identified'] > 0:
            final_percentage = (flow['final_included'] / flow['total_identified']) * 100
            summary.append("")
            summary.append(f"Overall inclusion rate: {final_percentage:.1f}% ({flow['final_included']:,}/{flow['total_identified']:,})")
        
        return "\n".join(summary)


def generate_prisma_diagram(
    pipeline_metrics: Dict,
    output_path: Optional[Path] = None,
    title: str = "PRISMA Flow Diagram"
) -> bool:
    """Generate PRISMA flow diagram.
    
    Args:
        pipeline_metrics: Metrics from pipeline execution
        output_path: Path to save diagram (defaults to outputs/prisma.png)
        title: Title for the diagram
        
    Returns:
        True if successful, False otherwise
    """
    if output_path is None:
        output_path = config.outputs_dir / "prisma.png"
    
    generator = PRISMAGenerator()
    generator.set_metrics(pipeline_metrics)
    
    return generator.create_prisma_diagram(output_path, title)


def generate_prisma_summary(pipeline_metrics: Dict) -> str:
    """Generate PRISMA text summary.
    
    Args:
        pipeline_metrics: Metrics from pipeline execution
        
    Returns:
        Text summary of the selection process
    """
    generator = PRISMAGenerator()
    generator.set_metrics(pipeline_metrics)
    
    return generator.generate_prisma_text_summary()
