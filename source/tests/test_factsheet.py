import json
from pathlib import Path

import pytest

from bill_decoder.factsheet import build_factsheet, normalize_history

HERE = Path(__file__).parent


@pytest.fixture(scope="module")
def fs():
    final = json.loads((HERE / "expected" / "KESC_0008.json").read_text(encoding="utf-8"))
    raw = json.loads((HERE / "raw" / "KESC_0008.json").read_text(encoding="utf-8"))
    return build_factsheet(final, raw, "KE")


def test_breakdown(fs):
    b = fs["breakdown"]
    assert b["tax_share_pct"]["value"] == 16.61
    assert b["estimate_cost_per_unit_from_current_bill"]["value"] == 22.72


def test_history_previous_months(fs):
    prev = fs["history"]["previous_months"]
    assert prev["units"]["count"] == 12
    assert prev["units"]["total"]["value"] == 1877
    assert prev["units"]["average"]["value"] == 156.42
    assert prev["units"]["max"] == {"value": 239, "month": "July 2025", "reason": None}
    assert prev["units_above"]["200"]["count"] == 2
    assert prev["units_above"]["200"]["months"] == ["July 2025", "August 2025"]
    assert fs["history"]["history_scope"] == "including_current"


def test_history_including_current(fs):
    assert fs["history"]["including_current"]["units"]["count"] == 13


def test_change_vs_previous_month(fs):
    ch = fs["history"]["change_vs_previous_month"]["units"]
    assert ch["absolute"]["value"] == 36
    assert ch["percent"]["value"] == 31.3


def test_payment_facts(fs):
    p = fs["payment"]
    assert p["late_penalty"]["value"] == 286
    assert round(p["late_penalty_pct_of_within"]["value"], 1) == 8.3  # fact sheet keeps 2 dp (8.34)
    assert p["days_issue_to_due"]["value"] == 14
    assert p["arrears_status"]["value"] == "credit"


def test_nulls_have_reasons(fs):
    def walk(node):
        if isinstance(node, dict):
            if "value" in node and "reason" in node and node["value"] is None:
                assert isinstance(node["reason"], str) and node["reason"]
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(fs)


def test_missing_inputs_give_null_with_reason():
    final = {"bill_month": None, "units_consumed": None, "current_bill": None, "total_taxes": None,
             "charges": [], "taxes": []}
    out = build_factsheet(final, {}, "LESCO")
    assert out["breakdown"]["tax_share_pct"]["value"] is None
    assert out["breakdown"]["tax_share_pct"]["reason"]
    assert out["payment"]["late_penalty"]["reason"]


@pytest.mark.parametrize("raw_month,key", [("Sep25", "2025-09"), ("SEP25", "2025-09"), ("APR-25", "2025-04"),
                                           ("Aug 25", "2025-08"), ("08/26", "2026-08"), ("Apr 2025", "2025-04")])
def test_month_normalisation(raw_month, key):
    rows, bad = normalize_history([{"month": raw_month, "units": "-12", "bill": "1,000", "payment": None, "status": None}])
    assert rows[0]["month"] == key and rows[0]["units"] == -12 and rows[0]["bill"] == 1000 and not bad
