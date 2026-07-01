"""Gestion du moteur SQLAlchemy et des sessions pour StockInvest Pro."""

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from data.schema import Base
from utils.logger import logger


class Database:
    """
    Point d'entrée unique vers la base de données.

    Compatible SQLite (défaut) et PostgreSQL : seule l'URL de connexion
    change, aucune autre modification n'est nécessaire ailleurs dans le code.
    """

    def __init__(self, database_url: str = "sqlite:///stockinvest.db", echo: bool = False) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = create_engine(database_url, echo=echo, connect_args=connect_args)
        self._session_factory: sessionmaker[Session] = sessionmaker(bind=self.engine, expire_on_commit=False)
        logger.info(f"Base de données initialisée: {database_url}")

    def create_all_tables(self) -> None:
        """Crée toutes les tables définies dans data/schema.py si elles n'existent pas."""
        Base.metadata.create_all(self.engine)
        logger.info("Tables créées/vérifiées avec succès")

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """
        Fournit une session transactionnelle avec commit/rollback automatique.

        Usage:
            with db.session_scope() as session:
                session.add(obj)
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Rollback de session suite à une exception")
            raise
        finally:
            session.close()
