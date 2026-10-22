"""Regression tests for SQLAlchemy Row and RowMapping serialization."""
from __future__ import annotations

import ast
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "apps" / "api" / "app" / "routes" / "commerce.py"


def load_out_function():
    """Load only the serializer to avoid initializing production settings/engines."""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "out"
    )
    module = ast.Module(body=[function], type_ignores=[])
    namespace: dict[str, Any] = {
        "Any": Any,
        "Mapping": Mapping,
        "Decimal": Decimal,
    }
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), "exec"), namespace)
    return namespace["out"]


def test_out_accepts_sqlalchemy_row_mapping():
    out = load_out_function()
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as connection:
        row = connection.execute(text("SELECT 17 AS quantity, 'UGX' AS currency")).mappings().one()
        assert out(row) == {"quantity": 17, "currency": "UGX"}


def test_out_accepts_sqlalchemy_row():
    out = load_out_function()
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as connection:
        row = connection.execute(text("SELECT 17 AS quantity, 'UGX' AS currency")).one()
        assert out(row) == {"quantity": 17, "currency": "UGX"}


def test_out_preserves_decimal_string_formatting_for_mappings():
    out = load_out_function()
    assert out({"amount": Decimal("12.3400")}) == {"amount": "12.3400"}
