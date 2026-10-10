"""RawBill (printed strings) -> final 18-key object (numbers, dates, signs, sums)."""

from __future__ import annotations

import itertools
import re

from .normalize import (
    Number,
    clean_text,
    number_in,
    parse_amount,
    parse_bill_month,
    parse_date,
    round_sum,
)
from .schema import ChargeLine, FinalBill, RawBill, TaxLine

TOL = 1.0 + 1e-9

# Slots of the LESCO/IESCO "Bill Charges Breakdown" column, top to bottom.
SLOTS = ["total", "subsidies", "net", "taxes", "current", "grand"]


def _has_value(s: str | None) -> bool:
    return s is not None and s.strip() not in {"", "-"}


def _amount(s: str | None, field: str, warnings: list[str]) -> Number | None:
    value = parse_amount(s)
    if value is None and _has_value(s) and re.search(r"\d", s or ""):
        warnings.append(f"could not parse {field}: {s!r}")
    return value


# --------------------------------------------------------------------------------
# Arithmetic alignment (LESCO / IESCO)
# --------------------------------------------------------------------------------
def _checks_hold(
    v: dict[str, Number | None], arrears: Number | None, payable: Number | None, extra: Number
) -> bool:
    total, subs, net, taxes, cur, grand = (v[k] for k in SLOTS)
    if None in (total, net, taxes, cur, grand):
        return False
    s = subs or 0
    if abs(total - s - net) > TOL:  # subsidies are printed positive in the column
        return False
    if abs(net + taxes - cur) > TOL:
        return False
    if abs(cur + (arrears or 0) + extra - grand) > TOL:
        return False
    if payable is not None and abs(grand - payable) > TOL:
        return False
    return True


def align_breakdown(
    raw: RawBill, provider: str, warnings: list[str], layout: str | None = None
) -> RawBill:
    """Use the bill's own arithmetic to decide which printed value belongs to which label.

    Phone photos shift values one row off their labels. If the model's own mapping
    already satisfies the bill arithmetic it is kept. Otherwise the values in
    ``breakdown_values`` are assigned in order to Total, Subsidies, Net, Taxes,
    Current Bill and Grand Total (only Subsidies may stay blank) and the first
    assignment that satisfies all checks is used. No value is ever altered, only
    re-assigned.
    """
    if provider not in {"LESCO", "IESCO"} or not raw.breakdown_values:
        return raw

    arrears = parse_amount(raw.arrears)
    payable = parse_amount(raw.payable_within_due_date)
    # IESCO prints Total FPA outside the net-charges column; it is added in the grand total.
    extra = 0
    if provider == "IESCO" or layout == "digital":
        for line in raw.charge_lines:
            if line.type == "fpa":
                extra += parse_amount(line.amount) or 0

    energy = next((c for c in raw.charge_lines if c.type == "energy"), None)
    subsidy = next((c for c in raw.charge_lines if c.type == "subsidy"), None)
    current_map = {
        "total": parse_amount(energy.amount) if energy else None,
        "subsidies": abs(parse_amount(subsidy.amount) or 0) if subsidy else None,
        "net": parse_amount(raw.total_charges),
        "taxes": parse_amount(raw.total_taxes),
        "current": parse_amount(raw.current_bill),
        "grand": payable,
    }
    if _checks_hold(current_map, arrears, payable, extra):
        return raw

    values = list(raw.breakdown_values)
    parsed = [parse_amount(v) for v in values]
    for size in (len(SLOTS) - 1, len(SLOTS)):
        for combo in itertools.combinations(range(len(values)), size):
            if any(parsed[i] is None for i in combo):
                continue
            chosen = [values[i] for i in combo]
            if size == len(SLOTS):
                slots = dict(zip(SLOTS, chosen))
            else:
                slots = {k: v for k, v in zip([s for s in SLOTS if s != "subsidies"], chosen)}
                slots["subsidies"] = None
            nums = {k: (parse_amount(v) if v is not None else None) for k, v in slots.items()}
            if nums["subsidies"] is not None:
                nums["subsidies"] = abs(nums["subsidies"])
            if _checks_hold(nums, arrears, payable, extra):
                return _apply_slots(raw, slots, warnings)

    warnings.append(
        "breakdown alignment: no assignment of breakdown_values satisfies the bill "
        "arithmetic; keeping the model's label mapping"
    )
    return raw


def _apply_slots(raw: RawBill, slots: dict[str, str | None], warnings: list[str]) -> RawBill:
    new = raw.model_copy(deep=True)
    lines = [c for c in new.charge_lines if c.type not in {"energy", "subsidy"}]
    energy_old = next((c for c in raw.charge_lines if c.type == "energy"), None)
    energy = ChargeLine(
        label=energy_old.label if energy_old else "Total Electricity Charges",
        amount=slots["total"],
        type="energy",
    )
    rebuilt = [energy]
    if slots["subsidies"] is not None:
        sub_old = next((c for c in raw.charge_lines if c.type == "subsidy"), None)
        rebuilt.append(
            ChargeLine(
                label=sub_old.label if sub_old else "Subsidies",
                amount=slots["subsidies"],
                type="subsidy",
            )
        )
    new.charge_lines = rebuilt + lines
    new.total_charges = slots["net"]
    new.total_taxes = slots["taxes"]
    new.current_bill = slots["current"]
    new.tax_lines = []
    before = (raw.total_charges, raw.total_taxes, raw.current_bill)
    after = (new.total_charges, new.total_taxes, new.current_bill)
    if before != after:
        warnings.append(
            f"breakdown alignment re-assigned values: (net, taxes, current) {before} -> {after}"
        )
    return new


# --------------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------------
def _lines(lines: list[ChargeLine] | list[TaxLine], kind: str, warnings: list[str]) -> list[dict]:
    out = []
    for line in lines:
        amount = _amount(line.amount, f"{kind} '{line.label}'", warnings)
        if amount is None or amount == 0:
            continue
        if line.type == "subsidy":
            amount = -abs(amount)
        out.append({"type": line.type, "amount": amount})
    return out


def _meter(raw: RawBill, provider: str, warnings: list[str]) -> tuple:
    rows = [r for r in raw.meter_rows if any(_has_value(x) for x in (r.previous, r.present, r.units))]

    previous = current = None
    if len(rows) == 1:
        previous = _amount(rows[0].previous, "previous_reading", warnings)
        current = _amount(rows[0].present, "current_reading", warnings)
    elif len(rows) > 1:  # readings are column sums across all meter rows
        previous = _column_sum([r.previous for r in rows], "previous_reading", warnings)
        current = _column_sum([r.present for r in rows], "current_reading", warnings)

    headline = number_in(raw.billed_units_headline)
    if headline is not None:
        units = headline
    else:
        cells = [r.units for r in rows if _has_value(r.units)]
        if not cells:
            units = None
        elif len(rows) == 1:
            units = _amount(cells[0], "units_consumed", warnings)
        else:
            units = _column_sum(cells, "units_consumed", warnings)
    return previous, current, units


def _column_sum(cells: list[str | None], field: str, warnings: list[str]) -> Number | None:
    """Column sum rounded to 2 decimals. Any unreadable cell makes the sum null."""
    values = []
    for cell in cells:
        value = parse_amount(cell) if _has_value(cell) else None
        if value is None:
            warnings.append(f"{field}: unreadable meter cell {cell!r}; sum set to null")
            return None
        values.append(value)
    return round_sum(values) if values else None


def assemble(
    raw: RawBill, provider: str | None, warnings: list[str], layout: str | None = None
) -> dict:
    """Build the final 18-key object. Never changes a printed value."""
    if provider in {"LESCO", "IESCO"} and layout != "web":
        raw = align_breakdown(raw, provider, warnings, layout)

    previous, current, units = _meter(raw, provider or "", warnings)

    after_amounts = [
        _amount(a, "payable_after_due_date", warnings) for a in raw.payable_after_due_date_amounts
    ]
    after_amounts = [a for a in after_amounts if a is not None]

    def date(value: str | None, field: str) -> str | None:
        result = parse_date(value)
        if result is None and _has_value(value):
            warnings.append(f"could not parse {field}: {value!r}")
        return result

    month = parse_bill_month(raw.bill_month)
    if month is None and _has_value(raw.bill_month):
        warnings.append(f"could not parse bill_month: {raw.bill_month!r}")

    final = FinalBill(
        provider=provider,
        tariff=clean_text(raw.tariff),
        sanctioned_load_kw=number_in(raw.sanctioned_load),
        bill_month=month,
        reading_date=date(raw.reading_date, "reading_date"),
        issue_date=date(raw.issue_date, "issue_date"),
        due_date=date(raw.due_date, "due_date"),
        previous_reading=previous,
        current_reading=current,
        units_consumed=units,
        charges=_lines(raw.charge_lines, "charge", warnings),
        total_charges=_amount(raw.total_charges, "total_charges", warnings),
        taxes=_lines(raw.tax_lines, "tax", warnings),
        total_taxes=_amount(raw.total_taxes, "total_taxes", warnings),
        current_bill=_amount(raw.current_bill, "current_bill", warnings),
        arrears=_amount(raw.arrears, "arrears", warnings),
        payable_within_due_date=_amount(raw.payable_within_due_date, "payable_within_due_date", warnings),
        payable_after_due_date=max(after_amounts) if after_amounts else None,
    )
    return final.to_ordered_dict()
