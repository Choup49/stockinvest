"""Panneau droit : score /100, radar 6 facteurs, explications."""

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.enums import FactorType
from core.models import QuantScore
from quant.explainer import FACTOR_LABELS_FR
from ui.theme import ACCENT_GREEN, ACCENT_RED, TEXT_SECONDARY, color_for_change


class RadarChartWidget(pg.PlotWidget):
    """Radar/spider chart des 6 facteurs, dessiné avec des PlotCurveItem polaires."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAspectLocked(True)
        self.hideAxis("bottom")
        self.hideAxis("left")
        self.setMouseEnabled(x=False, y=False)

    def plot_factors(self, percentiles: dict[FactorType, float]) -> None:
        self.clear()
        factors = list(percentiles.keys())
        n = len(factors)
        if n == 0:
            return

        angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
        values = np.array([percentiles[f] / 100.0 for f in factors])  # normalisé 0-1

        # Grille de fond (cercles à 25/50/75/100%)
        for r in (0.25, 0.5, 0.75, 1.0):
            circle_x = r * np.cos(np.linspace(0, 2 * np.pi, 100))
            circle_y = r * np.sin(np.linspace(0, 2 * np.pi, 100))
            self.plot(circle_x, circle_y, pen=pg.mkPen("#2A2D35", width=1))

        x = values * np.cos(angles)
        y = values * np.sin(angles)
        x = np.append(x, x[0])
        y = np.append(y, y[0])

        self.plot(x, y, pen=pg.mkPen("#3B82F6", width=2), fillLevel=0, brush=pg.mkBrush(59, 130, 246, 60))

        for i, factor in enumerate(factors):
            label_x = 1.15 * np.cos(angles[i])
            label_y = 1.15 * np.sin(angles[i])
            text = pg.TextItem(FACTOR_LABELS_FR[factor], anchor=(0.5, 0.5), color="#E6E8EB")
            text.setPos(label_x, label_y)
            self.addItem(text)


class QuantHudWidget(QWidget):
    """Panneau complet : score global, radar, listes forces/faiblesses."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.score_label = QLabel("--/100")
        self.score_label.setStyleSheet("font-size: 32px; font-weight: bold;")

        self.radar = RadarChartWidget()
        self.radar.setFixedHeight(220)

        self.strengths_label = QLabel("Points forts : —")
        self.strengths_label.setWordWrap(True)
        self.strengths_label.setStyleSheet(f"color: {ACCENT_GREEN};")

        self.weaknesses_label = QLabel("Points faibles : —")
        self.weaknesses_label.setWordWrap(True)
        self.weaknesses_label.setStyleSheet(f"color: {ACCENT_RED};")

        layout.addWidget(QLabel("SCORE QUANTITATIF"))
        layout.addWidget(self.score_label)
        layout.addWidget(self.radar)
        layout.addWidget(self.strengths_label)
        layout.addWidget(self.weaknesses_label)
        layout.addStretch()

    def update_score(self, score: QuantScore) -> None:
        self.score_label.setText(f"{score.global_score:.0f}/100")
        self.score_label.setStyleSheet(
            f"font-size: 32px; font-weight: bold; color: {color_for_change(score.global_score - 50)};"
        )

        percentiles = {ft: fs.percentile for ft, fs in score.factor_scores.items()}
        self.radar.plot_factors(percentiles)

        self.strengths_label.setText("Points forts :\n• " + "\n• ".join(score.strengths))
        self.weaknesses_label.setText("Points faibles :\n• " + "\n• ".join(score.weaknesses))
