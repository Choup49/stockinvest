"""
Barre de recherche universelle avec autocomplétion nom d'entreprise -> ticker.

Permet à l'utilisateur de taper "Apple" et de voir apparaître une liste
déroulante proposant "AAPL — Apple Inc. (NASDAQ)" à sélectionner, sans
avoir besoin de connaître le symbole boursier à l'avance.
"""

import uuid

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.models import TickerSearchResult
from core.orchestrator import MarketOrchestrator
from ui.theme import BORDER, SURFACE, TEXT_SECONDARY
from ui.workers import TickerSearchWorker

DEBOUNCE_MS = 300  # délai après la dernière frappe avant de lancer la recherche
MIN_QUERY_LENGTH = 2


class SearchBarWidget(QWidget):
    """
    Champ de recherche + popup de suggestions.

    Signaux :
        ticker_chosen(str) — émis quand l'utilisateur sélectionne un résultat
            (clic ou flèches + Entrée), ou valide un texte qui ressemble
            déjà à un ticker existant.
    """

    ticker_chosen = Signal(str)

    def __init__(self, orchestrator: MarketOrchestrator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.orchestrator = orchestrator
        self._active_request_id: str | None = None
        self._search_worker: TickerSearchWorker | None = None
        self._last_results: list[TickerSearchResult] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Recherche universelle (ex: Apple, Tesla, AAPL...)")
        layout.addWidget(self.input)

        self.suggestions_list = QListWidget()
        self.suggestions_list.setWindowFlags(Qt.WindowType.ToolTip)
        self.suggestions_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.suggestions_list.setStyleSheet(
            f"""
            QListWidget {{
                background-color: {SURFACE};
                border: 1px solid {BORDER};
                color: white;
                outline: none;
            }}
            QListWidget::item {{
                padding: 6px 10px;
            }}
            QListWidget::item:selected {{
                background-color: #3B82F6;
            }}
            """
        )
        self.suggestions_list.hide()

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._trigger_search)

        self.input.textEdited.connect(self._on_text_edited)
        self.input.returnPressed.connect(self._on_return_pressed)
        self.suggestions_list.itemClicked.connect(self._on_suggestion_clicked)

    # ------------------------------------------------------------------
    # SAISIE UTILISATEUR
    # ------------------------------------------------------------------

    def _on_text_edited(self, text: str) -> None:
        text = text.strip()
        if len(text) < MIN_QUERY_LENGTH:
            self._hide_suggestions()
            return
        self._debounce_timer.start(DEBOUNCE_MS)

    def _trigger_search(self) -> None:
        query = self.input.text().strip()
        if len(query) < MIN_QUERY_LENGTH:
            return

        request_id = str(uuid.uuid4())
        self._active_request_id = request_id

        self._search_worker = TickerSearchWorker(self.orchestrator, query, request_id)
        self._search_worker.finished_ok.connect(self._on_search_results)
        self._search_worker.failed.connect(self._on_search_failed)
        self._search_worker.start()

    def _on_search_results(self, results: list[TickerSearchResult], request_id: str) -> None:
        # Ignore les résultats d'une requête obsolète (l'utilisateur a retapé entre-temps)
        if request_id != self._active_request_id:
            return

        self._last_results = results
        if not results:
            self._hide_suggestions()
            return

        self.suggestions_list.clear()
        for result in results:
            label = f"{result.symbol} — {result.name}"
            if result.exchange:
                label += f" ({result.exchange})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, result.symbol)
            self.suggestions_list.addItem(item)

        self._show_suggestions()

    def _on_search_failed(self, message: str, request_id: str) -> None:
        if request_id != self._active_request_id:
            return
        self._hide_suggestions()

    # ------------------------------------------------------------------
    # SÉLECTION
    # ------------------------------------------------------------------

    def _on_suggestion_clicked(self, item: QListWidgetItem) -> None:
        symbol = item.data(Qt.ItemDataRole.UserRole)
        self._select_ticker(symbol)

    def _on_return_pressed(self) -> None:
        # Si des suggestions sont affichées, on prend la première (meilleur match)
        # plutôt que le texte brut tapé par l'utilisateur, qui n'est probablement
        # pas un ticker valide s'il s'agit d'un nom d'entreprise.
        if self.suggestions_list.isVisible() and self.suggestions_list.count() > 0:
            first_item = self.suggestions_list.item(0)
            symbol = first_item.data(Qt.ItemDataRole.UserRole)
            self._select_ticker(symbol)
            return

        # Aucune suggestion chargée : on tente le texte tel quel, en majuscules,
        # au cas où l'utilisateur a directement tapé un ticker valide et validé
        # avant la fin du débounce.
        raw_text = self.input.text().strip().upper()
        if raw_text:
            self._select_ticker(raw_text)

    def _select_ticker(self, symbol: str) -> None:
        self._hide_suggestions()
        self.input.setText(symbol)
        self.ticker_chosen.emit(symbol)

    # ------------------------------------------------------------------
    # AFFICHAGE POPUP
    # ------------------------------------------------------------------

    def _show_suggestions(self) -> None:
        global_pos = self.input.mapToGlobal(self.input.rect().bottomLeft())
        self.suggestions_list.move(global_pos)
        self.suggestions_list.resize(max(self.input.width(), 320), min(200, 32 * self.suggestions_list.count()))
        self.suggestions_list.show()
        self.suggestions_list.raise_()

    def _hide_suggestions(self) -> None:
        self.suggestions_list.hide()

    def focusOutEvent(self, event) -> None:
        # Petit délai pour laisser le clic sur une suggestion s'exécuter
        # avant de fermer le popup (sinon le clic est perdu).
        QTimer.singleShot(150, self._hide_suggestions)
        super().focusOutEvent(event)