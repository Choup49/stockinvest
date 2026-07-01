"""
Repository haut niveau : isole toute la logique CRUD de la base de données
du reste de l'application. quant/, ai/, ui/ ne doivent jamais importer
data/schema.py ou data/database.py directement — uniquement ce module.
"""

import pandas as pd
from sqlalchemy import select

from core.models import CompanyInfo, QualityReport, QuantScore
from data.database import Database
from data.schema import CompanyRecord, DataQualityLog, PriceBar, QuantScoreRecord
from utils.logger import logger


class MarketDataRepository:
    """Façade CRUD pour toutes les entités persistées."""

    def __init__(self, database: Database) -> None:
        self.db = database

    def upsert_company(self, info: CompanyInfo) -> int:
        """Insère ou met à jour une entreprise, retourne son id interne."""
        with self.db.session_scope() as session:
            existing = session.execute(
                select(CompanyRecord).where(CompanyRecord.ticker == info.ticker)
            ).scalar_one_or_none()

            if existing:
                existing.name = info.name
                existing.sector = info.sector.value
                existing.industry = info.industry
                existing.country = info.country
                existing.market_cap = info.market_cap
                existing.currency = info.currency
                existing.exchange = info.exchange
                session.flush()
                return existing.id

            record = CompanyRecord(
                ticker=info.ticker,
                name=info.name,
                sector=info.sector.value,
                industry=info.industry,
                country=info.country,
                market_cap=info.market_cap,
                currency=info.currency,
                exchange=info.exchange,
            )
            session.add(record)
            session.flush()
            logger.debug(f"Nouvelle entreprise persistée: {info.ticker} (id={record.id})")
            return record.id

    def save_price_history(self, company_id: int, df: pd.DataFrame) -> int:
        """Persiste un DataFrame OHLCV, remplace les données existantes pour ce company_id."""
        with self.db.session_scope() as session:
            session.query(PriceBar).filter(PriceBar.company_id == company_id).delete()

            bars = [
                PriceBar(
                    company_id=company_id,
                    date=index.to_pydatetime(),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    adj_close=float(row["Adj Close"]),
                    volume=float(row["Volume"]),
                )
                for index, row in df.iterrows()
            ]
            session.bulk_save_objects(bars)
            logger.debug(f"{len(bars)} barres de prix persistées (company_id={company_id})")
            return len(bars)

    def save_quality_report(self, report: QualityReport) -> None:
        """Persiste un rapport de qualité de nettoyage."""
        with self.db.session_scope() as session:
            log = DataQualityLog(
                ticker=report.ticker,
                rows_before=report.rows_before,
                rows_after=report.rows_after,
                rows_dropped=report.rows_dropped,
                drop_reasons=report.drop_reasons,
                passed_liquidity_filter=report.passed_liquidity_filter,
            )
            session.add(log)

    def save_quant_score(self, company_id: int, score: QuantScore) -> None:
        """Persiste un score quantitatif multi-facteurs."""
        from core.enums import FactorType

        with self.db.session_scope() as session:
            record = QuantScoreRecord(
                company_id=company_id,
                global_score=score.global_score,
                value_score=score.factor_scores[FactorType.VALUE].zscore,
                growth_score=score.factor_scores[FactorType.GROWTH].zscore,
                quality_score=score.factor_scores[FactorType.QUALITY].zscore,
                momentum_score=score.factor_scores[FactorType.MOMENTUM].zscore,
                risk_score=score.factor_scores[FactorType.RISK].zscore,
                technical_score=score.factor_scores[FactorType.TECHNICAL].zscore,
                strengths=score.strengths,
                weaknesses=score.weaknesses,
            )
            session.add(record)

    def get_price_history(self, ticker: str) -> pd.DataFrame:
        """Récupère l'historique de prix persisté pour un ticker, trié par date."""
        with self.db.session_scope() as session:
            company = session.execute(
                select(CompanyRecord).where(CompanyRecord.ticker == ticker)
            ).scalar_one_or_none()
            if not company:
                return pd.DataFrame()

            rows = session.execute(
                select(PriceBar).where(PriceBar.company_id == company.id).order_by(PriceBar.date)
            ).scalars().all()

            if not rows:
                return pd.DataFrame()

            data = {
                "Date": [r.date for r in rows],
                "Open": [r.open for r in rows],
                "High": [r.high for r in rows],
                "Low": [r.low for r in rows],
                "Close": [r.close for r in rows],
                "Adj Close": [r.adj_close for r in rows],
                "Volume": [r.volume for r in rows],
            }
            return pd.DataFrame(data).set_index("Date")

    def get_all_tickers(self) -> list[str]:
        """Retourne tous les tickers connus en base."""
        with self.db.session_scope() as session:
            rows = session.execute(select(CompanyRecord.ticker)).scalars().all()
            return list(rows)

    def get_latest_quant_scores(self) -> list[dict]:
        """Retourne le dernier score quant de chaque entreprise, sous forme de dicts (pour l'UI)."""
        with self.db.session_scope() as session:
            companies = session.execute(select(CompanyRecord)).scalars().all()
            results = []
            for company in companies:
                if not company.quant_scores:
                    continue
                latest = max(company.quant_scores, key=lambda s: s.computed_at)
                results.append(
                    {
                        "ticker": company.ticker,
                        "name": company.name,
                        "sector": company.sector,
                        "global_score": latest.global_score,
                        "value": latest.value_score,
                        "growth": latest.growth_score,
                        "quality": latest.quality_score,
                        "momentum": latest.momentum_score,
                        "risk": latest.risk_score,
                        "technical": latest.technical_score,
                    }
                )
            return results
