"""
Extraction des valeurs brutes des 6 facteurs quantitatifs à partir
d'un DataFrame enrichi (features.py) et d'un snapshot fondamental.

Ce module ne fait AUCUNE normalisation — il extrait uniquement les
valeurs brutes. La normalisation (winsorization, z-score, comparaison
sectorielle) est faite dans quant/normalizer.py.
"""

from dataclasses import dataclass

import pandas as pd

from core.enums import FactorType
from utils.logger import logger


@dataclass
class RawFactorValues:
    """Valeurs brutes des 6 facteurs pour un ticker, avant normalisation."""

    ticker: str
    value: dict[str, float | None]
    growth: dict[str, float | None]
    quality: dict[str, float | None]
    momentum: dict[str, float | None]
    risk: dict[str, float | None]
    technical: dict[str, float | None]


class FactorExtractor:
    """Extrait les valeurs brutes des 6 facteurs pour un ticker donné."""

    def extract(
        self, ticker: str, features_df: pd.DataFrame, fundamentals: dict[str, float | None]
    ) -> RawFactorValues:
        """
        Args:
            features_df: DataFrame enrichi par FeatureEngineer.compute_all,
                on utilise la dernière ligne (données les plus récentes).
            fundamentals: dict retourné par FundamentalFeatureEngineer.compute.
        """
        if features_df.empty:
            raise ValueError(f"features_df vide pour {ticker}, impossible d'extraire les facteurs")

        last = features_df.iloc[-1]

        return RawFactorValues(
            ticker=ticker,
            value=self._extract_value(fundamentals),
            growth=self._extract_growth(fundamentals),
            quality=self._extract_quality(fundamentals),
            momentum=self._extract_momentum(last),
            risk=self._extract_risk(last),
            technical=self._extract_technical(last),
        )

    def _extract_value(self, f: dict) -> dict[str, float | None]:
        per = f.get("per")
        fcf_yield = f.get("fcf_yield")
        return {
            # PER inversé : un PER faible = bon signal Value -> on stocke 1/PER
            "inverse_per": (1 / per) if per and per > 0 else None,
            "fcf_yield": fcf_yield,
        }

    def _extract_growth(self, f: dict) -> dict[str, float | None]:
        return {
            "revenue_growth": f.get("revenue_growth"),
        }

    def _extract_quality(self, f: dict) -> dict[str, float | None]:
        return {
            "roe": f.get("roe"),
            "profit_margin": f.get("profit_margin"),
        }

    def _extract_momentum(self, last_row: pd.Series) -> dict[str, float | None]:
        return {
            "momentum_3m": self._safe(last_row, "momentum_3m"),
            "momentum_6m": self._safe(last_row, "momentum_6m"),
            "momentum_12m": self._safe(last_row, "momentum_12m"),
        }

    def _extract_risk(self, last_row: pd.Series) -> dict[str, float | None]:
        vol = self._safe(last_row, "volatility_60d")
        beta = self._safe(last_row, "beta")
        return {
            # Risk : volatilité et beta faibles = bon signal -> on inverse
            "inverse_volatility": (1 / vol) if vol and vol > 0 else None,
            "inverse_beta": (1 / abs(beta)) if beta and beta != 0 else None,
        }

    def _extract_technical(self, last_row: pd.Series) -> dict[str, float | None]:
        rsi = self._safe(last_row, "rsi_14")
        macd_hist = self._safe(last_row, "macd_hist")
        bb = self._safe(last_row, "bollinger_pct_b")
        return {
            # RSI centré : distance à 50 pénalisée (survente/surachat extrêmes)
            "rsi_centered": (50 - abs(rsi - 50)) if rsi is not None else None,
            "macd_hist": macd_hist,
            "bollinger_pct_b": bb,
        }

    @staticmethod
    def _safe(row: pd.Series, key: str) -> float | None:
        val = row.get(key)
        if val is None or pd.isna(val):
            return None
        return float(val)


FACTOR_FIELD_MAP = {
    FactorType.VALUE: "value",
    FactorType.GROWTH: "growth",
    FactorType.QUALITY: "quality",
    FactorType.MOMENTUM: "momentum",
    FactorType.RISK: "risk",
    FactorType.TECHNICAL: "technical",
}
