"""Hard checks (trigger a retry) and soft checks (logged only)."""

from __future__ import annotations

import re

from .normalize import parse_amount
from .schema import RawBill

TOL = 1.0 + 1e-9


def hard_check(raw: RawBill) -> list[str]:
    """Return problems that justify asking the model again.

    Structure and enums are enforced by the pydantic parse; this covers amounts:
    every printed amount must parse as a number (or be null / non-numeric text).
    """
    errors: list[str] = []

    def check(value: str | None, field: str) -> None:
        if value is None or not value.strip():
            return
        if re.search(r"\d", value) and parse_amount(value) is None:
            errors.append(
                f"{field}: {value!r} is not a printed amount. Copy only the amount "
                "(digits, optional commas/decimals, optional CR or minus sign), never a percentage "
                "or a label; use null if it is not printed."
            )

    for name in (
        "total_charges", "total_taxes", "current_bill", "arrears", "payable_within_due_date",
    ):
        check(getattr(raw, name), name)
    for line in raw.charge_lines:
        check(line.amount, f"charge_lines '{line.label}'")
    for line in raw.tax_lines:
        check(line.amount, f"tax_lines '{line.label}'")
    for i, amount in enumerate(raw.payable_after_due_date_amounts):
        check(amount, f"payable_after_due_date_amounts[{i}]")
    for i, row in enumerate(raw.meter_rows):
        for col in ("previous", "present", "units"):
            check(getattr(row, col), f"meter_rows[{i}].{col}")
    for i, value in enumerate(raw.breakdown_values):
        check(value, f"breakdown_values[{i}]")
    return errors


def soft_check(final: dict) -> list[str]:
    """Arithmetic and leak checks. Logged to warnings.txt, never change a value."""
    w: list[str] = []
    prev, cur, units = final["previous_reading"], final["current_reading"], final["units_consumed"]
    if None not in (prev, cur, units) and abs((cur - prev) - units) > TOL:
        w.append(f"current_reading - previous_reading ({cur - prev}) differs from units_consumed ({units})")

    charges = final["charges"]
    has_subsidy = any(c["type"] == "subsidy" for c in charges)
    if final["total_charges"] is not None and charges and not has_subsidy:
        total = sum(c["amount"] for c in charges)
        if abs(total - final["total_charges"]) > TOL:
            w.append(f"charges sum ({round(total, 2)}) differs from total_charges ({final['total_charges']})")

    tc, tt, cb = final["total_charges"], final["total_taxes"], final["current_bill"]
    if None not in (tc, tt, cb) and abs(tc + tt - cb) > TOL:
        w.append(f"total_charges + total_taxes ({round(tc + tt, 2)}) differs from current_bill ({cb})")

    within, after = final["payable_within_due_date"], final["payable_after_due_date"]
    if None not in (within, after) and after < within:
        w.append(f"payable_after_due_date ({after}) is lower than payable_within_due_date ({within})")

    for key in ("provider", "tariff", "bill_month", "reading_date", "issue_date", "due_date"):
        value = final.get(key)
        if isinstance(value, str) and re.search(r"\d{8,}", value):
            w.append(f"{key} contains a run of 8+ digits (possible identifier leak): {value!r}")
    return w
