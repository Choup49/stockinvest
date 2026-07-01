"""Thème visuel 'Institutional Dark Terminal' — feuille de style QSS centralisée."""

BACKGROUND = "#0B0C10"
SURFACE = "#15171C"
BORDER = "#2A2D35"
TEXT_PRIMARY = "#E6E8EB"
TEXT_SECONDARY = "#8A8F98"
ACCENT_GREEN = "#1FCE7A"
ACCENT_RED = "#E5484D"
ACCENT_BLUE = "#3B82F6"
FONT_FAMILY = "JetBrains Mono"


def build_qss(background: str = BACKGROUND, surface: str = SURFACE, border: str = BORDER) -> str:
    """Génère la feuille QSS complète, paramétrable depuis config.ini."""
    return f"""
    QWidget {{
        background-color: {background};
        color: {TEXT_PRIMARY};
        font-family: '{FONT_FAMILY}', 'Consolas', monospace;
        font-size: 12px;
    }}

    QMainWindow {{
        background-color: {background};
    }}

    QFrame#surface, QTableWidget, QTreeWidget {{
        background-color: {surface};
        border: 1px solid {border};
        border-radius: 4px;
    }}

    QTableWidget {{
        gridline-color: {border};
        selection-background-color: {ACCENT_BLUE};
    }}

    QHeaderView::section {{
        background-color: {surface};
        color: {TEXT_SECONDARY};
        border: none;
        border-bottom: 1px solid {border};
        padding: 4px;
        font-weight: bold;
    }}

    QTabWidget::pane {{
        border: 1px solid {border};
        background-color: {surface};
    }}

    QTabBar::tab {{
        background-color: {background};
        color: {TEXT_SECONDARY};
        padding: 8px 16px;
        border: 1px solid {border};
        border-bottom: none;
    }}

    QTabBar::tab:selected {{
        background-color: {surface};
        color: {TEXT_PRIMARY};
        border-bottom: 2px solid {ACCENT_BLUE};
    }}

    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background-color: {surface};
        border: 1px solid {border};
        border-radius: 3px;
        padding: 4px 6px;
        color: {TEXT_PRIMARY};
    }}

    QPushButton {{
        background-color: {surface};
        border: 1px solid {border};
        border-radius: 3px;
        padding: 6px 14px;
        color: {TEXT_PRIMARY};
    }}

    QPushButton:hover {{
        border: 1px solid {ACCENT_BLUE};
    }}

    QPushButton:pressed {{
        background-color: {ACCENT_BLUE};
    }}

    QScrollBar:vertical {{
        background: {background};
        width: 10px;
    }}

    QScrollBar::handle:vertical {{
        background: {border};
        border-radius: 5px;
        min-height: 20px;
    }}

    QLabel.positive {{
        color: {ACCENT_GREEN};
    }}

    QLabel.negative {{
        color: {ACCENT_RED};
    }}
    """


def color_for_change(value: float) -> str:
    """Retourne la couleur adaptée pour afficher une variation (vert/rouge)."""
    if value > 0:
        return ACCENT_GREEN
    if value < 0:
        return ACCENT_RED
    return TEXT_SECONDARY
