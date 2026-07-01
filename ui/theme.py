"""
Thème visuel 'Modern Terminal' — design system centralisé.

Inspiré TradingView (simplicité) / Notion (clarté) / Bloomberg (densité
organisée). Priorité à la hiérarchie visuelle et à la réduction du bruit :
coins arrondis, hover subtils, transitions courtes, dégradé léger de fond.
"""

# --- Palette de base ---
BACKGROUND_TOP = "#0B0C10"
BACKGROUND_BOTTOM = "#111318"
SURFACE = "#15171C"
SURFACE_ELEVATED = "#1B1E24"  # cartes au-dessus du fond (léger contraste)
BORDER = "#2A2D35"
BORDER_SUBTLE = "#20232A"

TEXT_PRIMARY = "#E6E8EB"
TEXT_SECONDARY = "#8A8F98"
TEXT_MUTED = "#5D6169"

ACCENT_GREEN = "#1FCE7A"
ACCENT_RED = "#E5484D"
ACCENT_BLUE = "#3B82F6"
ACCENT_AMBER = "#F59E0B"

FONT_FAMILY = "JetBrains Mono"

# --- Rayon de coin standard pour toutes les "cartes" ---
RADIUS_CARD = 10
RADIUS_SMALL = 6

# --- Durée d'animation standard (utilisée par QPropertyAnimation côté widgets) ---
TRANSITION_MS = 180

# --- Points de rupture responsive (largeur fenêtre en px) ---
BREAKPOINT_WIDE = 1400   # 3 colonnes : Market / Chart / HUD
BREAKPOINT_MEDIUM = 900  # 2 colonnes : Market + Chart, HUD en panneau repliable
# < BREAKPOINT_MEDIUM : 1 colonne, navigation par onglets uniquement


def build_qss(background: str = BACKGROUND_TOP, surface: str = SURFACE, border: str = BORDER) -> str:
    """Génère la feuille QSS complète, paramétrable depuis config.ini."""
    return f"""
    QWidget {{
        background-color: {background};
        color: {TEXT_PRIMARY};
        font-family: '{FONT_FAMILY}', 'Consolas', monospace;
        font-size: 12px;
    }}

    QMainWindow {{
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 {BACKGROUND_TOP}, stop:1 {BACKGROUND_BOTTOM}
        );
    }}

    /* --- Cartes : coins arrondis, léger contraste, hover discret --- */
    QFrame#card, QFrame#surface {{
        background-color: {SURFACE_ELEVATED};
        border: 1px solid {border};
        border-radius: {RADIUS_CARD}px;
    }}

    QFrame#card:hover {{
        border: 1px solid {ACCENT_BLUE};
    }}

    QTableWidget, QTreeWidget, QListWidget {{
        background-color: {surface};
        border: 1px solid {border};
        border-radius: {RADIUS_SMALL}px;
        gridline-color: {border};
        selection-background-color: {ACCENT_BLUE};
    }}

    QHeaderView::section {{
        background-color: {surface};
        color: {TEXT_SECONDARY};
        border: none;
        border-bottom: 1px solid {border};
        padding: 6px;
        font-weight: 600;
    }}

    /* --- Onglets épurés, sans surcharge visuelle --- */
    QTabWidget::pane {{
        border: 1px solid {border};
        border-radius: {RADIUS_SMALL}px;
        background-color: {surface};
        top: -1px;
    }}

    QTabBar::tab {{
        background-color: transparent;
        color: {TEXT_SECONDARY};
        padding: 8px 18px;
        border: none;
        border-bottom: 2px solid transparent;
        margin-right: 4px;
    }}

    QTabBar::tab:selected {{
        color: {TEXT_PRIMARY};
        border-bottom: 2px solid {ACCENT_BLUE};
    }}

    QTabBar::tab:hover {{
        color: {TEXT_PRIMARY};
    }}

    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background-color: {surface};
        border: 1px solid {border};
        border-radius: {RADIUS_SMALL}px;
        padding: 6px 10px;
        color: {TEXT_PRIMARY};
    }}

    QLineEdit:focus, QComboBox:focus {{
        border: 1px solid {ACCENT_BLUE};
    }}

    QPushButton {{
        background-color: {surface};
        border: 1px solid {border};
        border-radius: {RADIUS_SMALL}px;
        padding: 7px 16px;
        color: {TEXT_PRIMARY};
    }}

    QPushButton:hover {{
        border: 1px solid {ACCENT_BLUE};
        background-color: {SURFACE_ELEVATED};
    }}

    QPushButton:pressed {{
        background-color: {ACCENT_BLUE};
    }}

    QPushButton#primary {{
        background-color: {ACCENT_BLUE};
        border: none;
        font-weight: 600;
    }}

    QPushButton#primary:hover {{
        background-color: #2563EB;
    }}

    QPushButton#ghost {{
        background-color: transparent;
        border: none;
        color: {TEXT_SECONDARY};
    }}

    QPushButton#ghost:hover {{
        color: {TEXT_PRIMARY};
        background-color: {SURFACE_ELEVATED};
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background: {border};
        border-radius: 4px;
        min-height: 24px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {ACCENT_BLUE};
    }}

    QSplitter::handle {{
        background-color: transparent;
    }}

    QStatusBar {{
        background-color: {surface};
        border-top: 1px solid {border};
        color: {TEXT_SECONDARY};
    }}

    QLabel.positive {{
        color: {ACCENT_GREEN};
    }}

    QLabel.negative {{
        color: {ACCENT_RED};
    }}

    QLabel.muted {{
        color: {TEXT_MUTED};
    }}
    """


def card_style(radius: int = RADIUS_CARD, surface: str = SURFACE_ELEVATED, border: str = BORDER) -> str:
    """Style QSS ponctuel pour un widget individuel affiché comme une 'carte'."""
    return (
        f"background-color: {surface}; border: 1px solid {border}; "
        f"border-radius: {radius}px; padding: 12px;"
    )


def color_for_change(value: float) -> str:
    """Retourne la couleur adaptée pour afficher une variation (vert/rouge)."""
    if value > 0:
        return ACCENT_GREEN
    if value < 0:
        return ACCENT_RED
    return TEXT_SECONDARY


def trend_arrow(value: float, threshold: float = 0.5) -> str:
    """Retourne une flèche de tendance ↑ / ↓ / ↔ selon la valeur (ex: score - 50)."""
    if value > threshold:
        return "↑"
    if value < -threshold:
        return "↓"
    return "↔"


class LayoutMode:
    """Modes de layout responsive, calculés à partir de la largeur de fenêtre."""

    WIDE = "wide"       # >= BREAKPOINT_WIDE : 3 colonnes
    MEDIUM = "medium"    # >= BREAKPOINT_MEDIUM : 2 colonnes + HUD repliable
    NARROW = "narrow"    # < BREAKPOINT_MEDIUM : 1 colonne, navigation par onglets

    @staticmethod
    def from_width(width: int) -> str:
        if width >= BREAKPOINT_WIDE:
            return LayoutMode.WIDE
        if width >= BREAKPOINT_MEDIUM:
            return LayoutMode.MEDIUM
        return LayoutMode.NARROW