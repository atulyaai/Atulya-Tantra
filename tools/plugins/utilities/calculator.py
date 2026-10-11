"""Safe arithmetic expression evaluator."""
from __future__ import annotations

import ast
import operator


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}


def calculate(expression: str) -> str:
    """Evaluate basic arithmetic only; never use eval or execute names/calls."""
    if len(expression) > 120:
        raise ValueError("That calculation is too long")
    try:
        tree = ast.parse(expression, mode="eval")

        def visit(node):
            if isinstance(node, ast.Expression):
                return visit(node.body)
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                return node.value
            if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
                left, right = visit(node.left), visit(node.right)
                if isinstance(node.op, ast.Pow) and abs(right) > 8:
                    raise ValueError("Exponent is too large")
                if abs(left) > 1e100 or abs(right) > 1e100:
                    raise ValueError("Number is too large")
                return _OPS[type(node.op)](left, right)
            if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
                return _OPS[type(node.op)](visit(node.operand))
            raise ValueError("Use numbers and basic arithmetic operators only")

        result = visit(tree)
    except (SyntaxError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError("I couldn't calculate that expression") from exc
    if not isinstance(result, (int, float)) or abs(result) > 1e100:
        raise ValueError("That result is outside the supported range")
    return f"{result:g}" if isinstance(result, float) else str(result)
