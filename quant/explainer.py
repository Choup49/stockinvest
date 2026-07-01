"""Génération d'explications lisibles pour un score quantitatif."""

from core.enums import FactorType
from core.models import FactorScore

FACTOR_LABELS_FR = {
    FactorType.VALUE: "Valorisation",
    FactorType.GROWTH: "Croissance",
    FactorType.QUALITY: "Qualité",
    FactorType.MOMENTUM: "Momentum",
    FactorType.RISK: "Risque maîtrisé",
    FactorType.TECHNICAL: "Signal technique",
}

STRENGTH_THRESHOLD = 0.75  # z-score
WEAKNESS_THRESHOLD = -0.75


class ScoreExplainer:
    """
    Transforme les z-scores par facteur en phrases d'explication
    (points forts / points faibles) affichées dans le Quant HUD.
    """

    def explain(
        self, factor_scores: dict[FactorType, FactorScore]
    ) -> tuple[list[str], list[str]]:
        """
        Returns:
            (strengths, weaknesses) — listes de phrases triées par intensité
            du z-score décroissante/croissante.
        """
        ranked = sorted(factor_scores.items(), key=lambda kv: kv[1].zscore, reverse=True)

        strengths = [
            self._format_strength(factor_type, score)
            for factor_type, score in ranked
            if score.zscore >= STRENGTH_THRESHOLD
        ]
        weaknesses = [
            self._format_weakness(factor_type, score)
            for factor_type, score in reversed(ranked)
            if score.zscore <= WEAKNESS_THRESHOLD
        ]

        if not strengths:
            best_factor, best_score = ranked[0]
            strengths = [self._format_strength(best_factor, best_score, tentative=True)]
        if not weaknesses:
            worst_factor, worst_score = ranked[-1]
            weaknesses = [self._format_weakness(worst_factor, worst_score, tentative=True)]

        return strengths, weaknesses

    def _format_strength(
        self, factor_type: FactorType, score: FactorScore, tentative: bool = False
    ) -> str:
        label = FACTOR_LABELS_FR[factor_type]
        if tentative:
            return f"{label} légèrement au-dessus de la moyenne sectorielle (z={score.zscore:+.2f})"
        return f"{label} nettement supérieur(e) au secteur (z={score.zscore:+.2f}, percentile {score.percentile:.0f}%)"

    def _format_weakness(
        self, factor_type: FactorType, score: FactorScore, tentative: bool = False
    ) -> str:
        label = FACTOR_LABELS_FR[factor_type]
        if tentative:
            return f"{label} légèrement en dessous de la moyenne sectorielle (z={score.zscore:+.2f})"
        return f"{label} nettement inférieur(e) au secteur (z={score.zscore:+.2f}, percentile {score.percentile:.0f}%)"
