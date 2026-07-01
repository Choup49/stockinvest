"""Configuration centralisée du logger loguru pour StockInvest Pro."""

import sys
from pathlib import Path

from loguru import logger

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - {message}",
)
logger.add(
    LOG_DIR / "stockinvest_{time:YYYY-MM-DD}.log",
    level="DEBUG",
    rotation="1 day",
    retention="14 days",
)

__all__ = ["logger"]
