"""Schéma ORM SQLAlchemy pour la persistance StockInvest Pro."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Boolean, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CompanyRecord(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str] = mapped_column(String(64))
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(32), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    price_bars: Mapped[list["PriceBar"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    quant_scores: Mapped[list["QuantScoreRecord"]] = relationship(back_populates="company", cascade="all, delete-orphan")


class PriceBar(Base):
    __tablename__ = "price_bars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    date: Mapped[datetime] = mapped_column(DateTime, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    adj_close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)

    company: Mapped["CompanyRecord"] = relationship(back_populates="price_bars")


class QuantScoreRecord(Base):
    __tablename__ = "quant_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    global_score: Mapped[float] = mapped_column(Float)
    value_score: Mapped[float] = mapped_column(Float)
    growth_score: Mapped[float] = mapped_column(Float)
    quality_score: Mapped[float] = mapped_column(Float)
    momentum_score: Mapped[float] = mapped_column(Float)
    risk_score: Mapped[float] = mapped_column(Float)
    technical_score: Mapped[float] = mapped_column(Float)
    strengths: Mapped[dict] = mapped_column(JSON, default=list)
    weaknesses: Mapped[dict] = mapped_column(JSON, default=list)

    company: Mapped["CompanyRecord"] = relationship(back_populates="quant_scores")


class DataQualityLog(Base):
    __tablename__ = "data_quality_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    rows_before: Mapped[int] = mapped_column(Integer)
    rows_after: Mapped[int] = mapped_column(Integer)
    rows_dropped: Mapped[int] = mapped_column(Integer)
    drop_reasons: Mapped[dict] = mapped_column(JSON, default=dict)
    passed_liquidity_filter: Mapped[bool] = mapped_column(Boolean)
