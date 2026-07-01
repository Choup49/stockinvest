"""Widget de graphique candlestick + volume + indicateurs via pyqtgraph."""

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ui.theme import ACCENT_GREEN, ACCENT_RED, BORDER, SURFACE


class CandlestickItem(pg.GraphicsObject):
    """Item pyqtgraph custom pour dessiner des bougies OHLC."""

    def __init__(self, data: pd.DataFrame) -> None:
        """
        Args:
            data: DataFrame avec colonnes Open, High, Low, Close, index entier (0..n).
        """
        super().__init__()
        self.data = data
        self.picture = pg.QtGui.QPicture()
        self._generate_picture()

    def _generate_picture(self) -> None:
        painter = pg.QtGui.QPainter(self.picture)
        width = 0.6

        for i, row in enumerate(self.data.itertuples()):
            color = ACCENT_GREEN if row.Close >= row.Open else ACCENT_RED
            pen = pg.mkPen(color=color, width=1)
            brush = pg.mkBrush(color=color)
            painter.setPen(pen)
            painter.setBrush(brush)

            painter.drawLine(pg.QtCore.QPointF(i, row.Low), pg.QtCore.QPointF(i, row.High))
            rect = pg.QtCore.QRectF(i - width / 2, min(row.Open, row.Close), width, abs(row.Close - row.Open) or 0.01)
            painter.drawRect(rect)

        painter.end()

    def paint(self, painter, *args) -> None:
        painter.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return pg.QtCore.QRectF(self.picture.boundingRect())


class ChartViewWidget(QWidget):
    """
    Graphique principal : candlestick + volume en sous-panneau + overlays
    d'indicateurs techniques (MA50, MA200, Bollinger).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        pg.setConfigOption("background", SURFACE)
        pg.setConfigOption("foreground", "#E6E8EB")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.price_plot = pg.PlotWidget()
        self.volume_plot = pg.PlotWidget()
        self.volume_plot.setMaximumHeight(100)
        self.volume_plot.setXLink(self.price_plot)

        layout.addWidget(self.price_plot, stretch=4)
        layout.addWidget(self.volume_plot, stretch=1)

        self._candle_item: CandlestickItem | None = None

    def plot(self, df: pd.DataFrame, show_ma: bool = True, show_bollinger: bool = False) -> None:
        """
        Args:
            df: DataFrame OHLCV enrichi de features (ma_50, ma_200 si show_ma=True).
        """
        self.price_plot.clear()
        self.volume_plot.clear()

        plot_df = df.reset_index(drop=True)

        self._candle_item = CandlestickItem(plot_df)
        self.price_plot.addItem(self._candle_item)

        if show_ma and "ma_50" in plot_df.columns:
            self.price_plot.plot(plot_df.index, plot_df["ma_50"].values, pen=pg.mkPen("#3B82F6", width=1))
        if show_ma and "ma_200" in plot_df.columns:
            self.price_plot.plot(plot_df.index, plot_df["ma_200"].values, pen=pg.mkPen("#F59E0B", width=1))

        volume_bars = pg.BarGraphItem(
            x=plot_df.index, height=plot_df["Volume"].values, width=0.6, brush=BORDER
        )
        self.volume_plot.addItem(volume_bars)
