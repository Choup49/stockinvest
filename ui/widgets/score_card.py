"""
Carte de score simplifiée — Niveau 1 de disclosure progressive.

Objectif UX : l'utilisateur comprend une action en moins de 5 secondes.
Affiche uniquement : score global, tendance, et 3 métriques clés
(Momentum, Risk, Growth). Tout le reste est accessible via un clic
("Voir l'analyse complète") qui bascule vers le Niveau 2.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.enums import FactorType
from core.models import QuantScore
from ui.theme import TEXT_SECONDARY, card_style, color_for_change, trend_arrow


class MetricPill(QFrame):
    """Petite pastille affichant une métrique clé (label + valeur colorée)."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        self.label_widget = QLabel(label.upper())
        self.label_widget.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; font-weight: 600;")

        self.value_widget = QLabel("—")
        self.value_widget.setStyleSheet("font-size: 20px; font-weight: 700;")

        layout.addWidget(self.label_widget)
        layout.addWidget(self.value_widget)

    def set_value(self, zscore: float) -> None:
        """Affiche un z-score sous forme de pourcentile lisible avec couleur de tendance."""
        arrow = trend_arrow(zscore, threshold=0.3)
        self.value_widget.setText(f"{arrow} {zscore:+.1f}")
        self.value_widget.setStyleSheet(
            f"font-size: 20px; font-weight: 700; color: {color_for_change(zscore)};"
        )


class ScoreCardWidget(QWidget):
    """
    Vue simplifiée d'une entreprise : score /100 très visible, tendance,
    et 3 métriques clés seulement (Momentum, Risk, Growth).

    Signal:
        expand_requested — émis quand l'utilisateur clique sur
            "Voir l'analyse complète" pour passer au Niveau 2.
    """

    expand_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        # --- En-tête entreprise ---
        self.company_label = QLabel("Sélectionnez une entreprise")
        self.company_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(self.company_label)

        # --- Score géant + tendance ---
        score_card = QFrame()
        score_card.setObjectName("card")
        score_layout = QVBoxLayout(score_card)
        score_layout.setContentsMargins(28, 24, 28, 24)
        score_layout.setSpacing(4)

        self.score_label = QLabel("--")
        self.score_label.setStyleSheet("font-size: 56px; font-weight: 800;")

        self.score_sub_label = QLabel("Score quantitatif /100")
        self.score_sub_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")

        self.trend_label = QLabel("")
        self.trend_label.setStyleSheet("font-size: 14px; font-weight: 600;")

        score_layout.addWidget(self.score_label)
        score_layout.addWidget(self.score_sub_label)
        score_layout.addWidget(self.trend_label)

        layout.addWidget(score_card)

        # --- 3 métriques clés seulement ---
        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(10)

        self.momentum_pill = MetricPill("Momentum")
        self.risk_pill = MetricPill("Risk")
        self.growth_pill = MetricPill("Growth")

        metrics_grid.addWidget(self.momentum_pill, 0, 0)
        metrics_grid.addWidget(self.risk_pill, 0, 1)
        metrics_grid.addWidget(self.growth_pill, 0, 2)

        layout.addLayout(metrics_grid)

        # --- CTA vers le Niveau 2 ---
        self.expand_button = QPushButton("Voir l'analyse complète →")
        self.expand_button.setObjectName("primary")
        self.expand_button.clicked.connect(self.expand_requested.emit)
        layout.addWidget(self.expand_button)

        layout.addStretch()

    def update_score(self, company_name: str, quant_score: QuantScore) -> None:
        """Met à jour la carte avec le score et les 3 métriques clés d'une entreprise."""
        self.company_label.setText(f"{company_name} ({quant_score.ticker})")

        self.score_label.setText(f"{quant_score.global_score:.0f}")
        self.score_label.setStyleSheet(
            f"font-size: 56px; font-weight: 800; color: {color_for_change(quant_score.global_score - 50)};"
        )

        delta = quant_score.global_score - 50
        arrow = trend_arrow(delta, threshold=2)
        direction = "au-dessus" if delta > 0 else "en dessous" if delta < 0 else "dans"
        self.trend_label.setText(f"{arrow} {direction} de la moyenne sectorielle")
        self.trend_label.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {color_for_change(delta)};"
        )

        momentum = quant_score.factor_scores.get(FactorType.MOMENTUM)
        risk = quant_score.factor_scores.get(FactorType.RISK)
        growth = quant_score.factor_scores.get(FactorType.GROWTH)

        self.momentum_pill.set_value(momentum.zscore if momentum else 0.0)
        self.risk_pill.set_value(risk.zscore if risk else 0.0)
        self.growth_pill.set_value(growth.zscore if growth else 0.0)