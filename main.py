"""
Point d'entrée principal de StockInvest Pro.

Lance l'application desktop : initialise config, logger, base de données,
orchestrateur, puis affiche la fenêtre principale PySide6.
"""

import sys

from PySide6.QtWidgets import QApplication

from core.orchestrator import MarketOrchestrator
from data.database import Database
from data.repository import MarketDataRepository
from ui.main_window import MainWindow
from utils.config_loader import ConfigLoader
from utils.logger import logger


def main() -> int:
    logger.info("Démarrage de StockInvest Pro")

    config = ConfigLoader().load()

    database = Database(database_url=config.database_url)
    database.create_all_tables()
    repository = MarketDataRepository(database)

    orchestrator = MarketOrchestrator(
        repository=repository,
        min_dollar_volume=config.min_dollar_volume,
        default_period=config.default_period,
        use_openai=config.use_openai,
        openai_api_key=config.openai_api_key,
    )

    app = QApplication(sys.argv)
    app.setApplicationName("StockInvest Pro")

    theme_colors = {
        "background": config.theme_background,
        "surface": config.theme_surface,
        "border": config.theme_border,
    }

    window = MainWindow(
        repository=repository,
        orchestrator=orchestrator,
        theme_colors=theme_colors,
        default_watchlist=config.default_watchlist,
    )
    window.show()

    logger.info("Interface affichée, entrée dans la boucle événementielle Qt")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())