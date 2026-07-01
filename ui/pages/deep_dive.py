"""Page Deep Dive : analyse complète d'une entreprise (chart, fondamentaux, quant, sentiment, IA)."""

from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from ai.sentiment import SentimentResult
from ai.summarizer import CompanySummary
from core.models import CompanyInfo, FundamentalsSnapshot, QuantScore
from ui.widgets.chart_view import ChartViewWidget
from ui.widgets.quant_hud import QuantHudWidget


class DeepDivePage(QWidget):
    """Vue détaillée d'une entreprise unique, combinant toutes les couches d'analyse."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QGridLayout(self)

        self.header_label = QLabel("Sélectionnez une entreprise")
        self.header_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.chart = ChartViewWidget()
        self.quant_hud = QuantHudWidget()

        self.fundamentals_label = QLabel("Fondamentaux : —")
        self.fundamentals_label.setWordWrap(True)

        self.sentiment_label = QLabel("Sentiment : —")
        self.sentiment_label.setWordWrap(True)

        self.summary_label = QLabel("Résumé IA : —")
        self.summary_label.setWordWrap(True)

        layout.addWidget(self.header_label, 0, 0, 1, 3)
        layout.addWidget(self.chart, 1, 0, 2, 2)
        layout.addWidget(self.quant_hud, 1, 2, 2, 1)
        layout.addWidget(self.fundamentals_label, 3, 0)
        layout.addWidget(self.sentiment_label, 3, 1)
        layout.addWidget(self.summary_label, 3, 2)

    def load_company(
        self,
        company: CompanyInfo,
        price_features_df,
        fundamentals: FundamentalsSnapshot,
        quant_score: QuantScore,
        sentiment: SentimentResult,
        summary: CompanySummary,
    ) -> None:
        """Recharge entièrement la page pour une nouvelle entreprise sélectionnée."""
        self.header_label.setText(f"{company.name} ({company.ticker}) — {company.sector.value}")

        self.chart.plot(price_features_df)
        self.quant_hud.update_score(quant_score)

        self.fundamentals_label.setText(
            "Fondamentaux :\n"
            f"PER: {fundamentals.trailing_pe or '—'}  |  "
            f"ROE: {fundamentals.return_on_equity or '—'}  |  "
            f"Marge nette: {fundamentals.profit_margins or '—'}"
        )

        self.sentiment_label.setText(
            f"Sentiment : {sentiment.label} ({sentiment.global_sentiment:+.2f}) "
            f"— {sentiment.n_headlines_analyzed} news analysées"
        )

        self.summary_label.setText(f"Résumé IA ({summary.source}) :\n{summary.overview}")
