"""
Normalisation sectorielle des facteurs bruts : winsorization 1%-99%,
z-score, comparaison uniquement avec les entreprises du même secteur.
"""

import numpy as np
import pandas as pd

from core.enums import Sector
from utils.logger import logger


class SectorNormalizer:
    """
    Normalise un facteur brut par rapport à son univers sectoriel.

    Toutes les comparaisons sont faites entreprise-vs-secteur, jamais
    entreprise-vs-marché entier, conformément au cahier des charges.
    """

    def __init__(self, winsorize_lower: float = 0.01, winsorize_upper: float = 0.99) -> None:
        self.winsorize_lower = winsorize_lower
        self.winsorize_upper = winsorize_upper

    def normalize_universe(
        self, raw_values: dict[str, float | None], sector: Sector
    ) -> dict[str, float]:
        """
        Args:
            raw_values: {ticker: valeur_brute} pour TOUTES les entreprises
                du même secteur (déjà filtrées en amont).
            sector: secteur de comparaison (pour logging uniquement ici).

        Returns:
            {ticker: zscore} — les tickers avec valeur brute None sont
            exclus du calcul mais reçoivent un z-score de 0.0 (neutre).
        """
        valid_items = {t: v for t, v in raw_values.items() if v is not None and not np.isnan(v)}

        if len(valid_items) < 3:
            logger.warning(
                f"Secteur {sector.value}: seulement {len(valid_items)} valeurs valides, "
                "z-scores mis à 0 (neutre) par manque de taille d'échantillon"
            )
            return {t: 0.0 for t in raw_values}

        series = pd.Series(valid_items)
        winsorized = self._winsorize(series)

        mean = winsorized.mean()
        std = winsorized.std()

        if std == 0 or np.isnan(std):
            zscores = pd.Series(0.0, index=series.index)
        else:
            zscores = (winsorized - mean) / std

        result = {t: float(zscores.get(t, 0.0)) for t in raw_values}
        return result

    def _winsorize(self, series: pd.Series) -> pd.Series:
        """Écrête les valeurs extrêmes aux percentiles 1% et 99%."""
        lower_bound = series.quantile(self.winsorize_lower)
        upper_bound = series.quantile(self.winsorize_upper)
        return series.clip(lower=lower_bound, upper=upper_bound)

    @staticmethod
    def zscore_to_percentile(zscore: float) -> float:
        """Convertit un z-score en percentile approximatif (loi normale), utile pour l'UI."""
        from math import erf, sqrt

        return 100.0 * 0.5 * (1 + erf(zscore / sqrt(2)))
