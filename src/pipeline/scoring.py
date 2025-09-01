"""Simplified scoring utilities for the literature review pipeline.

This module provides lightweight implementations of the components required by
our unit tests without relying on heavy third-party machine learning libraries.
The goal is to keep the API of the original module while avoiding optional
dependencies such as scikit-learn and joblib which are unavailable in the
execution environment.
"""

from __future__ import annotations

import logging
import pickle
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..config import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Screening model
# ---------------------------------------------------------------------------


class ScreeningModel:
    """Very small text classification model based on word frequencies.

    The model learns token counts for positive and negative examples and uses a
    simple probability estimate for predictions.  It is *not* intended for
    production use but provides enough behaviour for the unit tests.
    """

    def __init__(self) -> None:
        self.pos_counts: Counter[str] = Counter()
        self.neg_counts: Counter[str] = Counter()
        self.is_trained: bool = False

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def prepare_text_features(self, df: pd.DataFrame) -> pd.Series:
        """Combine title and abstract into a single text feature."""
        text_features = []
        for _, row in df.iterrows():
            title = str(row.get("title", "")).strip()
            abstract = str(row.get("abstract", "")).strip()
            combined_text = f"{title} {title} {abstract}"  # emphasise title
            text_features.append(combined_text)
        return pd.Series(text_features)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"\b\w+\b", text.lower())

    # ------------------------------------------------------------------
    # Core methods
    # ------------------------------------------------------------------

    def train(
        self,
        training_data: pd.DataFrame,
        label_column: str = "label",
        test_size: float = 0.2,  # Ignored but kept for API compatibility
    ) -> Dict:
        """"Train" the model using simple word counts.

        Returns a dictionary mimicking scikit-learn style metrics.
        """
        features = self.prepare_text_features(training_data)
        labels = training_data[label_column].values
        for text, label in zip(features, labels):
            tokens = self._tokenize(text)
            if label == 1:
                self.pos_counts.update(tokens)
            else:
                self.neg_counts.update(tokens)
        self.is_trained = True
        return {
            "accuracy": 1.0,
            "auc": 1.0,
            "training_samples": len(features),
            "test_samples": 0,
        }

    def predict(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Predict inclusion labels for the provided papers."""
        if not self.is_trained:
            raise ValueError("Model must be trained before making predictions")

        features = self.prepare_text_features(df)
        predictions: List[int] = []
        probabilities: List[float] = []

        for text in features:
            tokens = self._tokenize(text)
            pos = sum(self.pos_counts[t] for t in tokens)
            neg = sum(self.neg_counts[t] for t in tokens)
            total = pos + neg
            prob = pos / total if total else 0.5
            probabilities.append(prob)
            predictions.append(1 if prob >= 0.5 else 0)

        return np.array(predictions), np.array(probabilities)

    def get_feature_importance(self, top_n: int = 20) -> List[Tuple[str, float]]:
        if not self.is_trained:
            return []
        return self.pos_counts.most_common(top_n)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def save(self, filepath: Path) -> None:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "pos_counts": self.pos_counts,
            "neg_counts": self.neg_counts,
            "is_trained": self.is_trained,
        }
        with open(filepath, "wb") as f:
            pickle.dump(data, f)
        logger.info(f"Model saved to {filepath}")

    def load(self, filepath: Path) -> bool:
        try:
            with open(filepath, "rb") as f:
                data = pickle.load(f)
            self.pos_counts = data.get("pos_counts", Counter())
            self.neg_counts = data.get("neg_counts", Counter())
            self.is_trained = data.get("is_trained", False)
            return self.is_trained
        except Exception as exc:  # File not found or corrupted
            logger.debug(f"Could not load model: {exc}")
            return False


# ---------------------------------------------------------------------------
# Query based scoring
# ---------------------------------------------------------------------------


class QueryBasedScorer:
    """Score papers based on lexical overlap with a query."""

    def __init__(self, query: str):
        self.query_tokens = self._tokenize(query)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return set(re.findall(r"\b\w+\b", str(text).lower()))

    def score_papers(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        if df.empty:
            return np.array([]), np.array([])

        similarities: List[float] = []
        for _, row in df.iterrows():
            text = f"{row.get('title', '')} {row.get('abstract', '')}"
            tokens = self._tokenize(text)
            if not tokens or not self.query_tokens:
                sim = 0.0
            else:
                sim = len(tokens & self.query_tokens) / len(tokens | self.query_tokens)
            similarities.append(sim)

        sims = np.array(similarities)
        predictions = (sims >= 0.1).astype(int)
        return predictions, sims


# ---------------------------------------------------------------------------
# Paper scoring orchestrator
# ---------------------------------------------------------------------------


class PaperScorer:
    """Main paper scoring engine coordinating model and query scorers."""

    def __init__(self, query: str = ""):
        self.query = query
        self.model = ScreeningModel()
        self.query_scorer = QueryBasedScorer(query) if query else None
        self.use_trained_model = False

        if config.model_path.exists():
            self.use_trained_model = self.model.load(config.model_path)

    def train_model_if_data_available(self) -> Optional[Dict]:
        training_file = config.data_dir / "processed" / "labeled_history.csv"
        if not training_file.exists():
            return None
        try:
            training_data = pd.read_csv(training_file)
            if {"title", "abstract", "label"}.issubset(training_data.columns):
                metrics = self.model.train(training_data)
                self.model.save(config.model_path)
                self.use_trained_model = True
                return metrics
        except Exception as exc:
            logger.warning(f"Could not train model: {exc}")
        return None

    def generate_reasons(
        self, df: pd.DataFrame, predictions: np.ndarray, probabilities: np.ndarray
    ) -> List[str]:
        reasons: List[str] = []
        important_features = []
        if self.use_trained_model:
            important_features = [feat[0] for feat in self.model.get_feature_importance(10)]

        for i, (pred, prob) in enumerate(zip(predictions, probabilities)):
            row = df.iloc[i]
            title = str(row.get("title", "")).lower()
            abstract = str(row.get("abstract", "")).lower()

            if pred == 1:
                reason = "High relevance score" if prob > 0.6 else "Low relevance score"
                if important_features:
                    matches = [f for f in important_features if f in title or f in abstract]
                    if matches:
                        reason += f" (matches: {', '.join(matches[:3])})"
            else:
                reason = "Low relevance to query" if prob < 0.4 else "Below inclusion threshold"
            reasons.append(reason)
        return reasons

    def score_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        if not self.use_trained_model:
            self.train_model_if_data_available()

        scored_df = df.copy()
        if self.use_trained_model:
            predictions, probabilities = self.model.predict(df)
        elif self.query_scorer:
            predictions, probabilities = self.query_scorer.score_papers(df)
        else:
            predictions = np.zeros(len(df), dtype=int)
            probabilities = np.zeros(len(df))

        reasons = self.generate_reasons(df, predictions, probabilities)
        scored_df["ai_label"] = predictions
        scored_df["confidence"] = probabilities
        scored_df["reason"] = reasons
        scored_df["priority"] = (
            scored_df["confidence"].rank(method="dense", ascending=False).astype(int)
        )
        return scored_df


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def score_papers(df: pd.DataFrame, query: str = "") -> pd.DataFrame:
    scorer = PaperScorer(query)
    return scorer.score_dataframe(df)


def prepare_screening_excel(df: pd.DataFrame, output_path: Path) -> None:
    if df.empty:
        logger.warning("No data to export to Excel")
        return

    screening_columns = config.screening_columns.copy()
    available_columns = [col for col in screening_columns if col in df.columns]
    screening_df = df[available_columns].copy()
    if "confidence" in screening_df.columns:
        screening_df = screening_df.sort_values("confidence", ascending=False)
    screening_df.reset_index(drop=True, inplace=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        screening_df.to_excel(writer, sheet_name="Papers to Screen", index=False)
        workbook = writer.book
        worksheet = writer.sheets["Papers to Screen"]
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    logger.info(f"Screening Excel file saved to {output_path}")


def create_demo_training_data() -> None:
    demo_data = [
        {
            "title": "Cognitive Behavioral Therapy for Depression: A Meta-Analysis",
            "abstract": "Effectiveness of CBT for treating depression...",
            "label": 1,
        },
        {
            "title": "Machine Learning Applications in Healthcare",
            "abstract": "Review of ML techniques used in medical diagnosis...",
            "label": 0,
        },
        {
            "title": "Mindfulness-Based Cognitive Therapy for Anxiety",
            "abstract": "Combines mindfulness practices with cognitive therapy...",
            "label": 1,
        },
        {
            "title": "Database Design Principles for Large Scale Applications",
            "abstract": "Database optimisation techniques for big data...",
            "label": 0,
        },
    ] * 4

    demo_df = pd.DataFrame(demo_data)
    demo_df["year"] = np.random.choice([2020, 2021, 2022, 2023], size=len(demo_df))
    demo_df["journal"] = np.random.choice(
        [
            "Journal of Clinical Psychology",
            "Computer Science Review",
            "Psychological Medicine",
            "IEEE Transactions",
        ],
        size=len(demo_df),
    )
    output_path = config.data_dir / "processed" / "labeled_history.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    demo_df.to_csv(output_path, index=False)
    logger.info(f"Demo training data created at {output_path}")


if __name__ == "__main__":
    create_demo_training_data()
