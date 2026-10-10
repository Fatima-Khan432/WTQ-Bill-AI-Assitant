"""Parsing of printed bill strings into numbers, dates and bill months.

The LLM copies text exactly as printed; everything here is deterministic code.
Every function returns ``None`` instead of guessing when a value cannot be
parsed. Callers decide whether to log a warning.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

Number = int | float

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_CURRENCY_RE = re.compile(r"(?i)\b(?:rs|pkr)\b\.?|₨")
_NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


class NormalizeError(ValueError):
    """Raised by the strict variants when a printed value cannot be parsed."""


def to_number(value: Decimal) -> Number:
    """Whole values become ints, everything else a float as printed."""
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def parse_amount(text: str | None) -> Number | None:
    """Parse a printed amount.

    ``Rs. 19,964`` -> 19964, ``54770CR`` -> -54770, ``39411 / 2`` -> 39411.
    Returns None for empty text, ``-``, percentages or anything unparseable.
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s or s in {"-", "--", "—", "null", "None", "N/A", "n/a"}:
        return None
    if "%" in s:
        return None
    # Drop everything from "/" onwards ("39411 / 2").
    s = s.split("/", 1)[0]
    s = _CURRENCY_RE.sub("", s)
    s = s.replace(",", "").replace(" ", "").replace("\u00a0", "")
    # Unicode minus signs.
    s = s.replace("\u2212", "-").replace("\u2013", "-")
    negative = False
    upper = s.upper()
    if upper.endswith("CR"):
        negative = True
        s = s[:-2]
    elif upper.startswith("CR"):
        negative = True
        s = s[2:]
    if not s:
        return None
    # A trailing minus is occasionally printed ("1234-").
    if s.endswith("-") and not s.startswith("-"):
        s = "-" + s[:-1]
    if not _NUMBER_RE.match(s):
        return None
    try:
        value = Decimal(s)
    except InvalidOperation:
        return None
    if negative:
        value = -abs(value)
    return to_number(value)


def parse_amount_strict(text: str | None) -> Number | None:
    """Like :func:`parse_amount` but raise when non-empty text is unparseable."""
    result = parse_amount(text)
    if result is None and text is not None and _looks_numeric(text):
        raise NormalizeError(f"cannot parse amount: {text!r}")
    return result


def _looks_numeric(text: str) -> bool:
    """True if text contains digits and no obvious non-amount words."""
    s = str(text)
    return bool(re.search(r"\d", s)) and "%" not in s


def _month_from_name(name: str) -> int | None:
    return MONTHS.get(name.strip().lower()[:3])


def _expand_year(year: str) -> int:
    y = int(year)
    return 2000 + y if y < 100 else y


def _clean_date_text(text: str) -> str:
    s = str(text).strip()
    # Ordinal suffixes: 13th, 22nd, 1st, 3rd.
    s = re.sub(r"(?i)(\d)(?:st|nd|rd|th)\b", r"\1", s)
    s = s.replace(",", " ")
    return re.sub(r"\s+", " ", s).strip()


def _valid_date(year: int, month: int, day: int) -> str | None:
    import datetime

    try:
        datetime.date(year, month, day)
    except ValueError:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_date(text: str | None) -> str | None:
    """Parse a printed date into ``YYYY-MM-DD``.

    Two-digit years become 20YY. Numeric dates are read as DD/MM/YY.
    """
    if text is None:
        return None
    s = _clean_date_text(text)
    if not s:
        return None

    # ISO: 2026-04-03
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return _valid_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # 26 AUG 26 / 29-Jun-2026 / 25-Jun-26 / 13 Jul 2026
    m = re.fullmatch(r"(\d{1,2})[\s\-/.]*([A-Za-z]{3,9})\.?[\s\-/.]*(\d{2}|\d{4})", s)
    if m:
        month = _month_from_name(m.group(2))
        if month:
            return _valid_date(_expand_year(m.group(3)), month, int(m.group(1)))

    # Jun 29 2026 / Jun-29-2026
    m = re.fullmatch(r"([A-Za-z]{3,9})\.?[\s\-/.]*(\d{1,2})[\s\-/.]+(\d{2}|\d{4})", s)
    if m:
        month = _month_from_name(m.group(1))
        if month:
            return _valid_date(_expand_year(m.group(3)), month, int(m.group(2)))

    # 14/09/26, 14-09-2026, 14.09.26 (DD/MM/YY)
    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2}|\d{4})", s)
    if m:
        return _valid_date(_expand_year(m.group(3)), int(m.group(2)), int(m.group(1)))

    return None


def parse_bill_month(text: str | None) -> str | None:
    """Parse a printed bill month into ``YYYY-MM``.

    ``AUG 2026`` -> 2026-08, ``Apr-26`` -> 2026-04, ``SEP 26`` -> 2026-09.
    """
    if text is None:
        return None
    s = _clean_date_text(text)
    if not s:
        return None

    m = re.fullmatch(r"(\d{4})-(\d{1,2})", s)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}"

    m = re.fullmatch(r"([A-Za-z]{3,9})\.?[\s\-/.]*(\d{2}|\d{4})", s)
    if m:
        month = _month_from_name(m.group(1))
        if month:
            return f"{_expand_year(m.group(2)):04d}-{month:02d}"

    m = re.fullmatch(r"(\d{1,2})[\s\-/.](\d{2}|\d{4})", s)
    if m and 1 <= int(m.group(1)) <= 12:
        return f"{_expand_year(m.group(2)):04d}-{int(m.group(1)):02d}"

    return None


def number_in(text: str | None) -> Number | None:
    """First plain number inside free text: ``901 units =`` -> 901, ``10 kW`` -> 10."""
    if text is None:
        return None
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(text))
    if not m:
        return None
    return parse_amount(m.group(0))


def clean_text(text: str | None) -> str | None:
    """Trim a printed string; empty text becomes None. Case is preserved."""
    if text is None:
        return None
    s = re.sub(r"\s+", " ", str(text)).strip()
    return s or None


def round_sum(values: list[Number]) -> Number:
    """Sum rounded to 2 decimals; a whole result is returned as an int."""
    total = sum(Decimal(str(v)) for v in values)
    return to_number(total.quantize(Decimal("0.01")))
