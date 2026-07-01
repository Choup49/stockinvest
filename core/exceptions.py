"""Exceptions métier custom pour StockInvest Pro."""


class StockInvestProError(Exception):
    """Exception de base pour toute l'application."""


class DataFetchError(StockInvestProError):
    """Levée quand la récupération de données échoue (réseau, ticker invalide, etc.)."""

    def __init__(self, ticker: str, reason: str) -> None:
        self.ticker = ticker
        self.reason = reason
        super().__init__(f"Échec de récupération pour '{ticker}': {reason}")


class InvalidTickerError(DataFetchError):
    """Levée quand un ticker n'existe pas ou ne renvoie aucune donnée."""


class DataQualityError(StockInvestProError):
    """Levée quand un dataset ne passe pas les contrôles qualité minimaux."""

    def __init__(self, ticker: str, reason: str) -> None:
        self.ticker = ticker
        self.reason = reason
        super().__init__(f"Qualité de données insuffisante pour '{ticker}': {reason}")


class InsufficientDataError(StockInvestProError):
    """Levée quand un calcul nécessite plus de points de données que disponibles."""

    def __init__(self, ticker: str, required: int, available: int) -> None:
        self.ticker = ticker
        self.required = required
        self.available = available
        super().__init__(
            f"Données insuffisantes pour '{ticker}': {available} points disponibles, {required} requis"
        )


class ScoringError(StockInvestProError):
    """Levée quand le moteur de scoring quantitatif échoue."""


class BacktestError(StockInvestProError):
    """Levée quand la simulation de backtest échoue."""
