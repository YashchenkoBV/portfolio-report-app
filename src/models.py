"""Database models for the portfolio report app.

We use SQLAlchemy's declarative system to define our tables. The models
represent brokers, accounts, instruments, positions, transactions and
valuations. A ``SourceFile`` records metadata about a parsed PDF file.

The sign conventions follow a simple rule: contributions into the account
(money that the investor puts into the broker) are negative cash flows and
withdrawals are positive cash flows. This makes computing money‑weighted
returns straightforward when adding the terminal value as a positive flow.
"""

from __future__ import annotations

from datetime import date, datetime
from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Float,
    Text,
    UniqueConstraint,
    Date as SA_Date,
    DateTime as SA_DateTime,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for SQLAlchemy declarative models."""

    pass


class Broker(Base):
    __tablename__ = "brokers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)

    accounts: Mapped[list["Account"]] = relationship(back_populates="broker")
    files: Mapped[list["SourceFile"]] = relationship(back_populates="broker")


class SourceFile(Base):
    __tablename__ = "source_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broker_id: Mapped[int] = mapped_column(ForeignKey("brokers.id"))
    path: Mapped[str] = mapped_column(Text)
    # optional as‑of date extracted from the PDF
    asof_date: Mapped[date | None] = mapped_column(SA_Date, nullable=True)

    broker: Mapped["Broker"] = relationship(back_populates="files")

    __table_args__ = (UniqueConstraint("path", name="uq_sourcefile_path"),)


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broker_id: Mapped[int] = mapped_column(ForeignKey("brokers.id"))
    name: Mapped[str] = mapped_column(String)
    base_currency: Mapped[str] = mapped_column(String, default="USD")

    broker: Mapped["Broker"] = relationship(back_populates="accounts")
    positions: Mapped[list["PositionSnapshot"]] = relationship(back_populates="account")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")
    cashflows: Mapped[list["CashFlowExternal"]] = relationship(back_populates="account")
    valuations: Mapped[list["Valuation"]] = relationship(back_populates="account")

    __table_args__ = (
        UniqueConstraint("broker_id", "name", name="uq_account_broker_name"),
    )


class Instrument(Base):
    __tablename__ = "instruments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String)
    isin: Mapped[str | None] = mapped_column(String, nullable=True)
    cusip: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str | None] = mapped_column(String, nullable=True)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)

    positions: Mapped[list["PositionSnapshot"]] = relationship(back_populates="instrument")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="instrument")


class PositionSnapshot(Base):
    """A snapshot of a position in an account at a given date."""

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

    account: Mapped["Account"] = relationship(back_populates="positions")
    instrument: Mapped["Instrument"] = relationship(back_populates="positions")


class Transaction(Base):
    """A transaction or cash movement related to an instrument."""

    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datetime: Mapped[datetime] = mapped_column(SA_DateTime)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"), nullable=True)
    type: Mapped[str] = mapped_column(String)
    qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    account: Mapped["Account"] = relationship(back_populates="transactions")
    instrument: Mapped["Instrument"] = relationship(back_populates="transactions")


class CashFlowExternal(Base):
    """A cash flow external to the account, such as a deposit or withdrawal."""

    __tablename__ = "cashflows_external"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(SA_Date)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String, default="USD")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    account: Mapped["Account"] = relationship(back_populates="cashflows")


class Valuation(Base):
    """The total value of an account at a given date."""

    __tablename__ = "valuations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(SA_Date)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    total_value: Mapped[float] = mapped_column(Float)
    method: Mapped[str | None] = mapped_column(String, nullable=True)

    account: Mapped["Account"] = relationship(back_populates="valuations")