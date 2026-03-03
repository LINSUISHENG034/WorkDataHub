"""Unit tests for scripts.seed_data.export_seed_csv."""

from __future__ import annotations

import pytest

from scripts.seed_data.export_seed_csv import parse_table_identifier


def test_parse_table_identifier_accepts_valid_identifier() -> None:
    """Parser should return schema/table pair for standard identifiers."""
    schema, table = parse_table_identifier("enterprise.base_info")
    assert schema == "enterprise"
    assert table == "base_info"


def test_parse_table_identifier_rejects_missing_separator() -> None:
    """Identifier must follow schema.table format."""
    with pytest.raises(ValueError, match="Use schema.table"):
        parse_table_identifier("base_info")


def test_parse_table_identifier_rejects_invalid_schema() -> None:
    """Schema identifier should reject unsafe characters."""
    with pytest.raises(ValueError, match="Invalid schema identifier"):
        parse_table_identifier("enterprise-prod.base_info")


def test_parse_table_identifier_rejects_injection_payload() -> None:
    """Table identifier should reject SQL injection payloads."""
    with pytest.raises(ValueError, match="Invalid table identifier"):
        parse_table_identifier('enterprise.base_info";SELECT pg_sleep(1);--')
