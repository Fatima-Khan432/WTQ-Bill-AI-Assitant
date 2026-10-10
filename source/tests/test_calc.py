import pytest

from bill_decoder.calc import CalcError, calculate


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("1 + 2 * 3", 7),
        ("(1877 / 12)", 1877 / 12),
        ("-5 + 2", -3),
        ("round(1877 / 12, 2)", 156.42),
        ("sum([1, 2, 3.5])", 6.5),
        ("max([141, 239, 203])", 239),
        ("min(3, 4)", 3),
        ("abs(-0.53)", 0.53),
        ("round(569.62 / 3430.24 * 100, 1)", 16.6),
    ],
)
def test_allowed(expr, expected):
    assert calculate(expr) == pytest.approx(expected)


@pytest.mark.parametrize(
    "expr",
    [
        "", "   ", "x + 1", "__import__('os').system('dir')", "open('f')", "(1).real",
        "[1,2][0]", "[x for x in [1]]", "'a' * 3", "round(1.5, digits=1)", "1 / 0",
        "2 ** 3", "10 % 3", "sum([[1]])", "max([])", "lambda: 1", "True + 1",
        "9" * 500, "1e308 * 10", "[1, 2]", "print(1)", "abs(1, 2)",
    ],
)
def test_rejected(expr):
    with pytest.raises(CalcError):
        calculate(expr)
