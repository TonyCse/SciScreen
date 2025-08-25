"""Scoring module for the Literature Review Pipeline.

This module provides machine learning-based scoring and ranking
of papers for the screening process.
"""

import logging
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from ..config import config

logger = logging.getLogger(__name__)


class ScreeningModel:
    """Machine learning model for paper screening."""
    
    def __init__(self):
        """Initialize the screening model."""
        self.model = None
        self.vectorizer = None
        self.is_trained = False
        self.feature_names = []
        
        # Default model: TF-IDF + Logistic Regression
        self.pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(
                max_features=5000,
                stop_words='english',
                ngram_range=(1, 2),
                lowercase=True,
                strip_accents='unicode'
            )),
            ('classifier', LogisticRegression(
                random_state=42,
                max_iter=1000,
                class_weight='balanced'
            ))
        ])
    
    def prepare_text_features(self, df: pd.DataFrame) -> pd.Series:
        """Prepare text features for training/prediction.
        
        Args:
            df: DataFrame with paper data
            
        Returns:
            Series with combined text features
        """
        # Combine title and abstract
        text_features = []
        for _, row in df.iterrows():
            title = str(row.get('title', '')).strip()
            abstract = str(row.get('abstract', '')).strip()
            
            # Combine with more weight on title
            combined_text = f"{title} {title} {abstract}"
            text_features.append(combined_text)
        
        return pd.Series(text_features)
    
    def train(
        self,
        training_data: pd.DataFrame,
        label_column: str = 'label',
        test_size: float = 0.2
    ) -> Dict:
        """Train the screening model.
        
        Args:
            training_data: DataFrame with labeled training data
            label_column: Name of the label column (1=include, 0=exclude)
            test_size: Proportion of data to use for testing
            
        Returns:
            Dictionary with training metrics
        """
        logger.info(f"Training screening model with {len(training_data)} samples...")
        
        # Prepare features
        X = self.prepare_text_features(training_data)
        y = training_data[label_column]
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
        
        # Train model
        self.pipeline.fit(X_train, y_train)
        self.is_trained = True
        
        # Evaluate
        y_pred = self.pipeline.predict(X_test)
        y_prob = self.pipeline.predict_proba(X_test)[:, 1]
        
        metrics = {
            "accuracy": self.pipeline.score(X_test, y_test),
            "auc": roc_auc_score(y_test, y_prob),
            "classification_report": classification_report(y_test, y_pred, output_dict=True),
            "training_samples": len(X_train),
            "test_samples": len(X_test)
        }
        
        logger.info(f"Model trained - Accuracy: {metrics['accuracy']:.3f}, AUC: {metrics['auc']:.3f}")
        
        return metrics
    
    def predict(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Make predictions on new data.
        
        Args:
            df: DataFrame with papers to score
            
        Returns:
            Tuple of (predicted labels, prediction probabilities)
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before making predictions")
        
        X = self.prepare_text_features(df)
        
        predictions = self.pipeline.predict(X)
        probabilities = self.pipeline.predict_proba(X)[:, 1]
        
        return predictions, probabilities
    
    def get_feature_importance(self, top_n: int = 20) -> List[Tuple[str, float]]:
        """Get most important features from the trained model.
        
        Args:
            top_n: Number of top features to return
            
        Returns:
            List of (feature_name, importance) tuples
        """
        if not self.is_trained:
            return []
        
        # Get feature names and coefficients
        feature_names = self.pipeline['tfidf'].get_feature_names_out()
        coefficients = self.pipeline['classifier'].coef_[0]
        
        # Sort by absolute importance
        feature_importance = list(zip(feature_names, np.abs(coefficients)))
        feature_importance.sort(key=lambda x: x[1], reverse=True)
        
        return feature_importance[:top_n]
    
    def save(self, filepath: Path) -> None:
        """Save the trained model.
        
        Args:
            filepath: Path to save the model
        """
        if not self.is_trained:
            logger.warning("Attempting to save untrained model")
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.pipeline, filepath)
        logger.info(f"Model saved to {filepath}")
    
    def load(self, filepath: Path) -> bool:
        """Load a trained model.
        
        Args:
            filepath: Path to load the model from
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if filepath.exists():
                self.pipeline = joblib.load(filepath)
                self.is_trained = True
                logger.info(f"Model loaded from {filepath}")
                return True
            else:
                logger.warning(f"Model file not found: {filepath}")
                return False
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False


class QueryBasedScorer:
    """Fallback scorer using TF-IDF similarity to query."""
    
    def __init__(self, query: str):
        """Initialize with search query.
        
        Args:
            query: The search query to compare against
        """
        self.query = query.lower().strip()
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2),
            lowercase=True
        )
    
    def score_papers(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Score papers based on similarity to query.
        
        Args:
            df: DataFrame with papers to score
            
        Returns:
            Tuple of (binary predictions, similarity scores)
        """
        if df.empty:
            return np.array([]), np.array([])
        
        # Prepare text features
        paper_texts = []
        for _, row in df.iterrows():
            title = str(row.get('title', '')).strip()
            abstract = str(row.get('abstract', '')).strip()
            combined = f"{title} {abstract}"
            paper_texts.append(combined)
        
        # Add query to texts for fitting
        all_texts = [self.query] + paper_texts
        
        # Fit TF-IDF vectorizer
        tfidf_matrix = self.vectorizer.fit_transform(all_texts)
        
        # Calculate similarity to query (first document)
        query_vector = tfidf_matrix[0:1]
        paper_vectors = tfidf_matrix[1:]
        
        similarities = cosine_similarity(query_vector, paper_vectors).flatten()
        
        # Convert similarities to binary predictions using threshold
        threshold = config.confidence_threshold
        predictions = (similarities >= threshold).astype(int)
        
        return predictions, similarities


class PaperScorer:
    """Main paper scoring engine."""
    
    def __init__(self, query: str = ""):
        """Initialize the paper scorer.
        
        Args:
            query: Search query for fallback scoring
        """
        self.query = query
        self.model = ScreeningModel()
        self.query_scorer = QueryBasedScorer(query) if query else None
        self.use_trained_model = False
        
        # Try to load existing model
        if config.model_path.exists():
            self.use_trained_model = self.model.load(config.model_path)
    
    def train_model_if_data_available(self) -> Optional[Dict]:
        """Train model if training data is available.
        
        Returns:
            Training metrics if successful, None otherwise
        """
        # Look for training data
        training_file = config.data_dir / "processed" / "labeled_history.csv"
        
        if not training_file.exists():
            logger.info("No training data found, will use query-based scoring")
            return None
        
        try:
            training_data = pd.read_csv(training_file)
            
            # Check for required columns
            required_columns = ['title', 'abstract', 'label']
            missing_columns = [col for col in required_columns if col not in training_data.columns]
            
            if missing_columns:
                logger.warning(f"Training data missing columns: {missing_columns}")
                return None
            
            if len(training_data) < 10:
                logger.warning("Insufficient training data (< 10 samples)")
                return None
            
            # Train model
            metrics = self.model.train(training_data)
            
            # Save trained model
            self.model.save(config.model_path)
            self.use_trained_model = True
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error training model: {e}")
            return None
    
    def generate_reasons(
        self,
        df: pd.DataFrame,
        predictions: np.ndarray,
        probabilities: np.ndarray
    ) -> List[str]:
        """Generate human-readable reasons for predictions.
        
        Args:
            df: DataFrame with paper data
            predictions: Binary predictions
            probabilities: Prediction probabilities
            
        Returns:
            List of reason strings
        """
        reasons = []
        
        # Get important features if model is trained
        important_features = []
        if self.use_trained_model:
            important_features = [feat[0] for feat in self.model.get_feature_importance(10)]
        
        for i, (pred, prob) in enumerate(zip(predictions, probabilities)):
            row = df.iloc[i]
            title = str(row.get('title', '')).lower()
            abstract = str(row.get('abstract', '')).lower()
            
            # Generate reason based on prediction
            if pred == 1:  # Include
                if prob > 0.8:
                    reason = "High relevance score"
                elif prob > 0.6:
                    reason = "Moderate relevance score"
                else:
                    reason = "Low relevance score"
                
                # Add specific features if available
                if important_features:
                    matched_features = []
                    for feature in important_features[:3]:
                        if feature in title or feature in abstract:
                            matched_features.append(feature)
                    
                    if matched_features:
                        reason += f" (matches: {', '.join(matched_features)})"
            
            else:  # Exclude
                if prob < 0.2:
                    reason = "Low relevance to query"
                elif prob < 0.4:
                    reason = "Limited relevance"
                else:
                    reason = "Below inclusion threshold"
            
            reasons.append(reason)
        
        return reasons
    
    def score_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Score papers in a DataFrame.
        
        Args:
            df: DataFrame with papers to score
            
        Returns:
            DataFrame with added scoring columns
        """
        if df.empty:
            return df
        
        logger.info(f"Scoring {len(df)} papers...")
        
        # Try to train model if training data is available
        if not self.use_trained_model:
            training_metrics = self.train_model_if_data_available()
            if training_metrics:
                logger.info("Successfully trained model with available data")
        
        scored_df = df.copy()
        
        # Make predictions
        if self.use_trained_model:
            logger.info("Using trained ML model for scoring")
            predictions, probabilities = self.model.predict(df)
        elif self.query_scorer:
            logger.info("Using query-based scoring (no trained model)")
            predictions, probabilities = self.query_scorer.score_papers(df)
        else:
            logger.warning("No scoring method available, assigning random scores")
            predictions = np.random.choice([0, 1], size=len(df))
            probabilities = np.random.random(size=len(df))
        
        # Generate reasons
        reasons = self.generate_reasons(df, predictions, probabilities)
        
        # Add scoring columns
        scored_df['ai_label'] = predictions
        scored_df['confidence'] = probabilities
        scored_df['reason'] = reasons
        
        # Add priority ranking based on confidence
        scored_df['priority'] = scored_df['confidence'].rank(method='dense', ascending=False).astype(int)
        
        logger.info(f"Scoring completed: {predictions.sum()}/{len(df)} papers recommended for inclusion")
        
        return scored_df


def score_papers(df: pd.DataFrame, query: str = "") -> pd.DataFrame:
    """Convenience function to score papers.
    
    Args:
        df: DataFrame with papers to score
        query: Search query for scoring context
        
    Returns:
        DataFrame with scoring columns added
    """
    scorer = PaperScorer(query)
    return scorer.score_dataframe(df)


def prepare_screening_excel(df: pd.DataFrame, output_path: Path) -> None:
    """Prepare Excel file for manual screening.
    
    Args:
        df: Scored DataFrame
        output_path: Path to save Excel file
    """
    if df.empty:
        logger.warning("No data to export to Excel")
        return
    
    # Select and order columns for screening
    screening_columns = config.screening_columns.copy()
    
    # Only include columns that exist in the DataFrame
    available_columns = [col for col in screening_columns if col in df.columns]
    screening_df = df[available_columns].copy()
    
    # Sort by priority (highest confidence first)
    if 'confidence' in screening_df.columns:
        screening_df = screening_df.sort_values('confidence', ascending=False)
    
    # Reset index
    screening_df.reset_index(drop=True, inplace=True)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save to Excel with formatting
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        screening_df.to_excel(writer, sheet_name='Papers to Screen', index=False)
        
        # Get workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets['Papers to Screen']
        
        # Auto-adjust column widths
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            adjusted_width = min(max_length + 2, 50)  # Cap at 50
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    logger.info(f"Screening Excel file saved to {output_path}")


def create_demo_training_data() -> None:
    """Create demo training data for testing."""
    demo_data = [
        {
            "title": "Cognitive Behavioral Therapy for Depression: A Meta-Analysis",
            "abstract": "This meta-analysis examines the effectiveness of CBT for treating depression...",
            "label": 1
        },
        {
            "title": "Machine Learning Applications in Healthcare",
            "abstract": "This review covers various machine learning techniques used in medical diagnosis...",
            "label": 0
        },
        {
            "title": "Mindfulness-Based Cognitive Therapy for Anxiety and Depression",
            "abstract": "MBCT combines mindfulness practices with cognitive therapy approaches...",
            "label": 1
        },
        {
            "title": "Database Design Principles for Large Scale Applications",
            "abstract": "This paper discusses database optimization techniques for big data...",
            "label": 0
        },
        {
            "title": "Effectiveness of Psychotherapy vs Medication for Depression",
            "abstract": "Comparative study of psychotherapy and antidepressant medication effectiveness...",
            "label": 1
        },
    ] * 4  # Repeat to have 20 samples
    
    demo_df = pd.DataFrame(demo_data)
    
    # Add some variation
    demo_df['year'] = np.random.choice([2020, 2021, 2022, 2023], size=len(demo_df))
    demo_df['journal'] = np.random.choice([
        'Journal of Clinical Psychology',
        'Computer Science Review',
        'Psychological Medicine',
        'IEEE Transactions'
    ], size=len(demo_df))
    
    # Save to processed data directory
    output_path = config.data_dir / "processed" / "labeled_history.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    demo_df.to_csv(output_path, index=False)
    
    logger.info(f"Demo training data created at {output_path}")


if __name__ == "__main__":
    # Create demo training data when run directly
    create_demo_training_data()
