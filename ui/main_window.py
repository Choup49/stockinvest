"""Fenêtre principale StockInvest Pro : layout terminal (top bar, gauche, centre, droite, bas)."""

from PySide6.QtWidgets import (
    QLineEdit,
    QHBoxLayout,
    QMainWindow,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from data.repository import MarketDataRepository
from ui.pages.command_center import CommandCenterPage
from ui.pages.deep_dive import DeepDivePage
from ui.pages.quant_engine import QuantEnginePage
from ui.pages.simulator import SimulatorPage
from ui.theme import build_qss
from ui.widgets.chart_view import ChartViewWidget
from ui.widgets.market_watch import MarketWatchWidget
from ui.widgets.quant_hud import QuantHudWidget
from ui.widgets.ticker_tape import TickerTapeWidget
from utils.logger import logger


class MainWindow(QMainWindow):
    """
    Fenêtre principale : assemble top bar, market watch (gauche), chart
    (centre), quant HUD (droite), et les 4 pages en onglets (bas).
    """

    def __init__(self, repository: MarketDataRepository, theme_colors: dict[str, str]) -> None:
        super().__init__()
        self.repository = repository
        self.setWindowTitle("StockInvest Pro — Terminal Quantitatif")
        self.resize(1600, 950)
        self.setStyleSheet(build_qss(**{
            "background": theme_colors.get("background", "#0B0C10"),
            "surface": theme_colors.get("surface", "#15171C"),
            "border": theme_colors.get("border", "#2A2D35"),
        }))

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # --- TOP BAR ---
        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Recherche universelle (ticker, entreprise...)")
        self.ticker_tape = TickerTapeWidget()
        top_bar_layout.addWidget(self.search_bar, stretch=1)
        top_bar_layout.addWidget(self.ticker_tape, stretch=3)

        # --- ZONE CENTRALE (gauche / centre / droite) ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.market_watch = MarketWatchWidget()
        self.chart_view = ChartViewWidget()
        self.quant_hud = QuantHudWidget()

        main_splitter.addWidget(self.market_watch)
        main_splitter.addWidget(self.chart_view)
        main_splitter.addWidget(self.quant_hud)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setStretchFactor(2, 1)

        # --- BAS : onglets ---
        self.tabs = QTabWidget()
        self.command_center_page = CommandCenterPage()
        self.deep_dive_page = DeepDivePage()
        self.quant_engine_page = QuantEnginePage()
        self.simulator_page = SimulatorPage()

        self.tabs.addTab(self.command_center_page, "Command Center")
        self.tabs.addTab(self.deep_dive_page, "Deep Dive")
        self.tabs.addTab(self.quant_engine_page, "Quant Engine")
        self.tabs.addTab(self.simulator_page, "Simulator")

        vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        vertical_splitter.addWidget(main_splitter)
        vertical_splitter.addWidget(self.tabs)
        vertical_splitter.setStretchFactor(0, 3)
        vertical_splitter.setStretchFactor(1, 2)

        root_layout.addWidget(top_bar)
        root_layout.addWidget(vertical_splitter)

        self.setCentralWidget(central)
        self._connect_signals()

    def _connect_signals(self) -> None:
        self.market_watch.ticker_selected.connect(self._on_ticker_selected)
        self.quant_engine_page.table.row_selected.connect(
            lambda row: self._on_ticker_selected(row.get("ticker", ""))
        )

    def _on_ticker_selected(self, ticker: str) -> None:
        """
        Point d'entrée central quand un ticker est sélectionné n'importe où
        dans l'UI : recharge le chart, le quant HUD et bascule sur Deep Dive.
        """
        logger.debug(f"Ticker sélectionné dans l'UI: {ticker}")
        df = self.repository.get_price_history(ticker)
        if not df.empty:
            self.chart_view.plot(df)
        self.tabs.setCurrentWidget(self.deep_dive_page)
