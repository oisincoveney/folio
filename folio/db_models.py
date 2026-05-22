"""PostgreSQL record models for all supported document types."""

from __future__ import annotations

import contextlib
from decimal import Decimal, InvalidOperation
from typing import Self

import reflex as rx
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import Field, SQLModel, select


class _RecordBase(SQLModel):
    """Non-table base providing shared fields and classmethods for all record types."""

    id: int | None = Field(default=None, primary_key=True)
    file_key: str = Field(default="", index=True)
    content_hash: str = Field(default="")
    saved_at: str = Field(default="")
    status: str = Field(default="outstanding")

    @classmethod
    def upsert(cls, data: dict[str, str]) -> None:
        """Insert or update a record keyed on (file_key, content_hash)."""
        tbl = cls.__table__  # type: ignore[attr-defined]
        stmt = pg_insert(tbl).values(**data)
        update_dict = {
            k: getattr(stmt.excluded, k)
            for k in data
            if k not in ("id", "file_key", "content_hash")
        }
        with rx.session() as session:
            session.execute(
                stmt.on_conflict_do_update(
                    index_elements=["file_key", "content_hash"],
                    set_=update_dict,
                ),
            )
            session.commit()

    @classmethod
    def by_year(cls, year: int, quarter: int | None = None) -> list[Self]:
        """Return records saved in the given calendar year and optional quarter."""
        saved_at_col = cls.saved_at
        with rx.session() as session:
            if quarter is not None:
                start_m = (quarter - 1) * 3 + 1
                end_m = quarter * 3 + 1
                start = f"{year}-{start_m:02d}-01"
                end = f"{year + 1}-01-01" if end_m > 12 else f"{year}-{end_m:02d}-01"  # noqa: PLR2004
                stmt = select(cls).where(saved_at_col >= start, saved_at_col < end)
            else:
                stmt = select(cls).where(saved_at_col.startswith(str(year)))
            return list(session.exec(stmt).all())  # type: ignore[arg-type]

    @classmethod
    def outstanding(cls) -> list[Self]:
        """Return records with status='outstanding'."""
        status_col = cls.status
        with rx.session() as session:
            return list(
                session.exec(  # type: ignore[arg-type]
                    select(cls).where(status_col == "outstanding"),
                ).all(),
            )


class InvoiceRecord(_RecordBase, table=True):
    """Invoice record persisted after PDF parsing and S3 upload."""

    __table_args__ = (UniqueConstraint("file_key", "content_hash"),)

    doc_type: str = Field(default="invoice")
    amount: str = Field(default="")
    currency: str = Field(default="")
    company: str = Field(default="")
    invoice_number: str = Field(default="")
    invoice_date: str = Field(default="")
    description: str = Field(default="")
    account_number: str = Field(default="")
    payment_reference: str = Field(default="")

    @classmethod
    def eur_usd_totals(cls, year: int) -> dict[str, str]:
        """Return EUR and USD totals for the given year (Python-side aggregation)."""
        totals: dict[str, Decimal] = {}
        for r in cls.by_year(year):
            if r.currency in ("EUR", "USD"):
                with contextlib.suppress(InvalidOperation):
                    totals[r.currency] = (
                        totals.get(r.currency, Decimal(0)) + Decimal(r.amount)
                    )
        return {k: str(v) for k, v in totals.items()}


class BankTransactionRecord(_RecordBase, table=True):
    """Bank statement transaction record."""

    __table_args__ = (UniqueConstraint("file_key", "content_hash"),)

    doc_type: str = Field(default="bank_statement")
    transaction_date: str = Field(default="")
    amount: str = Field(default="")
    currency: str = Field(default="")
    counterparty: str = Field(default="")
    description: str = Field(default="")
    running_balance: str = Field(default="")


class TaxReceiptRecord(_RecordBase, table=True):
    """Tax receipt record."""

    __table_args__ = (UniqueConstraint("file_key", "content_hash"),)

    doc_type: str = Field(default="tax_receipt")
    tax_type: str = Field(default="")
    period: str = Field(default="")
    amount_paid: str = Field(default="")
    jurisdiction: str = Field(default="")

    @classmethod
    def by_jurisdiction(cls, jurisdiction: str) -> list[Self]:
        """Return records for the given jurisdiction code."""
        juris_col = cls.jurisdiction
        with rx.session() as session:
            return list(
                session.exec(  # type: ignore[arg-type]
                    select(cls).where(juris_col == jurisdiction),
                ).all(),
            )


class PayslipRecord(_RecordBase, table=True):
    """Payslip record."""

    __table_args__ = (UniqueConstraint("file_key", "content_hash"),)

    doc_type: str = Field(default="payslip")
    period: str = Field(default="")
    gross_salary: str = Field(default="")
    income_tax: str = Field(default="")
    social_tax: str = Field(default="")
    net_pay: str = Field(default="")
