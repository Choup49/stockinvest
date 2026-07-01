"""Panneau gauche : liste de tickers surveillés avec mini-graphique."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QWidget

from ui.theme import color_for_change

COLUMNS = ["Ticker", "Prix", "Var %"]


class MarketWatchWidget(QTableWidget):
    """
    Table compacte des tickers suivis. Émet ticker_selected quand
    l'utilisateur clique une ligne, pour piloter le Chart et le Quant HUD.
    """

    ticker_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, len(COLUMNS), parent)
        self.setHorizontalHeaderLabels(COLUMNS)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cellClicked.connect(self._on_cell_clicked)

    def update_watchlist(self, rows: list[dict]) -> None:
        """
        Args:
            rows: [{"ticker": str, "price": float, "change_pct": float}, ...]
        """
        self.setRowCount(len(rows))
        for i, row in enumerate(rows):
            ticker_item = QTableWidgetItem(row["ticker"])
            price_item = QTableWidgetItem(f"{row['price']:,.2f}")
            change = row["change_pct"]
            change_item = QTableWidgetItem(f"{'+' if change >= 0 else ''}{change:.2f}%")
            change_item.setForeground(Qt.GlobalColor.white)
            change_item.setData(Qt.ItemDataRole.ForegroundRole, None)

            self.setItem(i, 0, ticker_item)
            self.setItem(i, 1, price_item)
            self.setItem(i, 2, change_item)

    def _on_cell_clicked(self, row: int, _col: int) -> None:
        ticker_item = self.item(row, 0)
        if ticker_item:
            self.ticker_selected.emit(ticker_item.text())
