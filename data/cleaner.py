"""
Nettoyage robuste des données de prix pour StockInvest Pro.

Chaque étape de nettoyage est tracée pour produire un QualityReport
détaillant le nombre de lignes supprimées et la raison.
"""

import numpy as np
import pandas as pd

from core.exceptions import DataQualityError
from core.models import QualityReport
from utils.logger import logger

REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


class PriceDataCleaner:
    """
    Nettoie un DataFrame OHLCV brut issu du fetcher.

    Pipeline (dans l'ordre) :
    1. Garantir la présence de Adj Close (fallback sur Close si absente)
    2. Détecter et corriger les splits non ajustés
    3. Supprimer les valeurs impossibles (prix <= 0, High < Low, etc.)
    4. Gérer les données manquantes (forward-fill limité)
    5. Valider la cohérence volume/prix
    6. Appliquer le filtre de liquidité (dollar volume)
    """

    def __init__(self, min_dollar_volume: float = 250_000.0, max_ffill_days: int = 3) -> None:
        self.min_dollar_volume = min_dollar_volume
        self.max_ffill_days = max_ffill_days

    def clean(self, ticker: str, df: pd.DataFrame) -> tuple[pd.DataFrame, QualityReport]:
        """
        Nettoie le DataFrame et retourne (df_propre, rapport_qualite).

        Raises:
            DataQualityError: si après nettoyage il ne reste pas assez de lignes
                exploitables (< 30 jours de données).
        """
        rows_before = len(df)
        drop_reasons: dict[str, int] = {}
        clean_df = df.copy()

        clean_df = self._ensure_adj_close(clean_df)
        clean_df, n = self._fix_splits(clean_df)
        if n:
            drop_reasons["splits_corrigés"] = n

        clean_df, n = self._remove_impossible_values(clean_df)
        drop_reasons["valeurs_impossibles"] = n

        clean_df, n = self._handle_missing_data(clean_df)
        drop_reasons["donnees_manquantes_non_recuperables"] = n

        clean_df, n = self._validate_volume_price(clean_df)
        drop_reasons["incoherence_volume_prix"] = n

        passed_liquidity = self._check_liquidity(clean_df)

        rows_after = len(clean_df)
        rows_dropped = rows_before - rows_after

        report = QualityReport(
            ticker=ticker,
            rows_before=rows_before,
            rows_after=rows_after,
            rows_dropped=rows_dropped,
            drop_reasons={k: v for k, v in drop_reasons.items() if v > 0},
            passed_liquidity_filter=passed_liquidity,
        )

        if rows_after < 30:
            raise DataQualityError(
                ticker, f"seulement {rows_after} lignes exploitables après nettoyage (minimum 30)"
            )

        logger.info(
            f"Nettoyage {ticker}: {rows_before} -> {rows_after} lignes "
            f"({report.drop_ratio:.1%} supprimées) | liquidité OK={passed_liquidity}"
        )
        return clean_df, report

    def _ensure_adj_close(self, df: pd.DataFrame) -> pd.DataFrame:
        """Si Adj Close est absente, on la crée à partir de Close (cas auto_adjust=True)."""
        if "Adj Close" not in df.columns:
            logger.debug("Adj Close absente, fallback sur Close")
            df["Adj Close"] = df["Close"]
        return df

    def _fix_splits(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        """
        Détecte des sauts de prix > 40% en une journée sans mouvement de volume
        cohérent, symptomatiques d'un split mal ajusté, et les corrige via le
        ratio Close/Adj Close déjà fourni par Yahoo Finance.
        """
        if "Stock Splits" in df.columns:
            split_days = df["Stock Splits"].fillna(0) != 0
            n_splits = int(split_days.sum())
            if n_splits:
                # Adj Close intègre déjà l'ajustement Yahoo ; on aligne Close dessus
                # pour les colonnes utilisées par le feature engineering.
                ratio = df["Adj Close"] / df["Close"].replace(0, np.nan)
                for col in ["Open", "High", "Low", "Close"]:
                    df.loc[split_days, col] = df.loc[split_days, col] * ratio.loc[split_days]
            return df, n_splits
        return df, 0

    def _remove_impossible_values(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        """Supprime les lignes avec prix <= 0, High < Low, ou volume négatif."""
        mask_valid = (
            (df["Open"] > 0)
            & (df["High"] > 0)
            & (df["Low"] > 0)
            & (df["Close"] > 0)
            & (df["High"] >= df["Low"])
            & (df["Volume"] >= 0)
        )
        n_dropped = int((~mask_valid).sum())
        return df.loc[mask_valid].copy(), n_dropped

    def _handle_missing_data(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        """
        Forward-fill limité à max_ffill_days pour combler les trous courts
        (jours fériés mal alignés). Au-delà, les lignes restent NaN et sont
        supprimées.
        """
        before_na = df[REQUIRED_COLUMNS].isna().any(axis=1).sum()
        df[REQUIRED_COLUMNS] = df[REQUIRED_COLUMNS].ffill(limit=self.max_ffill_days)
        still_na_mask = df[REQUIRED_COLUMNS].isna().any(axis=1)
        n_dropped = int(still_na_mask.sum())
        df = df.loc[~still_na_mask].copy()
        logger.debug(f"Données manquantes: {before_na} lignes affectées, {n_dropped} non récupérables")
        return df, n_dropped

    def _validate_volume_price(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        """Supprime les lignes avec volume nul mais mouvement de prix > 5% (donnée suspecte)."""
        price_change = df["Close"].pct_change().abs()
        suspect = (df["Volume"] == 0) & (price_change > 0.05)
        n_dropped = int(suspect.sum())
        return df.loc[~suspect].copy(), n_dropped

    def _check_liquidity(self, df: pd.DataFrame) -> bool:
        """Vérifie que le dollar volume moyen (60j) dépasse le seuil configuré."""
        if df.empty:
            return False
        dollar_volume = (df["Close"] * df["Volume"]).tail(60).mean()
        return bool(dollar_volume >= self.min_dollar_volume)
