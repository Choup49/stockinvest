"""
Command Palette (Cmd+K / Ctrl+K) — navigation rapide façon éditeur de code
moderne (VS Code, Notion, Linear...).

Permet de :
- sauter directement vers une page (Command Center, Deep Dive, Quant Engine, Simulator)
- rechercher un ticker et l'ouvrir en Deep Dive
sans passer par la souris.
"""

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from core.orchestrator import MarketOrchestrator
from ui.theme import BORDER, SURFACE_ELEVATED, TEXT_SECONDARY
from ui.workers import TickerSearchWorker

DEBOUNCE_MS = 250
MIN_QUERY_LENGTH = 2


@dataclass
class PaletteAction:
    """Une entrée statique de la palette (navigation vers une page)."""

    label: str
    action_id: str  # ex: "page:command_center"


class CommandPaletteDialog(QDialog):
    """
    Fenêtre modale centrale déclenchée par Cmd+K / Ctrl+K.

    Signaux :
        page_requested(str) — l'utilisateur a choisi une page (action_id).
        ticker_requested(str) — l'utilisateur a choisi un ticker.
    """

    page_requested = Signal(str)
    ticker_requested = Signal(str)

    STATIC_ACTIONS: list[PaletteAction] = [
        PaletteAction("📊  Command Center", "page:command_center"),
        PaletteAction("🔍  Deep Dive", "page:deep_dive"),
        PaletteAction("🧮  Quant Engine", "page:quant_engine"),
        PaletteAction("⚙️  Simulator", "page:simulator"),
    ]

    def __init__(self, orchestrator: MarketOrchestrator, parent=None) -> None:
        super().__init__(parent)
        self.orchestrator = orchestrator
        self._active_request_id: str | None = None
        self._search_worker: TickerSearchWorker | None = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedWidth(560)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {SURFACE_ELEVATED};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
            QLineEdit {{
                background-color: transparent;
                border: none;
                border-bottom: 1px solid {BORDER};
                border-radius: 0;
                padding: 14px 16px;
                font-size: 15px;
            }}
            QListWidget {{
                background-color: transparent;
                border: none;
                padding: 6px;
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-radius: 6px;
            }}
            QListWidget::item:selected {{
                background-color: #3B82F6;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(0)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Tapez une commande ou un ticker (ex: 'Apple', 'Simulator')...")
        layout.addWidget(self.input)

        self.results_list = QListWidget()
        layout.addWidget(self.results_list)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._run_ticker_search)

        self.input.textEdited.connect(self._on_text_edited)
        self.input.returnPressed.connect(self._on_return_pressed)
        self.results_list.itemActivated.connect(self._on_item_activated)

        self._populate_static_actions()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.input.clear()
        self.input.setFocus()
        self._populate_static_actions()
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + 120
            self.move(x, y)

    # ------------------------------------------------------------------
    # CONTENU DE LA LISTE
    # ------------------------------------------------------------------

    def _populate_static_actions(self) -> None:
        self.results_list.clear()
        for action in self.STATIC_ACTIONS:
            item = QListWidgetItem(action.label)
            item.setData(Qt.ItemDataRole.UserRole, ("page", action.action_id))
            self.results_list.addItem(item)
        if self.results_list.count():
            self.results_list.setCurrentRow(0)

    def _on_text_edited(self, text: str) -> None:
        text = text.strip()
        if len(text) < MIN_QUERY_LENGTH:
            self._populate_static_actions()
            return
        self._debounce_timer.start(DEBOUNCE_MS)

    def _run_ticker_search(self) -> None:
        query = self.input.text().strip()
        if len(query) < MIN_QUERY_LENGTH:
            return

        import uuid

        request_id = str(uuid.uuid4())
        self._active_request_id = request_id

        self._search_worker = TickerSearchWorker(self.orchestrator, query, request_id)
        self._search_worker.finished_ok.connect(self._on_search_results)
        self._search_worker.start()

    def _on_search_results(self, results: list, request_id: str) -> None:
        if request_id != self._active_request_id:
            return

        self.results_list.clear()
        for result in results:
            label = f"📈  {result.symbol} — {result.name}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, ("ticker", result.symbol))
            self.results_list.addItem(item)

        if not results:
            item = QListWidgetItem("Aucun résultat")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results_list.addItem(item)
        else:
            self.results_list.setCurrentRow(0)

    # ------------------------------------------------------------------
    # SÉLECTION
    # ------------------------------------------------------------------

    def _on_return_pressed(self) -> None:
        item = self.results_list.currentItem()
        if item:
            self._on_item_activated(item)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, value = data
        self.close()
        if kind == "page":
            self.page_requested.emit(value)
        elif kind == "ticker":
            self.ticker_requested.emit(value)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        if event.key() == Qt.Key.Key_Down:
            self.results_list.setCurrentRow(
                min(self.results_list.currentRow() + 1, self.results_list.count() - 1)
            )
            return
        if event.key() == Qt.Key.Key_Up:
            self.results_list.setCurrentRow(max(self.results_list.currentRow() - 1, 0))
            return
        super().keyPressEvent(event)