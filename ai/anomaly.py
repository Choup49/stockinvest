"""
Détection d'anomalies (volume inhabituel, mouvement inhabituel, rupture
comportementale) via Isolation Forest.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from core.exceptions import InsufficientDataError
from utils.logger import logger


@dataclass
class AnomalyPoint:
    """Une anomalie détectée à une date donnée."""

    date: pd.Timestamp
    anomaly_score: float  # plus négatif = plus anormal
    volume_zscore: float
    return_zscore: float
    reason: str


class AnomalyDetector:
    """
    Détecte les comportements anormaux (volume/prix) via Isolation Forest
    entraîné sur les features dérivées du prix et du volume.
    """

    def __init__(self, contamination: float = 0.05, random_state: int = 42) -> None:
        self.contamination = contamination
        self.random_state = random_state

    def detect(self, ticker: str, df: pd.DataFrame, window: int = 20) -> list[AnomalyPoint]:
        """
        Args:
            df: DataFrame OHLCV nettoyé.
            window: fenêtre rolling utilisée pour calculer les z-scores locaux.

        Returns:
            Liste des points identifiés comme anomalies (label == -1 par IsolationForest),
            triée par score d'anomalie croissant (plus anormal en premier).
        """
        if len(df) < window * 2:
            raise InsufficientDataError(ticker, required=window * 2, available=len(df))

        features = self._build_features(df, window)
        clean_features = features.dropna()

        if len(clean_features) < 10:
            logger.warning(f"{ticker}: pas assez de points post-nettoyage pour la détection d'anomalies")
            return []

        model = IsolationForest(
            contamination=self.contamination, random_state=self.random_state, n_estimators=200
        )
        labels = model.fit_predict(clean_features)
        scores = model.decision_function(clean_features)

        anomalies: list[AnomalyPoint] = []
        for idx, (date, label, score) in enumerate(zip(clean_features.index, labels, scores)):
            if label == -1:
                row = clean_features.iloc[idx]
                anomalies.append(
                    AnomalyPoint(
                        date=date,
                        anomaly_score=float(score),
                        volume_zscore=float(row["volume_zscore"]),
                        return_zscore=float(row["return_zscore"]),
                        reason=self._explain(row),
                    )
                )

        anomalies.sort(key=lambda a: a.anomaly_score)
        logger.info(f"{ticker}: {len(anomalies)} anomalies détectées sur {len(clean_features)} points")
        return anomalies

    def _build_features(self, df: pd.DataFrame, window: int) -> pd.DataFrame:
        """Construit les features locales (volume/rendement en z-score glissant) pour IF."""
        returns = df["Adj Close"].pct_change()
        volume = df["Volume"]

        return_zscore = (returns - returns.rolling(window).mean()) / returns.rolling(window).std()
        volume_zscore = (volume - volume.rolling(window).mean()) / volume.rolling(window).std()

        return pd.DataFrame(
            {
                "return_zscore": return_zscore,
                "volume_zscore": volume_zscore,
                "abs_return": returns.abs(),
            }
        )

    def _explain(self, row: pd.Series) -> str:
        parts = []
        if abs(row["volume_zscore"]) > 2:
            parts.append("volume inhabituel")
        if abs(row["return_zscore"]) > 2:
            parts.append("mouvement de prix inhabituel")
        if not parts:
            parts.append("rupture comportementale détectée par le modèle")
        return " + ".join(parts)
