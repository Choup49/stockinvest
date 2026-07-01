"""Page Simulator : configuration et résultats de backtest."""

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.enums import RebalanceFrequency
from core.models import BacktestResult
from ui.theme import ACCENT_BLUE, SURFACE


class SimulatorPage(QWidget):
    """Interface de configuration de stratégie et affichage des résultats de backtest."""

    run_requested = Signal(dict)  # émet les paramètres choisis

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.top_n_input = QSpinBox()
        self.top_n_input.setRange(1, 100)
        self.top_n_input.setValue(10)

        self.rebalance_input = QComboBox()
        self.rebalance_input.addItems([f.value for f in RebalanceFrequency])
        self.rebalance_input.setCurrentText(RebalanceFrequency.QUARTERLY.value)

        self.transaction_cost_input = QDoubleSpinBox()
        self.transaction_cost_input.setRange(0, 100)
        self.transaction_cost_input.setValue(10.0)
        self.transaction_cost_input.setSuffix(" bps")

        self.slippage_input = QDoubleSpinBox()
        self.slippage_input.setRange(0, 100)
        self.slippage_input.setValue(5.0)
        self.slippage_input.setSuffix(" bps")

        self.initial_capital_input = QDoubleSpinBox()
        self.initial_capital_input.setRange(1_000, 100_000_000)
        self.initial_capital_input.setValue(100_000)
        self.initial_capital_input.setPrefix("$ ")

        form.addRow("Top N titres :", self.top_n_input)
        form.addRow("Rééquilibrage :", self.rebalance_input)
        form.addRow("Frais de transaction :", self.transaction_cost_input)
        form.addRow("Slippage :", self.slippage_input)
        form.addRow("Capital initial :", self.initial_capital_input)

        self.run_button = QPushButton("Lancer le backtest")
        self.run_button.clicked.connect(self._emit_run_request)

        self.results_grid = QGridLayout()
        self.cagr_label = QLabel("CAGR : —")
        self.sharpe_label = QLabel("Sharpe : —")
        self.mdd_label = QLabel("Max Drawdown : —")
        self.vol_label = QLabel("Volatilité : —")
        self.benchmark_label = QLabel("Benchmark (S&P 500) : —")
        for i, lbl in enumerate(
            [self.cagr_label, self.sharpe_label, self.mdd_label, self.vol_label, self.benchmark_label]
        ):
            self.results_grid.addWidget(lbl, i // 3, i % 3)

        self.equity_plot = pg.PlotWidget()
        self.equity_plot.setBackground(SURFACE)
        self.equity_plot.setLabel("left", "Valeur portefeuille ($)")
        self.equity_plot.setLabel("bottom", "Jours")

        layout.addLayout(form)
        layout.addWidget(self.run_button)
        layout.addLayout(self.results_grid)
        layout.addWidget(self.equity_plot)

    def _emit_run_request(self) -> None:
        params = {
            "top_n": self.top_n_input.value(),
            "rebalance_frequency": RebalanceFrequency(self.rebalance_input.currentText()),
            "transaction_cost_bps": self.transaction_cost_input.value(),
            "slippage_bps": self.slippage_input.value(),
            "initial_capital": self.initial_capital_input.value(),
        }
        self.run_requested.emit(params)

    def display_result(self, result: BacktestResult) -> None:
        self.cagr_label.setText(f"CAGR : {result.cagr:.1%}")
        self.sharpe_label.setText(f"Sharpe : {result.sharpe_ratio:.2f}")
        self.mdd_label.setText(f"Max Drawdown : {result.max_drawdown:.1%}")
        self.vol_label.setText(f"Volatilité : {result.volatility:.1%}")
        self.benchmark_label.setText(f"Benchmark (S&P 500) : {result.benchmark_return:.1%}")

        self.equity_plot.clear()
        values = list(result.equity_curve.values())
        self.equity_plot.plot(range(len(values)), values, pen=pg.mkPen(ACCENT_BLUE, width=2))
