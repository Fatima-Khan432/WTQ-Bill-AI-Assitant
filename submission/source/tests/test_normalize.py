import pytest

from bill_decoder.normalize import (
    clean_text,
    parse_amount,
    parse_bill_month,
    parse_date,
    round_sum,
)


@pytest.mark.parametrize(
    "printed,expected",
    [
        ("Rs. 19,964", 19964),
        ("54770CR", -54770),
        ("38209CR", -38209),
        ("Rs. -91,877.02", -91877.02),
        ("39411 / 2", 39411),
        ("3,430.24", 3430.24),
        ("3430.00", 3430),
        ("0", 0),
        ("Rs. 0", 0),
        ("-0.53", -0.53),
        ("PKR 1,234", 1234),
        ("84.76 %", None),
        ("", None),
        ("-", None),
        (None, None),
        ("NOT TO BE PAID", None),
        ("abc", None),
    ],
)
def test_parse_amount(printed, expected):
    assert parse_amount(printed) == expected
    if isinstance(expected, int):
        assert isinstance(parse_amount(printed), int)


@pytest.mark.parametrize(
    "printed,expected",
    [
        ("26 AUG 26", "2026-08-26"),
        ("29-Jun-2026", "2026-06-29"),
        ("25-Jun-26", "2026-06-25"),
        ("13th Jul 2026", "2026-07-13"),
        ("14/09/26", "2026-09-14"),
        ("22nd Sep 2026", "2026-09-22"),
        ("08 OCT 26", "2026-10-08"),
        ("2026-04-03", "2026-04-03"),
        ("31/02/26", None),
        ("garbage", None),
        (None, None),
    ],
)
def test_parse_date(printed, expected):
    assert parse_date(printed) == expected


@pytest.mark.parametrize(
    "printed,expected",
    [
        ("AUG 2026", "2026-08"),
        ("Apr-26", "2026-04"),
        ("SEP 26", "2026-09"),
        ("JUL 2026", "2026-07"),
        ("MAR 2026", "2026-03"),
        ("nonsense", None),
        (None, None),
    ],
)
def test_parse_bill_month(printed, expected):
    assert parse_bill_month(printed) == expected


def test_round_sum_whole_is_int():
    assert round_sum([1200, 1156]) == 2356
    assert isinstance(round_sum([1200, 1156]), int)
    assert round_sum([760.44, 140.5]) == 900.94


def test_clean_text():
    assert clean_text("  A-1b(03)T ") == "A-1b(03)T"
    assert clean_text("   ") is None
    assert clean_text(None) is None


@pytest.mark.parametrize('printed,expected', [('Apr-2026', '2026-04'), ('APR 26', '2026-04'), ('Sep25', '2025-09'), ('08/26', '2026-08'), ('Aug 25', '2025-08')])
def test_bill_month_variants(printed, expected):
    assert parse_bill_month(printed) == expected

