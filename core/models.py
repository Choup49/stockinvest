"""Dataclasses métier partagées entre toutes les couches de l'application."""

from dataclasses import dataclass, field
from datetime import datetime

from core.enums import FactorType, Sector


@dataclass
class TickerSearchResult:
    """Résultat de résolution nom d'entreprise -> symbole boursier."""

    symbol: str
    name: str
    exchange: str | None
    type: str | None  # "EQUITY", "ETF", etc.
    score: float = 0.0  # pertinence relative, plus haut = meilleur match


@dataclass
class CompanyInfo:
    """Informations descriptives d'une entreprise."""

    ticker: str
    name: str
    sector: Sector
    industry: str | None
    country: str | None
    market_cap: float | None
    currency: str | None
    exchange: str | None
    fetched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FundamentalsSnapshot:
    """Snapshot des ratios fondamentaux les plus récents disponibles."""

    ticker: str
    trailing_pe: float | None
    forward_pe: float | None
    return_on_equity: float | None
    free_cash_flow: float | None
    revenue_growth: float | None
    profit_margins: float | None
    total_revenue: float | None
    fetched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class QualityReport:
    """Rapport de qualité généré après nettoyage d'un dataset."""

    ticker: str
    rows_before: int
    rows_after: int
    rows_dropped: int
    drop_reasons: dict[str, int]
    passed_liquidity_filter: bool
    generated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def drop_ratio(self) -> float:
        if self.rows_before == 0:
            return 0.0
        return self.rows_dropped / self.rows_before


@dataclass
class FactorScore:
    """Score normalisé d'un facteur quantitatif unique pour un ticker."""

    factor_type: FactorType
    raw_value: float
    zscore: float
    percentile: float


@dataclass
class QuantScore:
    """Score quantitatif multi-facteurs complet pour un ticker."""

    ticker: str
    sector: Sector
    global_score: float  # /100
    factor_scores: dict[FactorType, FactorScore]
    strengths: list[str]
    weaknesses: list[str]
    computed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BacktestResult:
    """Résultat agrégé d'une simulation de backtest."""

    strategy_name: str
    cagr: float
    sharpe_ratio: float
    max_drawdown: float
    volatility: float
    total_return: float
    benchmark_return: float
    equity_curve: dict[str, float]  # date ISO -> valeur portefeuille