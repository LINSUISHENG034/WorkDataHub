"""Unit tests for seed_loader module."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from work_data_hub.io.schema.seed_loader import _load_csv_seed_data, load_seed_data


class _RecordingConnection:
    """Lightweight stand-in for SQLAlchemy Connection."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, object]] = []

    def execute(self, statement: object, params: object = None) -> None:
        self.calls.append((statement, params))


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def test_load_csv_seed_data_supports_large_fields(tmp_path: Path) -> None:
    """Large JSON-like fields should load without csv field-limit errors."""
    csv_path = tmp_path / "base_info.csv"
    large_value = "x" * 200_000
    _write_csv(csv_path, ["id", "raw_business_info"], [["1", large_value]])

    conn = _RecordingConnection()
    inserted = _load_csv_seed_data(conn, csv_path, "base_info", "enterprise")

    assert inserted == 1
    assert len(conn.calls) == 1


def test_load_csv_seed_data_preserves_newline_characters(tmp_path: Path) -> None:
    """Field payload should preserve embedded newlines for data fidelity."""
    csv_path = tmp_path / "base_info.csv"
    payload = '{"note":"line1\\nline2"}\n{"nested":"value"}'
    _write_csv(csv_path, ["id", "raw_data"], [["1", payload]])

    conn = _RecordingConnection()
    _load_csv_seed_data(conn, csv_path, "base_info", "enterprise")

    _, params = conn.calls[0]
    assert isinstance(params, list)
    assert params[0]["param_1"] == payload


def test_load_csv_seed_data_maps_empty_string_to_none(tmp_path: Path) -> None:
    """Empty CSV values should map to None to support nullable DB columns."""
    csv_path = tmp_path / "small.csv"
    _write_csv(csv_path, ["id", "optional_col"], [["1", ""]])

    conn = _RecordingConnection()
    _load_csv_seed_data(conn, csv_path, "small", "enterprise")

    _, params = conn.calls[0]
    assert isinstance(params, list)
    assert params[0]["param_1"] is None


def test_load_seed_data_raises_when_csv_missing(tmp_path: Path) -> None:
    """resolve_seed_file miss should surface as FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="No seed CSV found"):
        load_seed_data(
            conn=_RecordingConnection(),
            table_name="missing_table",
            schema="enterprise",
            seeds_base_dir=tmp_path,
        )
