"""Pydantic extraction models for all supported document types."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from folio.normalization import normalize_amount


def _amount_validator(value: object) -> str:
    return normalize_amount(value)


class InvoiceData(BaseModel):
    """Structured invoice data extracted from a PDF.

    JSON I/O uses camelCase keys (opencode extraction schema); Python attributes
    are snake_case. `model_dump(by_alias=True)` emits the camelCase form.
    """

    model_config = ConfigDict(populate_by_name=True)

    doc_type: Literal["invoice"] = "invoice"
    amount: str
    target_currency: str = Field(
        validation_alias="targetCurrency",
        serialization_alias="targetCurrency",
    )
    company: str = ""
    invoice_number: str = Field(
        default="",
        validation_alias="invoiceNumber",
        serialization_alias="invoiceNumber",
    )
    invoice_date: str = Field(
        default="",
        validation_alias="invoiceDate",
        serialization_alias="invoiceDate",
    )
    description: str = ""
    account_number: str = Field(
        default="",
        validation_alias="accountNumber",
        serialization_alias="accountNumber",
    )
    payment_reference: str = Field(
        default="",
        validation_alias="paymentReference",
        serialization_alias="paymentReference",
    )

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount_field(cls, value: object) -> str:
        """Normalize the amount field before validation."""
        return normalize_amount(value)


class BankTransactionData(BaseModel):
    """Structured data extracted from a bank statement transaction."""

    doc_type: Literal["bank_statement"] = "bank_statement"
    transaction_date: str
    amount: str
    currency: str
    counterparty: str = ""
    description: str = ""
    running_balance: str = ""

    @field_validator("amount", "running_balance", mode="before")
    @classmethod
    def normalize_amount_field(cls, value: object) -> str:
        """Normalize monetary fields before validation."""
        return normalize_amount(value)


class TaxReceiptData(BaseModel):
    """Structured data extracted from a tax receipt."""

    doc_type: Literal["tax_receipt"] = "tax_receipt"
    tax_type: str
    period: str
    amount_paid: str
    jurisdiction: str = ""

    @field_validator("amount_paid", mode="before")
    @classmethod
    def normalize_amount_field(cls, value: object) -> str:
        """Normalize the amount_paid field before validation."""
        return normalize_amount(value)


class PayslipData(BaseModel):
    """Structured data extracted from a payslip."""

    doc_type: Literal["payslip"] = "payslip"
    period: str
    gross_salary: str
    income_tax: str
    social_tax: str
    net_pay: str

    @field_validator("gross_salary", "income_tax", "social_tax", "net_pay", mode="before")  # noqa: E501
    @classmethod
    def normalize_amount_field(cls, value: object) -> str:
        """Normalize all monetary fields before validation."""
        return normalize_amount(value)


AnyDocumentData = Annotated[
    InvoiceData | BankTransactionData | TaxReceiptData | PayslipData,
    Field(discriminator="doc_type"),
]
