"""Bandeau défilant de tickers en top bar."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QHBoxLayout, QWidget

from ui.theme import color_for_change


class TickerTapeWidget(QWidget):
    """Affiche une liste de tickers avec leur variation, défilant horizontalement."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 4, 8, 4)
        self._layout.setSpacing(24)
        self._quotes: dict[str, tuple[float, float]] = {}
        self.setFixedHeight(28)

    def update_quotes(self, quotes: dict[str, tuple[float, float]]) -> None:
        """
        Args:
            quotes: {ticker: (prix, variation_pct)}.
        """
        self._quotes = quotes
        self._rebuild()

    def _rebuild(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for ticker, (price, change_pct) in self._quotes.items():
            sign = "+" if change_pct >= 0 else ""
            label = QLabel(f"{ticker}  {price:,.2f}  ({sign}{change_pct:.2f}%)")
            label.setStyleSheet(f"color: {color_for_change(change_pct)}; font-weight: bold;")
            self._layout.addWidget(label)

        self._layout.addStretch()
