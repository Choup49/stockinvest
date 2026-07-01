"""
Page Deep Dive : analyse d'une entreprise en 3 niveaux de disclosure
progressive.

Niveau 1 (défaut)  : ScoreCardWidget — score, tendance, 3 métriques clés.
                      Compréhension en < 5 secondes.
Niveau 2 (1 clic)  : chart complet + quant HUD 6 facteurs + fondamentaux
                      + sentiment.
Niveau 3 (1 clic)  : vue experte — décomposition mathématique du score,
                      données financières complètes, logs du quant engine.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ai.sentiment import SentimentResult
from ai.summarizer import CompanySummary
from core.enums import FactorType
from core.models import CompanyInfo, FundamentalsSnapshot, QuantScore
from quant.explainer import FACTOR_LABELS_FR
from ui.theme import ACCENT_BLUE, TEXT_SECONDARY, card_style, color_for_change
from ui.widgets.chart_view import ChartViewWidget
from ui.widgets.quant_hud import QuantHudWidget
from ui.widgets.score_card import ScoreCardWidget

LEVEL_1 = 0
LEVEL_2 = 1
LEVEL_3 = 2


class LevelNavBar(QWidget):
    """Petite barre de navigation entre les 3 niveaux de détail."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)

        self.btn_simple = QPushButton("Simple")
        self.btn_analytique = QPushButton("Analytique")
        self.btn_expert = QPushButton("Expert")

        for btn in (self.btn_simple, self.btn_analytique, self.btn_expert):
            btn.setObjectName("ghost")
            btn.setCheckable(True)

        layout.addWidget(self.btn_simple, 0, 0)
        layout.addWidget(self.btn_analytique, 0, 1)
        layout.addWidget(self.btn_expert, 0, 2)
        layout.setColumnStretch(3, 1)

    def set_active(self, level: int) -> None:
        self.btn_simple.setChecked(level == LEVEL_1)
        self.btn_analytique.setChecked(level == LEVEL_2)
        self.btn_expert.setChecked(level == LEVEL_3)
        active_style = f"color: white; border-bottom: 2px solid {ACCENT_BLUE}; border-radius: 0;"
        self.btn_simple.setStyleSheet(active_style if level == LEVEL_1 else "")
        self.btn_analytique.setStyleSheet(active_style if level == LEVEL_2 else "")
        self.btn_expert.setStyleSheet(active_style if level == LEVEL_3 else "")


class AnalyticalView(QWidget):
    """Niveau 2 : chart complet, quant HUD 6 facteurs, fondamentaux, sentiment."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setSpacing(12)

        self.chart = ChartViewWidget()
        self.quant_hud = QuantHudWidget()

        self.fundamentals_card = QFrame()
        self.fundamentals_card.setObjectName("card")
        fund_layout = QVBoxLayout(self.fundamentals_card)
        self.fundamentals_label = QLabel("Fondamentaux : —")
        self.fundamentals_label.setWordWrap(True)
        fund_layout.addWidget(QLabel("FONDAMENTAUX"))
        fund_layout.addWidget(self.fundamentals_label)

        self.sentiment_card = QFrame()
        self.sentiment_card.setObjectName("card")
        sent_layout = QVBoxLayout(self.sentiment_card)
        self.sentiment_label = QLabel("Sentiment : —")
        self.sentiment_label.setWordWrap(True)
        sent_layout.addWidget(QLabel("SENTIMENT"))
        sent_layout.addWidget(self.sentiment_label)

        self.summary_card = QFrame()
        self.summary_card.setObjectName("card")
        sum_layout = QVBoxLayout(self.summary_card)
        self.summary_label = QLabel("Résumé IA : —")
        self.summary_label.setWordWrap(True)
        sum_layout.addWidget(QLabel("RÉSUMÉ IA"))
        sum_layout.addWidget(self.summary_label)

        layout.addWidget(self.chart, 0, 0, 2, 2)
        layout.addWidget(self.quant_hud, 0, 2, 2, 1)
        layout.addWidget(self.fundamentals_card, 2, 0)
        layout.addWidget(self.sentiment_card, 2, 1)
        layout.addWidget(self.summary_card, 2, 2)


class ExpertView(QWidget):
    """
    Niveau 3 : vue experte — décomposition mathématique du score par
    facteur (raw value, z-score, percentile, poids), données financières
    complètes.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("DÉCOMPOSITION MATHÉMATIQUE DU SCORE"))

        self.breakdown_table = QTableWidget(0, 4)
        self.breakdown_table.setHorizontalHeaderLabels(["Facteur", "Valeur brute (z)", "Percentile", "Poids"])
        self.breakdown_table.verticalHeader().setVisible(False)
        self.breakdown_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.breakdown_table)

        layout.addWidget(QLabel("DONNÉES FINANCIÈRES COMPLÈTES"))
        self.financials_label = QLabel("—")
        self.financials_label.setWordWrap(True)
        self.financials_label.setStyleSheet(card_style())
        layout.addWidget(self.financials_label)

        layout.addStretch()

    def load_breakdown(self, quant_score: QuantScore) -> None:
        from quant.scoring import FACTOR_WEIGHTS

        self.breakdown_table.setRowCount(len(quant_score.factor_scores))
        for i, (factor_type, fs) in enumerate(quant_score.factor_scores.items()):
            weight = FACTOR_WEIGHTS.get(factor_type, 0.0)
            self.breakdown_table.setItem(i, 0, QTableWidgetItem(FACTOR_LABELS_FR[factor_type]))
            self.breakdown_table.setItem(i, 1, QTableWidgetItem(f"{fs.zscore:+.3f}"))
            self.breakdown_table.setItem(i, 2, QTableWidgetItem(f"{fs.percentile:.1f}%"))
            self.breakdown_table.setItem(i, 3, QTableWidgetItem(f"{weight:.0%}"))

    def load_financials(self, fundamentals: FundamentalsSnapshot) -> None:
        self.financials_label.setText(
            f"PER (trailing): {fundamentals.trailing_pe or '—'}\n"
            f"PER (forward): {fundamentals.forward_pe or '—'}\n"
            f"ROE: {fundamentals.return_on_equity or '—'}\n"
            f"Free Cash Flow: {fundamentals.free_cash_flow or '—'}\n"
            f"Croissance CA: {fundamentals.revenue_growth or '—'}\n"
            f"Marge nette: {fundamentals.profit_margins or '—'}\n"
            f"Chiffre d'affaires total: {fundamentals.total_revenue or '—'}"
        )


class DeepDivePage(QWidget):
    """
    Page Deep Dive complète, avec disclosure progressive sur 3 niveaux.
    Le Niveau 1 est affiché par défaut à chaque nouvelle sélection de
    ticker (principe de progressive disclosure demandé), l'utilisateur
    choisit ensuite d'aller plus loin.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 12, 16, 16)

        self.nav_bar = LevelNavBar()
        self.nav_bar.btn_simple.clicked.connect(lambda: self._go_to_level(LEVEL_1))
        self.nav_bar.btn_analytique.clicked.connect(lambda: self._go_to_level(LEVEL_2))
        self.nav_bar.btn_expert.clicked.connect(lambda: self._go_to_level(LEVEL_3))
        root_layout.addWidget(self.nav_bar)

        self.stack = QStackedWidget()

        self.level1_card = ScoreCardWidget()
        self.level1_card.expand_requested.connect(lambda: self._go_to_level(LEVEL_2))

        self.level2_view = AnalyticalView()

        expert_scroll = QScrollArea()
        expert_scroll.setWidgetResizable(True)
        self.level3_view = ExpertView()
        expert_scroll.setWidget(self.level3_view)

        self.stack.addWidget(self.level1_card)   # index LEVEL_1
        self.stack.addWidget(self.level2_view)    # index LEVEL_2
        self.stack.addWidget(expert_scroll)        # index LEVEL_3

        root_layout.addWidget(self.stack)

        self._go_to_level(LEVEL_1)

    def _go_to_level(self, level: int) -> None:
        self.stack.setCurrentIndex(level)
        self.nav_bar.set_active(level)

    # Alias pour accès direct au chart/quant_hud depuis main_window (compat)
    @property
    def chart(self) -> ChartViewWidget:
        return self.level2_view.chart

    @property
    def quant_hud(self) -> QuantHudWidget:
        return self.level2_view.quant_hud

    def load_company(
        self,
        company: CompanyInfo,
        price_features_df,
        fundamentals: FundamentalsSnapshot,
        quant_score: QuantScore,
        sentiment: SentimentResult,
        summary: CompanySummary,
    ) -> None:
        """
        Recharge entièrement la page pour une nouvelle entreprise sélectionnée.
        Revient systématiquement au Niveau 1 (principe : compréhension rapide
        d'abord, détails à la demande).
        """
        # --- Niveau 1 ---
        self.level1_card.update_score(company.name, quant_score)

        # --- Niveau 2 ---
        self.level2_view.chart.plot(price_features_df)
        self.level2_view.quant_hud.update_score(quant_score)
        self.level2_view.fundamentals_label.setText(
            f"PER: {fundamentals.trailing_pe or '—'}  |  "
            f"ROE: {fundamentals.return_on_equity or '—'}  |  "
            f"Marge nette: {fundamentals.profit_margins or '—'}"
        )
        self.level2_view.sentiment_label.setText(
            f"{sentiment.label} ({sentiment.global_sentiment:+.2f}) "
            f"— {sentiment.n_headlines_analyzed} news analysées"
        )
        self.level2_view.summary_label.setText(f"({summary.source}) {summary.overview}")

        # --- Niveau 3 ---
        self.level3_view.load_breakdown(quant_score)
        self.level3_view.load_financials(fundamentals)

        self._go_to_level(LEVEL_1)