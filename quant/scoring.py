"""
Moteur de scoring multi-facteurs StockInvest Pro.

Combine les 6 facteurs normalisés (z-scores sectoriels) selon la
pondération du cahier des charges pour produire un score global /100.
"""

from core.enums import FactorType, Sector
from core.exceptions import ScoringError
from core.models import FactorScore, QuantScore
from quant.explainer import ScoreExplainer
from quant.factors import FACTOR_FIELD_MAP, RawFactorValues
from quant.normalizer import SectorNormalizer
from utils.logger import logger

# Pondération imposée par le cahier des charges
FACTOR_WEIGHTS: dict[FactorType, float] = {
    FactorType.VALUE: 0.20,
    FactorType.GROWTH: 0.20,
    FactorType.QUALITY: 0.20,
    FactorType.MOMENTUM: 0.15,
    FactorType.RISK: 0.15,
    FactorType.TECHNICAL: 0.10,
}


class QuantScoringEngine:
    """
    Calcule le score quantitatif /100 d'un ticker à partir de ses facteurs
    bruts et de l'univers sectoriel de comparaison.
    """

    def __init__(self, normalizer: SectorNormalizer | None = None) -> None:
        self.normalizer = normalizer or SectorNormalizer()
        self.explainer = ScoreExplainer()
        self._validate_weights()

    def _validate_weights(self) -> None:
        total = sum(FACTOR_WEIGHTS.values())
        if abs(total - 1.0) > 1e-6:
            raise ScoringError(f"Pondération des facteurs invalide: somme={total} (attendu 1.0)")

    def score_universe(
        self, sector: Sector, universe_raw_values: dict[str, RawFactorValues]
    ) -> dict[str, QuantScore]:
        """
        Calcule les scores pour tous les tickers d'un même secteur en une passe,
        car la normalisation nécessite l'univers complet.

        Args:
            sector: secteur commun à tous les tickers de universe_raw_values.
            universe_raw_values: {ticker: RawFactorValues}.

        Returns:
            {ticker: QuantScore}
        """
        if not universe_raw_values:
            return {}

        factor_zscores: dict[FactorType, dict[str, float]] = {}

        for factor_type, field_name in FACTOR_FIELD_MAP.items():
            # Agrège les sous-métriques d'un facteur en une valeur composite
            # par simple moyenne des sous-métriques disponibles, PUIS normalise.
            composite_raw = self._compute_composite(universe_raw_values, field_name)
            factor_zscores[factor_type] = self.normalizer.normalize_universe(composite_raw, sector)

        results: dict[str, QuantScore] = {}
        for ticker in universe_raw_values:
            factor_scores: dict[FactorType, FactorScore] = {}
            global_score = 0.0

            for factor_type, weight in FACTOR_WEIGHTS.items():
                zscore = factor_zscores[factor_type].get(ticker, 0.0)
                percentile = self.normalizer.zscore_to_percentile(zscore)
                factor_scores[factor_type] = FactorScore(
                    factor_type=factor_type,
                    raw_value=zscore,  # valeur composite déjà agrégée en amont
                    zscore=zscore,
                    percentile=percentile,
                )
                # Score /100 : on mappe le z-score (borné à [-3,3]) linéairement sur [0,100]
                bounded = max(-3.0, min(3.0, zscore))
                contribution = ((bounded + 3.0) / 6.0) * 100.0
                global_score += weight * contribution

            strengths, weaknesses = self.explainer.explain(factor_scores)

            results[ticker] = QuantScore(
                ticker=ticker,
                sector=sector,
                global_score=round(global_score, 2),
                factor_scores=factor_scores,
                strengths=strengths,
                weaknesses=weaknesses,
            )

        logger.info(f"Scoring terminé pour secteur {sector.value}: {len(results)} tickers")
        return results

    def _compute_composite(
        self, universe: dict[str, RawFactorValues], field_name: str
    ) -> dict[str, float | None]:
        """Moyenne des sous-métriques disponibles d'un facteur pour chaque ticker."""
        composite: dict[str, float | None] = {}
        for ticker, raw in universe.items():
            sub_values = [v for v in getattr(raw, field_name).values() if v is not None]
            composite[ticker] = sum(sub_values) / len(sub_values) if sub_values else None
        return composite
