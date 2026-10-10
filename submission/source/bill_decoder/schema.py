"""Pydantic models: the raw LLM output and the final 18-key Level 1 object."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChargeType = Literal[
    "energy", "fixed", "fpa", "quarterly_adjustment", "surcharge", "meter_rent", "subsidy", "other"
]
TaxType = Literal["gst", "electricity_duty", "income_tax", "municipal_tax", "other_tax"]

CHARGE_TYPES = list(ChargeType.__args__)
TAX_TYPES = list(TaxType.__args__)


class MeterRow(BaseModel):
    label: str | None = None
    previous: str | None = None
    present: str | None = None
    units: str | None = None


class ChargeLine(BaseModel):
    label: str
    amount: str | None = None
    type: ChargeType


class TaxLine(BaseModel):
    label: str
    amount: str | None = None
    type: TaxType


class BillHistoryRow(BaseModel):
    """One printed row of the bill-history table / usage chart (strings as printed)."""

    month: str
    units: str | None = None
    bill: str | None = None
    payment: str | None = None
    status: str | None = None


# Bump when the raw schema or prompts change in a way that invalidates cached raw.json.
RAW_SCHEMA_VERSION = 2


class RawBill(BaseModel):
    """What the model returns: printed strings, copied as printed, or null."""

    model_config = ConfigDict(extra="ignore")

    tariff: str | None = None
    sanctioned_load: str | None = None
    bill_month: str | None = None
    reading_date: str | None = None
    issue_date: str | None = None
    due_date: str | None = None
    meter_rows: list[MeterRow] = Field(default_factory=list)
    billed_units_headline: str | None = None
    charge_lines: list[ChargeLine] = Field(default_factory=list)
    total_charges: str | None = None
    tax_lines: list[TaxLine] = Field(default_factory=list)
    total_taxes: str | None = None
    current_bill: str | None = None
    arrears: str | None = None
    payable_within_due_date: str | None = None
    payable_after_due_date_amounts: list[str] = Field(default_factory=list)
    payable_after_due_date_text: str | None = None
    # LESCO / IESCO only: every value in the breakdown column, top to bottom.
    breakdown_values: list[str] = Field(default_factory=list)
    # Saved for Level 2; ignored by the Level 1 final JSON.
    bill_history: list[BillHistoryRow] = Field(default_factory=list)


class FinalCharge(BaseModel):
    type: ChargeType
    amount: float | int


class FinalTax(BaseModel):
    type: TaxType
    amount: float | int


FINAL_KEYS = [
    "provider", "tariff", "sanctioned_load_kw", "bill_month", "reading_date", "issue_date",
    "due_date", "previous_reading", "current_reading", "units_consumed", "charges",
    "total_charges", "taxes", "total_taxes", "current_bill", "arrears",
    "payable_within_due_date", "payable_after_due_date",
]


class FinalBill(BaseModel):
    provider: Literal["KE", "LESCO", "IESCO"] | None = None
    tariff: str | None = None
    sanctioned_load_kw: float | int | None = None
    bill_month: str | None = None
    reading_date: str | None = None
    issue_date: str | None = None
    due_date: str | None = None
    previous_reading: float | int | None = None
    current_reading: float | int | None = None
    units_consumed: float | int | None = None
    charges: list[FinalCharge] = Field(default_factory=list)
    total_charges: float | int | None = None
    taxes: list[FinalTax] = Field(default_factory=list)
    total_taxes: float | int | None = None
    current_bill: float | int | None = None
    arrears: float | int | None = None
    payable_within_due_date: float | int | None = None
    payable_after_due_date: float | int | None = None

    def to_ordered_dict(self) -> dict:
        data = self.model_dump()
        return {k: data[k] for k in FINAL_KEYS}


def fallback_bill(provider: str | None) -> dict:
    """Complete 18-key object used when a bill cannot be processed."""
    return FinalBill(provider=provider).to_ordered_dict()
