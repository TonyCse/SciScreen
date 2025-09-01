"""Deduplication module for the Literature Review Pipeline.

This module provides functions to identify and remove duplicate papers
using various strategies including exact DOI/PMID matching and fuzzy
title matching.
"""

import logging
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

import pandas as pd

from ..config import config

logger = logging.getLogger(__name__)


class Deduplicator:
    """Deduplication engine for academic works."""
    
    def __init__(self):
        """Initialize the deduplicator."""
        self.title_threshold = config.title_similarity_threshold
        self.levenshtein_threshold = config.levenshtein_threshold
        self.year_tolerance = config.year_tolerance
        
        # Track deduplication metrics
        self.metrics = {
            "total_input": 0,
            "exact_duplicates_removed": 0,
            "fuzzy_duplicates_removed": 0,
            "final_count": 0,
            "duplicate_groups": []
        }
    
    def find_exact_duplicates(self, df: pd.DataFrame) -> Dict[str, List[int]]:
        """Find exact duplicates based on DOI/PMID/PMCID.
        
        Args:
            df: DataFrame to search for duplicates
            
        Returns:
            Dictionary mapping identifier to list of row indices
        """
        duplicate_groups = {}
        
        # Check DOI duplicates
        if 'doi' in df.columns:
            doi_groups = df[df['doi'].notna() & (df['doi'] != "")].groupby('doi').groups
            for doi, indices in doi_groups.items():
                if len(indices) > 1:
                    duplicate_groups[f"doi:{doi}"] = indices.tolist()
        
        # Check PMID duplicates
        if 'pmid' in df.columns:
            pmid_groups = df[df['pmid'].notna() & (df['pmid'] != "")].groupby('pmid').groups
            for pmid, indices in pmid_groups.items():
                if len(indices) > 1:
                    duplicate_groups[f"pmid:{pmid}"] = indices.tolist()
        
        # Check ID duplicates (for same source)
        if 'id' in df.columns and 'source' in df.columns:
            for source in df['source'].unique():
                source_df = df[df['source'] == source]
                id_groups = source_df[source_df['id'].notna() & (source_df['id'] != "")].groupby('id').groups
                for id_val, indices in id_groups.items():
                    if len(indices) > 1:
                        duplicate_groups[f"id:{source}:{id_val}"] = indices.tolist()
        
        return duplicate_groups
    
    def choose_best_duplicate(self, df: pd.DataFrame, indices: List[int]) -> int:
        """Choose the best entry from a group of duplicates.
        
        Priority:
        1. Has PDF URL
        2. Longest abstract
        3. Highest citation count
        4. Most complete metadata
        
        Args:
            df: DataFrame containing the duplicates
            indices: List of row indices of duplicates
            
        Returns:
            Index of the best duplicate to keep
        """
        duplicates = df.loc[indices].copy()
        
        # Score each duplicate
        scores = []
        for idx in indices:
            row = df.loc[idx]
            score = 0
            
            # PDF URL bonus
            if row.get('pdf_url', '') != "":
                score += 100
            
            # Abstract length bonus
            abstract_len = len(str(row.get('abstract', '')))
            score += min(abstract_len / 10, 50)  # Cap at 50 points
            
            # Citation count bonus
            cited_by = row.get('cited_by', 0) or 0
            score += min(cited_by / 10, 30)  # Cap at 30 points
            
            # Completeness bonus
            complete_fields = sum([
                1 for field in ['title', 'authors', 'journal', 'year', 'doi']
                if row.get(field, '') not in ['', None]
            ])
            score += complete_fields * 5
            
            scores.append(score)
        
        # Return index with highest score
        best_idx = indices[scores.index(max(scores))]
        return best_idx
    
    def remove_exact_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove exact duplicates and return deduplicated DataFrame.
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with exact duplicates removed
        """
        logger.info("Finding exact duplicates...")
        
        duplicate_groups = self.find_exact_duplicates(df)
        
        if not duplicate_groups:
            logger.info("No exact duplicates found")
            return df
        
        logger.info(f"Found {len(duplicate_groups)} groups of exact duplicates")
        
        # Track which indices to remove
        indices_to_remove = set()
        
        for identifier, indices in duplicate_groups.items():
            # Choose best duplicate to keep
            best_idx = self.choose_best_duplicate(df, indices)
            
            # Mark others for removal
            for idx in indices:
                if idx != best_idx:
                    indices_to_remove.add(idx)
            
            # Track metrics
            self.metrics["duplicate_groups"].append({
                "type": "exact",
                "identifier": identifier,
                "count": len(indices),
                "kept_index": best_idx,
                "removed_indices": [idx for idx in indices if idx != best_idx]
            })
        
        # Remove duplicates
        cleaned_df = df.drop(indices_to_remove).reset_index(drop=True)
        
        removed_count = len(indices_to_remove)
        self.metrics["exact_duplicates_removed"] = removed_count
        
        logger.info(f"Removed {removed_count} exact duplicates, {len(cleaned_df)} papers remaining")
        
        return cleaned_df
    
    def create_title_blocks(self, df: pd.DataFrame) -> Dict[str, List[int]]:
        """Create blocking strategy for efficient fuzzy matching.
        
        Uses first 3 words of normalized title as blocks.
        
        Args:
            df: DataFrame with normalized titles
            
        Returns:
            Dictionary mapping block keys to list of indices
        """
        blocks = {}
        
        for idx, row in df.iterrows():
            title_norm = row.get('title_normalized', '').strip()
            if not title_norm:
                continue

            # Create block key from the first two words to allow small variations
            # (e.g. singular/plural differences) to still fall into the same block.
            words = title_norm.split()[:2]
            if len(words) >= 2:  # Require at least 2 words
                block_key = ' '.join(words)
                blocks.setdefault(block_key, []).append(idx)
        
        # Only keep blocks with multiple items
        return {k: v for k, v in blocks.items() if len(v) > 1}
    
    def are_titles_similar(
        self,
        title1: str,
        title2: str,
        year1: any,
        year2: any
    ) -> bool:
        """Check if two titles are similar enough to be duplicates.
        
        Args:
            title1: First normalized title
            title2: Second normalized title
            year1: First publication year
            year2: Second publication year
            
        Returns:
            True if titles are considered similar
        """
        if not title1 or not title2:
            return False
        
        # Check year compatibility
        if year1 and year2:
            try:
                year_diff = abs(int(year1) - int(year2))
                if year_diff > self.year_tolerance:
                    return False
            except (ValueError, TypeError):
                pass
        
        # Calculate similarity
        ratio = int(SequenceMatcher(None, title1, title2).ratio() * 100)
        
        # Use different thresholds based on title length
        if len(title1) < 30 or len(title2) < 30:
            # Stricter threshold for short titles
            threshold = 90
        else:
            # Standard threshold for longer titles
            threshold = self.title_threshold * 100
        
        return ratio >= threshold
    
    def find_fuzzy_duplicates(self, df: pd.DataFrame) -> Dict[str, List[int]]:
        """Find fuzzy duplicates based on title similarity.
        
        Args:
            df: DataFrame to search for fuzzy duplicates
            
        Returns:
            Dictionary mapping group identifier to list of indices
        """
        logger.info("Finding fuzzy duplicates...")
        
        if 'title_normalized' not in df.columns:
            logger.warning("No normalized titles found, skipping fuzzy deduplication")
            return {}
        
        # Create blocks for efficient comparison
        blocks = self.create_title_blocks(df)
        
        if not blocks:
            logger.info("No title blocks created, no fuzzy duplicates found")
            return {}
        
        duplicate_groups = {}
        group_counter = 0
        
        for block_key, indices in blocks.items():
            logger.debug(f"Processing block '{block_key}' with {len(indices)} papers")
            
            # Compare all pairs within this block
            for i, idx1 in enumerate(indices):
                for idx2 in indices[i+1:]:
                    row1 = df.loc[idx1]
                    row2 = df.loc[idx2]
                    
                    title1 = row1.get('title_normalized', '')
                    title2 = row2.get('title_normalized', '')
                    year1 = row1.get('year')
                    year2 = row2.get('year')
                    
                    if self.are_titles_similar(title1, title2, year1, year2):
                        # Find existing group or create new one
                        existing_group = None
                        for group_id, group_indices in duplicate_groups.items():
                            if idx1 in group_indices or idx2 in group_indices:
                                existing_group = group_id
                                break
                        
                        if existing_group:
                            # Add to existing group
                            duplicate_groups[existing_group].extend([idx1, idx2])
                            duplicate_groups[existing_group] = list(set(duplicate_groups[existing_group]))
                        else:
                            # Create new group
                            group_counter += 1
                            duplicate_groups[f"fuzzy_group_{group_counter}"] = [idx1, idx2]
        
        logger.info(f"Found {len(duplicate_groups)} groups of fuzzy duplicates")
        return duplicate_groups
    
    def remove_fuzzy_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove fuzzy duplicates and return deduplicated DataFrame.
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with fuzzy duplicates removed
        """
        duplicate_groups = self.find_fuzzy_duplicates(df)
        
        if not duplicate_groups:
            logger.info("No fuzzy duplicates found")
            return df
        
        # Track which indices to remove
        indices_to_remove = set()
        
        for group_id, indices in duplicate_groups.items():
            # Choose best duplicate to keep
            best_idx = self.choose_best_duplicate(df, indices)
            
            # Mark others for removal
            for idx in indices:
                if idx != best_idx:
                    indices_to_remove.add(idx)
            
            # Track metrics
            self.metrics["duplicate_groups"].append({
                "type": "fuzzy",
                "identifier": group_id,
                "count": len(indices),
                "kept_index": best_idx,
                "removed_indices": [idx for idx in indices if idx != best_idx]
            })
        
        # Remove duplicates
        cleaned_df = df.drop(indices_to_remove).reset_index(drop=True)
        
        removed_count = len(indices_to_remove)
        self.metrics["fuzzy_duplicates_removed"] = removed_count
        
        logger.info(f"Removed {removed_count} fuzzy duplicates, {len(cleaned_df)} papers remaining")
        
        return cleaned_df
    
    def deduplicate(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """Perform complete deduplication process.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Tuple of (deduplicated DataFrame, metrics dictionary)
        """
        logger.info(f"Starting deduplication of {len(df)} papers...")
        
        self.metrics["total_input"] = len(df)
        
        if df.empty:
            self.metrics["final_count"] = 0
            return df, self.metrics
        
        # Step 1: Remove exact duplicates
        df_no_exact = self.remove_exact_duplicates(df)
        
        # Step 2: Remove fuzzy duplicates
        df_deduplicated = self.remove_fuzzy_duplicates(df_no_exact)
        
        self.metrics["final_count"] = len(df_deduplicated)
        
        # Log summary
        total_removed = self.metrics["exact_duplicates_removed"] + self.metrics["fuzzy_duplicates_removed"]
        removal_rate = (total_removed / self.metrics["total_input"]) * 100 if self.metrics["total_input"] > 0 else 0
        
        logger.info(
            f"Deduplication completed: {self.metrics['total_input']} → {self.metrics['final_count']} papers "
            f"({total_removed} removed, {removal_rate:.1f}% reduction)"
        )
        
        return df_deduplicated, self.metrics


def deduplicate_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """Convenience function to deduplicate a DataFrame.
    
    Args:
        df: DataFrame to deduplicate
        
    Returns:
        Tuple of (deduplicated DataFrame, metrics dictionary)
    """
    deduplicator = Deduplicator()
    return deduplicator.deduplicate(df)


def get_deduplication_report(metrics: Dict) -> str:
    """Generate a human-readable deduplication report.
    
    Args:
        metrics: Deduplication metrics dictionary
        
    Returns:
        Formatted report string
    """
    report = []
    report.append("Deduplication Report")
    report.append("=" * 20)
    report.append(f"Input papers: {metrics['total_input']}")
    report.append(f"Exact duplicates removed: {metrics['exact_duplicates_removed']}")
    report.append(f"Fuzzy duplicates removed: {metrics['fuzzy_duplicates_removed']}")
    report.append(f"Final count: {metrics['final_count']}")
    
    total_removed = metrics['exact_duplicates_removed'] + metrics['fuzzy_duplicates_removed']
    if metrics['total_input'] > 0:
        removal_rate = (total_removed / metrics['total_input']) * 100
        report.append(f"Reduction rate: {removal_rate:.1f}%")
    
    return "\n".join(report)
