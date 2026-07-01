"""Page Quant Engine : tableau des scores multi-facteurs, filtres, export CSV."""

import csv

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.data_table import DataTableWidget

COLUMNS = ["Ticker", "Score", "Value", "Growth", "Quality", "Momentum", "Risk", "Technical"]


class QuantEnginePage(QWidget):
    """Vue tabulaire de tous les scores quant, avec filtres pays/secteur/score min et export CSV."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        filters_layout = QHBoxLayout()
        self.sector_filter = QComboBox()
        self.sector_filter.addItem("Tous secteurs")
        self.country_filter = QComboBox()
        self.country_filter.addItem("Tous pays")

        self.min_score_filter = QDoubleSpinBox()
        self.min_score_filter.setRange(0, 100)
        self.min_score_filter.setValue(0)
        self.min_score_filter.setPrefix("Score min: ")

        self.export_button = QPushButton("Exporter CSV")
        self.export_button.clicked.connect(self._export_csv)

        filters_layout.addWidget(QLabel("Filtres :"))
        filters_layout.addWidget(self.sector_filter)
        filters_layout.addWidget(self.country_filter)
        filters_layout.addWidget(self.min_score_filter)
        filters_layout.addStretch()
        filters_layout.addWidget(self.export_button)

        self.table = DataTableWidget(COLUMNS)

        layout.addLayout(filters_layout)
        layout.addWidget(self.table)

        self.sector_filter.currentTextChanged.connect(self._apply_filters)
        self.country_filter.currentTextChanged.connect(self._apply_filters)
        self.min_score_filter.valueChanged.connect(self._apply_filters)

        self._all_rows: list[dict] = []

    def load_scores(self, rows: list[dict]) -> None:
        """
        Args:
            rows: [{"ticker", "name", "sector", "country", "global_score",
                    "value", "growth", "quality", "momentum", "risk", "technical"}, ...]
        """
        self._all_rows = rows

        sectors = sorted({r.get("sector", "Unknown") for r in rows})
        countries = sorted({r.get("country", "Unknown") for r in rows if r.get("country")})

        self.sector_filter.blockSignals(True)
        self.country_filter.blockSignals(True)
        self.sector_filter.clear()
        self.sector_filter.addItem("Tous secteurs")
        self.sector_filter.addItems(sectors)
        self.country_filter.clear()
        self.country_filter.addItem("Tous pays")
        self.country_filter.addItems(countries)
        self.sector_filter.blockSignals(False)
        self.country_filter.blockSignals(False)

        self._apply_filters()

    def _apply_filters(self) -> None:
        sector = self.sector_filter.currentText()
        country = self.country_filter.currentText()
        min_score = self.min_score_filter.value()

        def predicate(row: dict) -> bool:
            if sector != "Tous secteurs" and row.get("sector") != sector:
                return False
            if country != "Tous pays" and row.get("country") != country:
                return False
            if row.get("global_score", 0) < min_score:
                return False
            return True

        filtered = [r for r in self._all_rows if predicate(r)]
        # Adapte les clés au format attendu par DataTableWidget (score au lieu de global_score)
        display_rows = [{**r, "score": r.get("global_score", 0)} for r in filtered]
        self.table.load_rows(display_rows)

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Exporter en CSV", "quant_scores.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(self._all_rows[0].keys()) if self._all_rows else [])
            writer.writeheader()
            writer.writerows(self._all_rows)
