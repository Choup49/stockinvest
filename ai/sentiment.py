"""
Analyse de sentiment pour StockInvest Pro.

Combine sentiment textuel (news, via HuggingFace local par défaut) et
signaux volume/prix pour produire un score de sentiment global.
"""

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd

from utils.logger import logger


@dataclass
class SentimentResult:
    """Résultat d'analyse de sentiment pour un ticker."""

    ticker: str
    text_sentiment_score: float | None  # -1 (négatif) à +1 (positif), None si pas de news
    price_volume_signal: float  # -1 à +1, dérivé du comportement marché
    global_sentiment: float  # -1 à +1, moyenne pondérée
    label: str  # "Positif" / "Neutre" / "Négatif"
    n_headlines_analyzed: int


class SentimentAnalyzer:
    """
    Analyseur de sentiment hybride : NLP sur les news + signal quantitatif
    volume/prix. Le modèle HuggingFace est chargé paresseusement (lazy)
    pour ne pas alourdir le démarrage de l'app si l'utilisateur n'ouvre
    jamais l'onglet sentiment.
    """

    def __init__(self, model_name: str = "distilbert-base-uncased-finetuned-sst-2-english") -> None:
        self.model_name = model_name
        self._pipeline = None

    @property
    def pipeline(self):
        """Charge le pipeline HuggingFace à la première utilisation."""
        if self._pipeline is None:
            from transformers import pipeline as hf_pipeline

            logger.info(f"Chargement du modèle de sentiment: {self.model_name}")
            self._pipeline = hf_pipeline("sentiment-analysis", model=self.model_name)
        return self._pipeline

    def analyze(self, ticker: str, headlines: list[str], price_df: pd.DataFrame) -> SentimentResult:
        """
        Args:
            headlines: titres de news récents pour ce ticker (peut être vide).
            price_df: DataFrame OHLCV nettoyé, utilisé pour le signal volume/prix.
        """
        text_score = self._analyze_headlines(headlines) if headlines else None
        pv_signal = self._price_volume_signal(price_df)

        if text_score is not None:
            global_sentiment = 0.6 * text_score + 0.4 * pv_signal
        else:
            global_sentiment = pv_signal

        return SentimentResult(
            ticker=ticker,
            text_sentiment_score=text_score,
            price_volume_signal=pv_signal,
            global_sentiment=round(float(global_sentiment), 3),
            label=self._to_label(global_sentiment),
            n_headlines_analyzed=len(headlines),
        )

    def _analyze_headlines(self, headlines: list[str]) -> float:
        """Moyenne des scores de sentiment sur les titres, dans [-1, 1]."""
        results = self.pipeline(headlines, truncation=True)
        scores = []
        for r in results:
            sign = 1.0 if r["label"].upper() == "POSITIVE" else -1.0
            scores.append(sign * float(r["score"]))
        return float(np.mean(scores)) if scores else 0.0

    def _price_volume_signal(self, df: pd.DataFrame) -> float:
        """
        Signal dérivé du comportement récent : combinaison de la tendance
        de prix sur 20j et de l'anomalie de volume, normalisé dans [-1, 1].
        """
        if df.empty or len(df) < 20:
            return 0.0

        recent = df.tail(20)
        price_trend = recent["Adj Close"].iloc[-1] / recent["Adj Close"].iloc[0] - 1
        price_signal = float(np.clip(price_trend * 5, -1, 1))  # échelle empirique

        avg_volume = recent["Volume"].mean()
        last_volume = recent["Volume"].iloc[-1]
        volume_ratio = (last_volume / avg_volume) if avg_volume > 0 else 1.0
        volume_signal = float(np.clip((volume_ratio - 1), -1, 1))

        return float(np.clip(0.7 * price_signal + 0.3 * volume_signal, -1, 1))

    @staticmethod
    def _to_label(score: float) -> str:
        if score > 0.15:
            return "Positif"
        if score < -0.15:
            return "Négatif"
        return "Neutre"
