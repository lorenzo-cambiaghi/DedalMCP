"""AST-based safe arithmetic expression evaluator.

Used by composite/v1 to evaluate strings like "x/2", "y*0.85", "max(x, 1)".
NO eval/exec. Only whitelisted AST nodes and a fixed function namespace.
"""

from __future__ import annotations

import ast
import operator
from typing import Any

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

_ALLOWED_CALLS = {
    "min": min,
    "max": max,
    "abs": abs,
    "int": int,
    "float": float,
    "round": round,
}


class UnsafeExpressionError(ValueError):
    pass


def safe_eval(expr: str, variables: dict[str, Any]) -> Any:
    """Evaluate *expr* with *variables* as the only available names.

    Raises UnsafeExpressionError on any disallowed construct.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise UnsafeExpressionError(f"Invalid expression {expr!r}: {e}") from e
    return _eval_node(tree.body, variables, expr)


def _eval_node(node: ast.AST, variables: dict[str, Any], expr: str) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise UnsafeExpressionError(
            f"Only numeric constants allowed in {expr!r}, got {type(node.value).__name__}"
        )

    if isinstance(node, ast.Name):
        if node.id in variables:
            return variables[node.id]
        if node.id in _ALLOWED_CALLS:
            return _ALLOWED_CALLS[node.id]
        raise UnsafeExpressionError(
            f"Unknown name {node.id!r} in expression {expr!r} (available: {sorted(variables)})"
        )

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise UnsafeExpressionError(f"Operator {op_type.__name__} not allowed in {expr!r}")
        left = _eval_node(node.left, variables, expr)
        right = _eval_node(node.right, variables, expr)
        return _BIN_OPS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise UnsafeExpressionError(f"Unary {op_type.__name__} not allowed in {expr!r}")
        return _UNARY_OPS[op_type](_eval_node(node.operand, variables, expr))

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, variables, expr)
        for op, comparator in zip(node.ops, node.comparators):
            op_type = type(op)
            if op_type not in _CMP_OPS:
                raise UnsafeExpressionError(f"Comparison {op_type.__name__} not allowed")
            right = _eval_node(comparator, variables, expr)
            if not _CMP_OPS[op_type](left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.IfExp):
        test = _eval_node(node.test, variables, expr)
        return _eval_node(node.body if test else node.orelse, variables, expr)

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_CALLS:
            raise UnsafeExpressionError(
                f"Only calls to {sorted(_ALLOWED_CALLS)} allowed, got {ast.dump(node.func)!r}"
            )
        if node.keywords:
            raise UnsafeExpressionError("Keyword args not allowed in expressions")
        args = [_eval_node(a, variables, expr) for a in node.args]
        return _ALLOWED_CALLS[node.func.id](*args)

    raise UnsafeExpressionError(
        f"Disallowed AST node {type(node).__name__} in expression {expr!r}"
    )


def eval_value(value: Any, variables: dict[str, Any]) -> Any:
    """If *value* is a string, evaluate it as expression; otherwise return as-is."""
    if isinstance(value, str):
        return safe_eval(value, variables)
    return value
