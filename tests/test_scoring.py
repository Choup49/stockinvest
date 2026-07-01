"""Tests unitaires pour quant/scoring.py et quant/normalizer.py."""

import pytest

from core.enums import Sector
from core.exceptions import ScoringError
from quant.factors import RawFactorValues
from quant.normalizer import SectorNormalizer
from quant.scoring import QuantScoringEngine, FACTOR_WEIGHTS


def _make_universe(n: int = 10) -> dict[str, RawFactorValues]:
    universe = {}
    for i in range(n):
        ticker = f"TICK{i}"
        universe[ticker] = RawFactorValues(
            ticker=ticker,
            value={"inverse_per": 0.05 + i * 0.01, "fcf_yield": 0.03 + i * 0.005},
            growth={"revenue_growth": 0.05 + i * 0.02},
            quality={"roe": 0.10 + i * 0.01, "profit_margin": 0.08 + i * 0.005},
            momentum={"momentum_3m": 0.02 * i, "momentum_6m": 0.04 * i, "momentum_12m": 0.06 * i},
            risk={"inverse_volatility": 5.0 - i * 0.1, "inverse_beta": 1.0},
            technical={"rsi_centered": 40 + i, "macd_hist": 0.1 * i, "bollinger_pct_b": 0.5},
        )
    return universe


def test_factor_weights_sum_to_one():
    assert abs(sum(FACTOR_WEIGHTS.values()) - 1.0) < 1e-9


def test_normalizer_returns_neutral_zscore_for_small_sample():
    normalizer = SectorNormalizer()
    result = normalizer.normalize_universe({"A": 1.0, "B": 2.0}, Sector.TECHNOLOGY)
    assert result["A"] == 0.0
    assert result["B"] == 0.0


def test_normalizer_produces_zero_mean_zscores():
    normalizer = SectorNormalizer()
    raw = {f"T{i}": float(i) for i in range(10)}
    result = normalizer.normalize_universe(raw, Sector.TECHNOLOGY)
    values = list(result.values())
    assert abs(sum(values) / len(values)) < 1e-6


def test_scoring_engine_produces_score_between_0_and_100():
    engine = QuantScoringEngine()
    universe = _make_universe(10)
    scores = engine.score_universe(Sector.TECHNOLOGY, universe)

    assert len(scores) == 10
    for score in scores.values():
        assert 0 <= score.global_score <= 100
        assert len(score.strengths) >= 1
        assert len(score.weaknesses) >= 1


def test_scoring_engine_ranks_better_universe_members_higher():
    engine = QuantScoringEngine()
    universe = _make_universe(10)
    scores = engine.score_universe(Sector.TECHNOLOGY, universe)

    # TICK9 a les meilleures valeurs brutes sur presque tous les facteurs -> score attendu élevé
    assert scores["TICK9"].global_score > scores["TICK0"].global_score
