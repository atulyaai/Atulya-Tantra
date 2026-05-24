"""Small AST-based evaluator for agent math expressions.

This intentionally supports only arithmetic expressions and a short list of
pure math functions. It never calls Python's eval/exec machinery.
"""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Callable
from typing import Any


class SafeExpressionError(ValueError):
    """Raised when an expression uses unsupported syntax or values."""


_BIN_OPS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

def _safe_pow(base: Any, exp: Any, mod: Any = None) -> Any:
    if not isinstance(exp, (int, float)):
        raise SafeExpressionError("exponent must be a number")
    if abs(exp) > 12:
        raise SafeExpressionError("exponent is too large")
    if mod is not None:
        return pow(base, exp, mod)
    return pow(base, exp)


_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "pow": _safe_pow,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "ceil": math.ceil,
    "floor": math.floor,
}

_CONSTANTS = {"pi": math.pi, "e": math.e}


def safe_math_eval(expression: str) -> Any:
    """Evaluate a restricted arithmetic expression."""

    if len(expression) > 512:
        raise SafeExpressionError("expression is too long")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise SafeExpressionError("invalid expression") from exc
    return _eval_node(tree.body)


def safe_expression_output(expression: str) -> str:
    """Return a printable result or a user-facing validation error."""

    try:
        return str(safe_math_eval(expression))
    except Exception as exc:
        return f"Expression blocked: {str(exc)[:200]}"


def _eval_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise SafeExpressionError("only numeric literals are allowed")

    if isinstance(node, ast.Name):
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        raise SafeExpressionError(f"unknown name: {node.id}")

    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise SafeExpressionError("operator is not allowed")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 12:
            raise SafeExpressionError("exponent is too large")
        return op(left, right)

    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise SafeExpressionError("operator is not allowed")
        return op(_eval_node(node.operand))

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise SafeExpressionError("only named math functions are allowed")
        func = _FUNCTIONS.get(node.func.id)
        if func is None:
            raise SafeExpressionError(f"function is not allowed: {node.func.id}")
        if node.keywords:
            raise SafeExpressionError("keyword arguments are not allowed")
        args = [_eval_node(arg) for arg in node.args]
        return func(*args)

    if isinstance(node, (ast.Tuple, ast.List)):
        return [_eval_node(elt) for elt in node.elts]

    raise SafeExpressionError(f"syntax is not allowed: {type(node).__name__}")
