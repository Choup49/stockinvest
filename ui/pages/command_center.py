"""Page Command Center : heatmap secteurs, régime marché, volatilité, top movers."""

import pyqtgraph as pg
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from core.enums import MarketRegime
from ui.theme import color_for_change
from ui.widgets.data_table import DataTableWidget


class SectorHeatmapWidget(QWidget):
    """Grille colorée représentant la performance moyenne par secteur."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setSpacing(4)

    def update_heatmap(self, sector_performance: dict[str, float]) -> None:
        """
        Args:
            sector_performance: {secteur: variation_pct_moyenne}.
        """
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sectors = list(sector_performance.items())
        n_cols = 3
        for i, (sector, perf) in enumerate(sectors):
            row, col = divmod(i, n_cols)
            color = color_for_change(perf)
            label = QLabel(f"{sector}\n{'+' if perf >= 0 else ''}{perf:.2f}%")
            label.setStyleSheet(
                f"background-color: {color}22; border: 1px solid {color}; "
                f"color: {color}; padding: 12px; font-weight: bold;"
            )
            label.setWordWrap(True)
            self._layout.addWidget(label, row, col)


class CommandCenterPage(QWidget):
    """
    Vue d'ensemble marché : heatmap secteurs, régime, volatilité globale,
    top movers du jour.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.regime_label = QLabel("Régime de marché : —")
        self.regime_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.volatility_label = QLabel("Volatilité globale (VIX proxy) : —")

        self.heatmap = SectorHeatmapWidget()

        self.top_movers_table = DataTableWidget(["Ticker", "Prix", "Var %"])

        layout.addWidget(self.regime_label)
        layout.addWidget(self.volatility_label)
        layout.addWidget(QLabel("HEATMAP SECTEURS"))
        layout.addWidget(self.heatmap)
        layout.addWidget(QLabel("TOP MOVERS"))
        layout.addWidget(self.top_movers_table)

    def update_market_regime(self, regime: MarketRegime, volatility: float) -> None:
        self.regime_label.setText(f"Régime de marché : {regime.value.upper()}")
        self.volatility_label.setText(f"Volatilité globale : {volatility:.1%}")

    def update_sector_heatmap(self, sector_performance: dict[str, float]) -> None:
        self.heatmap.update_heatmap(sector_performance)

    def update_top_movers(self, movers: list[dict]) -> None:
        self.top_movers_table.load_rows(movers)
