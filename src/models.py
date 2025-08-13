from datetime import date, datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import (
    Integer, String, Float, ForeignKey, Text, UniqueConstraint,
    Date as SA_Date, DateTime as SA_DateTime
)

class Base(DeclarativeBase):
    pass

class Broker(Base):
    __tablename__ = "brokers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)

class SourceFile(Base):
    __tablename__ = "source_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broker_id: Mapped[int] = mapped_column(ForeignKey("brokers.id"))
    path: Mapped[str] = mapped_column(Text)
    asof_date: Mapped[date | None] = mapped_column(SA_Date, nullable=True)
    broker = relationship("Broker")
    __table_args__ = (UniqueConstraint("path", name="uq_sourcefile_path"),)

class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broker_id: Mapped[int] = mapped_column(ForeignKey("brokers.id"))
    name: Mapped[str] = mapped_column(String)
    base_currency: Mapped[str] = mapped_column(String, default="USD")
    broker = relationship("Broker")
    __table_args__ = (UniqueConstraint("broker_id", "name", name="uq_account_broker_name"),)

class Instrument(Base):
    __tablename__ = "instruments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String)
    isin: Mapped[str | None] = mapped_column(String, nullable=True)
    cusip: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str | None] = mapped_column(String, nullable=True)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)

class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(SA_Date)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_basis: Mapped[float | None] = mapped_column(Float, nullable=True)
    est_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    asset_class: Mapped[str | None] = mapped_column(String, nullable=True)
    sector: Mapped[str | None] = mapped_column(String, nullable=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datetime: Mapped[datetime] = mapped_column(SA_DateTime)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"), nullable=True)
    type: Mapped[str] = mapped_column(String)  # BUY/SELL/DIV/COUPON/TAX/FEE/TRANSFER_IN/TRANSFER_OUT
    qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

class CashFlowExternal(Base):
    __tablename__ = "cashflows_external"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(SA_Date)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[float] = mapped_column(Float)  # contributions negative, withdrawals positive
    currency: Mapped[str] = mapped_column(String, default="USD")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

class Valuation(Base):
    __tablename__ = "valuations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(SA_Date)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    total_value: Mapped[float] = mapped_column(Float)
    method: Mapped[str | None] = mapped_column(String, nullable=True)  # 'reported' or 'reconstructed'
