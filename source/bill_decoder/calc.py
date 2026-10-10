"""Safe arithmetic evaluator used as the Level 2 `calculate` tool.

Only numeric literals, lists, ``+ - * /``, unary minus, parentheses and the functions
``round``, ``sum``, ``min``, ``max`` and ``abs`` are allowed. Everything else
(names, attributes, subscripts, comprehensions, keyword arguments, strings, ...) is rejected.
"""

from __future__ import annotations

import ast
import math

MAX_EXPRESSION_LENGTH = 400
MAX_ABS_VALUE = 1e15
MAX_NODES = 200
ALLOWED_FUNCS = {"round", "sum", "min", "max", "abs"}


class CalcError(ValueError):
    """The expression is not allowed or cannot be evaluated."""


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalcError("only numbers are allowed")
    if isinstance(value, float) and not math.isfinite(value):
        raise CalcError("result is not finite")
    if abs(value) > MAX_ABS_VALUE:
        raise CalcError("number too large")
    return value


def _eval(node):
    if isinstance(node, ast.Constant):
        return _number(node.value)
    if isinstance(node, ast.List):
        return [_eval(e) for e in node.elts]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _eval(node.operand)
        if isinstance(v, list):
            raise CalcError("unary operators apply to numbers only")
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(left, list) or isinstance(right, list):
            raise CalcError("operators apply to numbers only")
        if isinstance(node.op, ast.Add):
            return _number(left + right)
        if isinstance(node.op, ast.Sub):
            return _number(left - right)
        if isinstance(node.op, ast.Mult):
            return _number(left * right)
        if right == 0:
            raise CalcError("division by zero")
        return _number(left / right)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCS:
            raise CalcError("function not allowed")
        if node.keywords:
            raise CalcError("keyword arguments are not allowed")
        args = [_eval(a) for a in node.args]
        name = node.func.id
        if name == "round":
            if not 1 <= len(args) <= 2 or isinstance(args[0], list):
                raise CalcError("round takes a number and optional digits")
            digits = args[1] if len(args) == 2 else 0
            if isinstance(digits, list) or int(digits) != digits or not -6 <= digits <= 6:
                raise CalcError("round digits must be a small integer")
            return _number(round(args[0], int(digits)))
        if name == "abs":
            if len(args) != 1 or isinstance(args[0], list):
                raise CalcError("abs takes one number")
            return _number(abs(args[0]))
        # sum / min / max: one list, or several numbers
        values = args[0] if len(args) == 1 and isinstance(args[0], list) else args
        if not values or any(isinstance(v, list) for v in values):
            raise CalcError(f"{name} needs a non-empty list of numbers")
        if name == "sum":
            return _number(sum(values))
        return _number(min(values) if name == "min" else max(values))
    raise CalcError("expression not allowed")


def calculate(expression: str) -> float:
    """Evaluate a safe arithmetic expression and return a number."""
    if not isinstance(expression, str) or not expression.strip():
        raise CalcError("empty expression")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise CalcError("expression too long")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise CalcError(f"invalid expression: {exc.msg}") from exc
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise CalcError("expression too complex")
    result = _eval(tree.body)
    if isinstance(result, list):
        raise CalcError("result must be a number, not a list")
    return float(result)
