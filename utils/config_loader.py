"""Chargement et validation de config.ini pour StockInvest Pro."""

import configparser
from dataclasses import dataclass
from pathlib import Path

from utils.logger import logger

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.ini"


@dataclass
class AppConfig:
    """Configuration typée de l'application, dérivée de config.ini."""

    database_url: str
    min_dollar_volume: float
    default_period: str
    default_watchlist: list[str]
    openai_api_key: str | None
    use_openai: bool
    theme_background: str
    theme_surface: str
    theme_border: str


class ConfigLoader:
    """Charge config.ini et expose un AppConfig validé et typé."""

    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
        self.config_path = config_path
        self._parser = configparser.ConfigParser()

    def load(self) -> AppConfig:
        if not self.config_path.exists():
            logger.warning(f"{self.config_path} introuvable, création d'une config par défaut")
            self._write_default_config()

        self._parser.read(self.config_path)

        db = self._parser["database"]
        pipeline = self._parser["pipeline"]
        ai = self._parser["ai"]
        theme = self._parser["theme"]

        watchlist_raw = pipeline.get(
            "default_watchlist", "AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,JPM,V,UNH"
        )
        default_watchlist = [t.strip().upper() for t in watchlist_raw.split(",") if t.strip()]

        config = AppConfig(
            database_url=db.get("url", "sqlite:///stockinvest.db"),
            min_dollar_volume=pipeline.getfloat("min_dollar_volume", 250_000.0),
            default_period=pipeline.get("default_period", "2y"),
            default_watchlist=default_watchlist,
            openai_api_key=ai.get("openai_api_key", fallback=None) or None,
            use_openai=ai.getboolean("use_openai", False),
            theme_background=theme.get("background", "#0B0C10"),
            theme_surface=theme.get("surface", "#15171C"),
            theme_border=theme.get("border", "#2A2D35"),
        )
        logger.info("Configuration chargée avec succès")
        return config

    def _write_default_config(self) -> None:
        self._parser["database"] = {"url": "sqlite:///stockinvest.db"}
        self._parser["pipeline"] = {
            "min_dollar_volume": "250000",
            "default_period": "2y",
            "default_watchlist": "AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,JPM,V,UNH",
        }
        self._parser["ai"] = {"use_openai": "false", "openai_api_key": ""}
        self._parser["theme"] = {
            "background": "#0B0C10",
            "surface": "#15171C",
            "border": "#2A2D35",
        }
        with open(self.config_path, "w") as f:
            self._parser.write(f)