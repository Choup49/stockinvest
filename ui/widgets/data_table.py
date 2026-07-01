"""Table de données générique réutilisable (Quant Engine, Command Center)."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem, QWidget


class DataTableWidget(QTableWidget):
    """
    Table générique pilotée par des dicts, avec tri par colonne et
    émission de row_selected pour piloter les autres panneaux.
    """

    row_selected = Signal(dict)

    def __init__(self, columns: list[str], parent: QWidget | None = None) -> None:
        super().__init__(0, len(columns), parent)
        self.columns = columns
        self.setHorizontalHeaderLabels(columns)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSortingEnabled(True)
        self._rows: list[dict] = []
        self.cellClicked.connect(self._on_cell_clicked)

    def load_rows(self, rows: list[dict]) -> None:
        """
        Args:
            rows: liste de dicts, dont les clés matchent (en snake_case)
                les colonnes fournies au constructeur.
        """
        self._rows = rows
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))

        for i, row in enumerate(rows):
            for j, col in enumerate(self.columns):
                key = col.lower().replace(" ", "_").replace("%", "pct")
                value = row.get(key, "")
                display = f"{value:.2f}" if isinstance(value, float) else str(value)
                item = QTableWidgetItem(display)
                item.setData(Qt.ItemDataRole.UserRole, row)
                self.setItem(i, j, item)

        self.setSortingEnabled(True)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        item = self.item(row, col)
        if item:
            row_data = item.data(Qt.ItemDataRole.UserRole)
            if row_data:
                self.row_selected.emit(row_data)

    def apply_filter(self, predicate) -> None:
        """Réapplique load_rows en filtrant self._rows avec le prédicat fourni."""
        filtered = [r for r in self._rows if predicate(r)]
        self.load_rows(filtered)
