import json
from pathlib import Path

import pytest

from bill_decoder.assemble import assemble
from bill_decoder.csv_io import to_json_line
from bill_decoder.provider import provider_from_filename, provider_from_text
from bill_decoder.schema import FINAL_KEYS, RawBill, fallback_bill
from bill_decoder.validate import hard_check, soft_check

from score_level1 import score_bill

HERE = Path(__file__).parent
BILLS = ["KESC_0008", "KESC_0004", "LESCO_0006", "LESCO_0005", "IESCO_0004"]


def _load(bill):
    raw = RawBill.model_validate_json((HERE / "raw" / f"{bill}.json").read_text(encoding="utf-8"))
    want = json.loads((HERE / "expected" / f"{bill}.json").read_text(encoding="utf-8"))
    return raw, want


@pytest.mark.parametrize("bill", BILLS)
def test_assemble_matches_expected(bill):
    raw, want = _load(bill)
    provider = {"KESC": "KE", "LESCO": "LESCO", "IESCO": "IESCO"}[bill.split("_")[0]]
    assert hard_check(raw) == []
    warnings: list[str] = []
    got = assemble(raw, provider, warnings)
    assert score_bill(got, want) == []
    assert list(got.keys()) == FINAL_KEYS


def test_kesc_0008_is_identical_to_guide():
    raw, want = _load("KESC_0008")
    assert assemble(raw, "KE", []) == want


def test_lesco_0005_realigns_shifted_values():
    raw, _ = _load("LESCO_0005")
    warnings: list[str] = []
    got = assemble(raw, "LESCO", warnings)
    assert got["current_bill"] == 20726
    assert got["total_taxes"] == 3358.23
    assert got["payable_after_due_date"] is None
    assert any("re-assigned" in w for w in warnings)


def test_ke_multi_row_readings_are_column_sums_and_headline_units_used():
    raw, _ = _load("KESC_0004")
    got = assemble(raw, "KE", [])
    assert got["previous_reading"] == 12436.16 and got["current_reading"] == 14711.51
    assert got["units_consumed"] == 901


def test_layout_detection():
    from bill_decoder.provider import detect_layout

    assert detect_layout("LESCO", "LESCO CHARGES ... GOVT. CHARGES") == "web"
    assert detect_layout("LESCO", "Subsidies Total FPA W.E Credit Lock Open Credit") == "digital"
    assert detect_layout("LESCO", "Total Electricity Charges Taxes") == "standard"
    assert detect_layout("KE", "LESCO CHARGES GOVT. CHARGES") is None


def test_unparseable_amount_becomes_null_with_warning():
    raw, _ = _load("KESC_0008")
    raw.total_taxes = "84.76 %"
    warnings: list[str] = []
    got = assemble(raw, "KE", warnings)
    assert got["total_taxes"] is None
    assert any("total_taxes" in w for w in warnings)
    assert hard_check(raw)


def test_soft_check_flags_mismatch_only():
    raw, _ = _load("IESCO_0004")
    final = assemble(raw, "IESCO", [])
    # IESCO prints 2770 + 498 = 3268 but Current Bill 3267: within tolerance, no warning.
    assert not [w for w in soft_check(final) if "current_bill" in w]
    assert final["current_bill"] == 3267  # never recalculated


def test_fallback_row_is_complete():
    row = fallback_bill("KE")
    assert list(row.keys()) == FINAL_KEYS
    assert row["provider"] == "KE" and row["charges"] == [] and row["taxes"] == []
    assert all(row[k] is None for k in FINAL_KEYS if k not in {"provider", "charges", "taxes"})


def test_json_line_has_no_newlines():
    line = to_json_line({"a": "é", "b": [1, 2]})
    assert "\n" not in line and line == '{"a":"é","b":[1,2]}'


def test_provider_detection():
    assert provider_from_text("LAHORE ELECTRIC SUPPLY COMPANY LESCO") == "LESCO"
    assert provider_from_text("ISLAMABAD ELECTRIC SUPPLY COMPANY IESCO") == "IESCO"
    assert provider_from_text("KE NTN No. 1543137-1 KE GST") == "KE"
    assert provider_from_filename("x/KESC_0004.png") == "KE"
    assert provider_from_filename("IESCO_0002.jpg") == "IESCO"
