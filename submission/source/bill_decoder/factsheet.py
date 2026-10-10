"""Deterministic fact sheet for Level 2: every number the answers rely on is computed here.

Every computed value is a metric ``{"value": ..., "reason": ...}``; ``reason`` is ``None``
when the value exists and explains why it is missing when the value is ``None``.
Derived values are rounded to 2 decimals; printed bill values are never altered.
"""

from __future__ import annotations

import calendar
import datetime
import statistics
from typing import Any

from .normalize import parse_amount, parse_bill_month

THRESHOLDS = (100, 200, 300, 500, 1000)
SUMMER_MONTHS = (6, 7, 8)
WINTER_MONTHS = (12, 1, 2)
TOL_PAYMENT = 1.5


# --------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------
def metric(value: Any, reason: str | None = None) -> dict:
    if value is None:
        return {"value": None, "reason": reason or "not available on the bill"}
    return {"value": value, "reason": None}


def r2(x: float | None) -> float | None:
    return None if x is None else round(float(x), 2)


def _div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def _pct(a, b):
    v = _div(a, b)
    return None if v is None else v * 100


def _idx(key: str) -> int:
    y, m = key.split("-")
    return int(y) * 12 + int(m) - 1


def _shift(key: str, n: int) -> str:
    i = _idx(key) + n
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def _label(key: str) -> str:
    y, m = key.split("-")
    return f"{calendar.month_name[int(m)]} {y}"


def _days_between(a: str | None, b: str | None) -> int | None:
    try:
        return (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------------
# history
# --------------------------------------------------------------------------------
def normalize_history(raw_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Merge printed history rows by month (YYYY-MM), parse numbers, sort oldest first."""
    merged: dict[str, dict] = {}
    unparsed: list[dict] = []
    for r in raw_rows or []:
        key = parse_bill_month(r.get("month"))
        if key is None:
            unparsed.append(r)
            continue
        cur = merged.setdefault(
            key,
            {"month": key, "label": _label(key), "units": None, "bill": None, "payment": None,
             "status": None, "is_current": False, "filled_from_level1": False},
        )
        for f in ("units", "bill", "payment"):
            v = parse_amount(r.get(f))
            if cur[f] is None and v is not None:
                cur[f] = v
        status = (r.get("status") or "").strip() or None
        if cur["status"] is None and status:
            cur["status"] = status
    return sorted(merged.values(), key=lambda x: x["month"]), unparsed


def _stats(rows: list[dict], field: str, what: str) -> dict:
    vals = [(r["month"], r[field]) for r in rows if r[field] is not None]
    if not vals:
        none = f"no {what} values in this history scope"
        return {
            "count": 0, "total": metric(None, none), "average": metric(None, none),
            "median": metric(None, none), "min": metric(None, none), "max": metric(None, none),
        }
    nums = [v for _, v in vals]
    lo = min(vals, key=lambda p: p[1])
    hi = max(vals, key=lambda p: p[1])
    return {
        "count": len(nums),
        "total": metric(r2(sum(nums))),
        "average": metric(r2(sum(nums) / len(nums))),
        "median": metric(r2(statistics.median(nums))),
        "min": {"value": r2(lo[1]), "month": _label(lo[0]), "reason": None},
        "max": {"value": r2(hi[1]), "month": _label(hi[0]), "reason": None},
    }


def _above(rows: list[dict]) -> dict:
    out = {}
    for t in THRESHOLDS:
        months = [r["label"] for r in rows if r["units"] is not None and r["units"] > t]
        out[str(t)] = {"count": len(months), "months": months}
    return out


def _season(rows: list[dict], months: tuple[int, ...]) -> dict:
    sel = [r for r in rows if r["units"] is not None and int(r["month"][5:]) in months]
    if not sel:
        return {
            "months": [], "total": metric(None, "no history months in this season"),
            "average": metric(None, "no history months in this season"),
        }
    total = sum(r["units"] for r in sel)
    return {
        "months": [r["label"] for r in sel], "total": metric(r2(total)),
        "average": metric(r2(total / len(sel))),
    }


def _seasonal(rows: list[dict]) -> dict:
    summer, winter = _season(rows, SUMMER_MONTHS), _season(rows, WINTER_MONTHS)
    out = {"summer_jun_aug": summer, "winter_dec_feb": winter}
    for key, name in (("total", "difference_in_total"), ("average", "difference_in_average")):
        a, b = summer[key]["value"], winter[key]["value"]
        out[name] = metric(
            r2(a - b) if a is not None and b is not None else None,
            "summer or winter months are missing from the history",
        )
    return out


def _trend_last3(rows: list[dict]) -> dict:
    sel = [r for r in rows if r["units"] is not None][-3:]
    if len(sel) < 3:
        return {"months": [r["label"] for r in sel], "direction": metric(None, "fewer than 3 months of units in this scope"),
                "change_first_to_last": metric(None, "fewer than 3 months of units in this scope")}
    units = [r["units"] for r in sel]
    steps = [b - a for a, b in zip(units, units[1:])]
    if all(s > 0 for s in steps):
        direction = "up"
    elif all(s < 0 for s in steps):
        direction = "down"
    elif units[-1] == units[0] and all(s == 0 for s in steps):
        direction = "flat"
    else:
        direction = "mixed (net " + ("up" if units[-1] > units[0] else "down" if units[-1] < units[0] else "flat") + ")"
    return {
        "months": [r["label"] for r in sel], "units": units, "direction": metric(direction),
        "change_first_to_last": metric(r2(units[-1] - units[0])),
        "change_first_to_last_pct": metric(r2(_pct(units[-1] - units[0], units[0])), "first month is 0"),
    }


def _forecast(rows: list[dict], bill_month: str | None, cost_per_unit: float | None) -> dict:
    """Estimates of next month's units (clearly estimates, from the last 12 months with units)."""
    pts = [r for r in rows if r["units"] is not None][-12:]
    nxt = _shift(bill_month, 1) if bill_month else None
    out: dict = {"next_month": _label(nxt) if nxt else None, "points_used": len(pts)}
    if len(pts) < 3:
        why = "fewer than 3 months of unit history"
        for k in ("average_of_window", "linear_trend", "same_month_last_year", "primary_estimate", "estimated_bill_at_current_rate"):
            out[k] = metric(None, why)
        return out
    vals = [r["units"] for r in pts]
    avg = sum(vals) / len(vals)
    out["average_of_window"] = metric(r2(avg))
    xs = [_idx(r["month"]) for r in pts]
    mx, my = sum(xs) / len(xs), avg
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        out["linear_trend"] = metric(None, "history months are not distinct")
        lin = None
    else:
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, vals)) / sxx
        lin = max(0.0, my + slope * (_idx(nxt) - mx)) if nxt else None
        out["linear_trend"] = metric(r2(lin), "bill month unknown")
        out["linear_trend_slope_units_per_month"] = metric(r2(slope))
    ly = next((r["units"] for r in rows if nxt and r["month"] == _shift(nxt, -12) and r["units"] is not None), None)
    out["same_month_last_year"] = metric(r2(ly), "that month is not in the printed history")
    primary = lin if (lin is not None and len(pts) >= 6) else avg
    out["primary_estimate"] = metric(
        r2(primary),
    )
    out["primary_estimate_method"] = (
        "linear trend over the last 12 months of history" if (lin is not None and len(pts) >= 6)
        else "average of the available months of history"
    )
    out["estimated_bill_at_current_rate"] = metric(
        r2(primary * cost_per_unit) if cost_per_unit is not None else None,
        "cost per unit cannot be estimated from this bill",
    )
    return out


def _payments(rows: list[dict]) -> dict:
    billed = [r for r in rows if r["bill"] is not None]
    if not billed:
        why = "the bill prints no payment history amounts"
        return {"months_with_bill_data": 0, "months_unpaid": metric(None, why), "months_partial": metric(None, why),
                "months_fully_paid": metric(None, why), "total_billed": metric(None, why), "total_paid": metric(None, why)}
    unpaid, partial, full, nodue, over = [], [], [], [], []
    for r in billed:
        b, p = r["bill"], r["payment"]
        if b <= 0:
            nodue.append(r["label"])
        elif p is None or p <= 0:
            unpaid.append(r["label"])
        elif p < b - TOL_PAYMENT:
            partial.append(f"{r['label']} (billed {r2(b)}, paid {r2(p)})")
        else:
            full.append(r["label"])
            if p > b + TOL_PAYMENT:
                over.append(r["label"])
    paid = [r["payment"] for r in billed if r["payment"] is not None]
    return {
        "months_with_bill_data": len(billed),
        "months_unpaid_or_blank_payment": unpaid,
        "months_partial": partial,
        "months_fully_paid": full,
        "months_with_credit_or_zero_bill_no_payment_due": nodue,
        "months_paid_more_than_billed": over,
        "total_billed": metric(r2(sum(r["bill"] for r in billed))),
        "total_paid": metric(r2(sum(paid)) if paid else None, "no payment amounts printed"),
    }


def _change(cur, prev, what: str) -> dict:
    if cur is None or prev is None:
        why = f"{what} for the current or previous month is not available"
        return {"absolute": metric(None, why), "percent": metric(None, why)}
    return {
        "absolute": metric(r2(cur - prev)),
        "percent": metric(r2(_pct(cur - prev, prev)), "previous value is 0"),
    }


def _history(final: dict, raw: dict, provider: str, cost_per_unit: float | None) -> dict:
    rows, unparsed = normalize_history(raw.get("bill_history") or [])
    bm = final.get("bill_month")
    scope = "including_current" if provider == "KE" else "previous_months_only"
    info: dict = {
        "history_scope": scope,
        "scope_note": (
            "The K-Electric 13-month chart includes the current month."
            if provider == "KE"
            else "The printed history tables list previous months only."
        ),
        "printed_months": len(rows),
        "unparsed_rows": unparsed,
    }
    if bm is None:
        info["note"] = "bill_month is not available, so current-month handling is skipped"
        cur_row = None
    else:
        cur_row = next((r for r in rows if r["month"] == bm), None)
        printed_current = cur_row is not None and cur_row["units"] is not None
        info["current_month_in_printed_history"] = printed_current
        if cur_row is None:
            cur_row = {"month": bm, "label": _label(bm), "units": None, "bill": None, "payment": None,
                       "status": None, "is_current": True, "filled_from_level1": True}
            rows.append(cur_row)
        if cur_row["units"] is None and final.get("units_consumed") is not None:
            cur_row["units"] = final["units_consumed"]
            cur_row["filled_from_level1"] = True
        if cur_row["bill"] is None and final.get("current_bill") is not None:
            cur_row["bill"] = final["current_bill"]
            cur_row["filled_from_level1"] = True
        cur_row["is_current"] = True
        rows.sort(key=lambda x: x["month"])
    info["current_month_appended_or_filled"] = bool(cur_row and cur_row["filled_from_level1"])

    prev_rows = [r for r in rows if not r["is_current"]]
    incl_rows = rows
    by_month = {r["month"]: r for r in rows}

    def scope_block(sel: list[dict]) -> dict:
        return {
            "months": [r["label"] for r in sel],
            "units": _stats(sel, "units", "units"),
            "bill": _stats(sel, "bill", "bill"),
            "units_above": _above(sel),
        }

    info["previous_months"] = scope_block(prev_rows)
    info["including_current"] = scope_block(incl_rows)

    cur_units = final.get("units_consumed")
    prev_key = _shift(bm, -1) if bm else None
    last_year_key = _shift(bm, -12) if bm else None
    prev_row = by_month.get(prev_key) if prev_key else None
    ly_row = by_month.get(last_year_key) if last_year_key else None
    info["change_vs_previous_month"] = {
        "previous_month": _label(prev_key) if prev_key else None,
        "units": _change(cur_units, prev_row["units"] if prev_row else None, "units"),
        "bill": _change(final.get("current_bill"), prev_row["bill"] if prev_row else None, "bill"),
    }
    info["change_vs_same_month_last_year"] = {
        "month": _label(last_year_key) if last_year_key else None,
        "last_year_units": metric(ly_row["units"] if ly_row else None, "that month is not in the printed history"),
        "units": _change(cur_units, ly_row["units"] if ly_row else None, "units"),
        "bill": _change(final.get("current_bill"), ly_row["bill"] if ly_row else None, "bill"),
    }
    prev_avg = info["previous_months"]["units"]["average"]["value"]
    info["current_units_vs_previous_months_average"] = {
        "average_used": metric(prev_avg, "no previous months with units"),
        "absolute": metric(r2(cur_units - prev_avg) if None not in (cur_units, prev_avg) else None, "current units or previous average is missing"),
        "percent": metric(r2(_pct(cur_units - prev_avg, prev_avg)) if None not in (cur_units, prev_avg) else None, "current units or previous average is missing"),
    }
    info["payments_previous_months"] = _payments(prev_rows)
    info["seasonal_units"] = {
        "previous_months": _seasonal(prev_rows), "including_current": _seasonal(incl_rows),
    }
    info["last_3_months_trend"] = {
        "previous_months": _trend_last3(prev_rows), "including_current": _trend_last3(incl_rows),
    }
    info["forecast_next_month_units_estimate"] = _forecast(incl_rows, bm, cost_per_unit)

    avg_bill_prev = info["previous_months"]["bill"]["average"]["value"]
    avg_bill_incl = info["including_current"]["bill"]["average"]["value"]
    cb = final.get("current_bill")
    n_bill = info["including_current"]["bill"]["count"]
    info["monthly_set_aside_estimate"] = {
        "average_monthly_bill_previous_months": metric(avg_bill_prev, "no billed amounts for previous months on the bill"),
        "average_monthly_bill_including_current": metric(avg_bill_incl, "no billed amounts on the bill"),
        "annualised_from_current_bill_per_month": metric(r2(cb), "current_bill is not printed"),
        "primary_estimate": metric(
            avg_bill_incl if (avg_bill_incl is not None and n_bill >= 6) else (r2(cb) if cb is not None else None),
            "no billed amounts available",
        ),
        "primary_estimate_method": (
            "average billed amount over the printed history including the current month"
            if (avg_bill_incl is not None and n_bill >= 6)
            else "the current bill repeated every month (history has too few billed amounts)"
        ),
        "printed_history_bill_count": n_bill,
    }
    prev_units = prev_row["units"] if prev_row else None
    info["repeat_consumption_estimates"] = {
        "if_same_units_as_previous_month": {
            "units": metric(prev_units, "previous month is not in the printed history"),
            "previous_month_actual_bill": metric(prev_row["bill"] if prev_row else None, "previous month's billed amount is not printed"),
            "estimated_bill_at_current_rate": metric(
                r2(prev_units * cost_per_unit) if None not in (prev_units, cost_per_unit) else None,
                "previous month's units or the current cost per unit is not available",
            ),
        },
        "if_same_units_as_current_month": {
            "units": metric(cur_units, "units_consumed is not printed"),
            "bill": metric(cb, "current_bill is not printed"),
        },
    }
    info["rows"] = rows
    return info


# --------------------------------------------------------------------------------
# main entry
# --------------------------------------------------------------------------------
def _labelled(final_lines: list[dict], raw_lines: list[dict]) -> list[dict]:
    """Attach printed labels to final lines: greedy match on (type, |amount|) in printed order."""
    pool = [dict(l, _used=False) for l in raw_lines or []]
    out = []
    for line in final_lines:
        label = line["type"]
        for cand in pool:
            if cand["_used"] or cand.get("type") != line["type"]:
                continue
            amt = parse_amount(cand.get("amount"))
            if amt is not None and abs(abs(amt) - abs(line["amount"])) < 0.005:
                cand["_used"] = True
                label = cand.get("label") or label
                break
        out.append({"type": line["type"], "label": label, "amount": line["amount"]})
    return out


def build_factsheet(final: dict, raw: dict, provider: str, ocr_text: str | None = None) -> dict:
    """Compute every number Level 2 answers may use (see module docstring)."""
    tc, tt, cb = final.get("total_charges"), final.get("total_taxes"), final.get("current_bill")
    units = final.get("units_consumed")
    charges = _labelled(final.get("charges") or [], raw.get("charge_lines"))
    taxes = _labelled(final.get("taxes") or [], raw.get("tax_lines"))

    for c in charges:
        c["percent_of_total_charges"] = metric(r2(_pct(c["amount"], tc)), "total_charges is not printed or is 0")
    for t in taxes:
        t["percent_of_total_taxes"] = metric(r2(_pct(t["amount"], tt)), "total_taxes is not printed or is 0")

    by_type: dict[str, float] = {}
    for c in charges:
        by_type[c["type"]] = r2(by_type.get(c["type"], 0) + c["amount"])
    subsidies = [c["amount"] for c in charges if c["type"] == "subsidy"]

    cost_cb = _div(cb, units)
    cost_tc = _div(tc, units)
    breakdown = {
        "tax_share_pct": metric(r2(_pct(tt, cb)), "total_taxes or current_bill is not printed"),
        "charges_share_pct": metric(r2(_pct(tc, cb)), "total_charges or current_bill is not printed"),
        "charges_by_type": by_type,
        "subsidy_saved": metric(r2(abs(sum(subsidies))), None) if subsidies else metric(0.0),
        "estimate_cost_per_unit_from_current_bill": metric(r2(cost_cb), "current_bill or units_consumed is not available"),
        "estimate_cost_per_unit_from_total_charges": metric(r2(cost_tc), "total_charges or units_consumed is not available"),
        "note": "cost-per-unit figures are estimates (printed amount divided by units billed)",
    }

    within, after = final.get("payable_within_due_date"), final.get("payable_after_due_date")
    penalty = after - within if None not in (after, within) else None
    raw_after = [parse_amount(a) for a in raw.get("payable_after_due_date_amounts") or []]
    tiers = []
    for a in sorted({a for a in raw_after if a is not None}):
        extra = a - within if within is not None else None
        tiers.append({"payable": a, "extra_over_within_due": r2(extra), "extra_pct": r2(_pct(extra, within))})
    arrears = final.get("arrears")
    if arrears is None:
        arrears_status = metric(None, "arrears is not printed")
    else:
        arrears_status = metric("owed" if arrears > 0 else "credit" if arrears < 0 else "none")

    evidence = []
    if within is not None and within < 0:
        evidence.append("payable_within_due_date is negative (credit)")
    if arrears is not None and arrears < 0:
        evidence.append("arrears is negative (credit)")
    for row in raw.get("meter_rows") or []:
        lab = (row.get("label") or "").lower()
        if any(k in lab for k in ("import", "export", "net meter")):
            evidence.append(f"meter register labelled '{row.get('label')}'")
            break
    if ocr_text and "net meter" in ocr_text.lower().replace("_", " "):
        evidence.append("the bill text mentions net metering")
    if any((r.get("units") or "").strip().startswith(("-", "\u2212")) for r in raw.get("bill_history") or []):
        evidence.append("history shows negative units (export)")

    payment = {
        "late_penalty": metric(r2(penalty), "payable_after_due_date or payable_within_due_date is not printed"),
        "late_penalty_pct_of_within": metric(r2(_pct(penalty, within)), "payable amounts missing or within-due amount is 0"),
        "late_payment_tiers": tiers,
        "payable_after_due_date_text": raw.get("payable_after_due_date_text"),
        "days_issue_to_due": metric(_days_between(final.get("issue_date"), final.get("due_date")), "issue_date or due_date is not available"),
        "days_reading_to_issue": metric(_days_between(final.get("reading_date"), final.get("issue_date")), "reading_date or issue_date is not available"),
        "arrears_status": arrears_status,
        "net_metering": {"value": bool(evidence), "evidence": evidence, "reason": None},
    }

    fpa = [c for c in charges if c["type"] == "fpa"]
    fpa_total = sum(c["amount"] for c in fpa)
    fpa_info = {
        "lines": [{"label": c["label"], "amount": c["amount"]} for c in fpa],
        "total": metric(r2(fpa_total) if fpa else None, "no fuel adjustment (FPA/FCA) line is printed on this bill"),
    }

    return {
        "provider": provider,
        "bill_month": final.get("bill_month"),
        "level1": final,
        "charge_lines": charges,
        "tax_lines": taxes,
        "breakdown": breakdown,
        "fuel_adjustment": fpa_info,
        "payment": payment,
        "history": _history(final, raw, provider, cost_cb),
    }
