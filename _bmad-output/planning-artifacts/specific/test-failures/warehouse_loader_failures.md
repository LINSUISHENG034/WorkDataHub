# Warehouse Loader Test Failures Report

**Date**: 2025-12-22
**Component**: `io/loader/warehouse_loader`
**Status**: 3 Failures analyzed

## Overview
During the verification of Story 7.2 (IO Layer Modularization), several tests in `tests/io/test_warehouse_loader.py` failed. Detailed analysis suggests a common root cause related to Python import path resolution and class identity mismatches following the file decomposition.

## Summary of Failures

| Test Name | Error Type | Message | Root Cause Hypothesis |
|-----------|------------|---------|----------------------|
| `test_load_validation_errors` | `DataWarehouseLoaderError` (Uncaught) | `Invalid mode: invalid` | `pytest.raises` failed to catch exception due to class mismatch (`src.` prefix vs standard import). |
| `test_load_dataframe_executes_batches` | `AssertionError` | `assert isinstance(result, LoadResult)` failed | `LoadResult` class mismatch between test import and runtime object. |
| `test_dataframe_load_rolls_back_on_error` | `DataWarehouseLoaderError` (Uncaught) | `Load failed... invalid input syntax` | `pytest.raises` failed to catch exception due to class mismatch. |

## Detailed Analysis

### 1. Class Identity Mismatch
All three failures are symptomatic of Python treating the same class as two different types because they were imported via different paths.

*   **Test Import Path**: likely `src.work_data_hub.io.loader...` or similar.
*   **Runtime Import Path**: `work_data_hub.io.loader...` (via `uv run`).

When `pytest.raises(ErrorClass)` checks if an exception matches `ErrorClass`, it uses strict type identity. If `ErrorClass` is imported as `src.package.Error` in the test, but the code raises `package.Error`, the check fails even if they look identical.

Similarly, `isinstance(obj, Class)` fails if `obj` is an instance of `package.Class` but `Class` is `src.package.Class`.

### 2. Failure Evidence
From `warehouse_loader_failures.log`:

**Failure 1:**
```python
>           raise DataWarehouseLoaderError(f"Invalid mode: {mode}")
E           work_data_hub.io.loader.models.DataWarehouseLoaderError: Invalid mode: invalid
```
The exception trace shows the full path `work_data_hub.io.loader.models.DataWarehouseLoaderError`. The test expected to catch it but didn't, implying the test thinks `DataWarehouseLoaderError` is something else.

**Failure 2:**
```python
>       assert isinstance(result, LoadResult)
E       AssertionError: assert False
E        +  where False = isinstance(LoadResult(..., errors=[]), LoadResult)
```
The object string repr `LoadResult(...)` confirms it *is* a LoadResult object, just not the *same* `LoadResult` class definition as the test has.

## Remediation Plan

1.  **Standardize Imports in Tests**:
    *   Review `tests/io/test_warehouse_loader.py`.
    *   Remove `src.` prefix from imports if present (e.g., change `from src.work_data_hub...` to `from work_data_hub...`).
    *   Ensure the test runner (`uv run pytest`) has the `src` directory in `PYTHONPATH` so it can resolve `work_data_hub` directly.

2.  **Verify Facade Re-exports**:
    *   Ensure `io/loader/warehouse_loader.py` and `io/loader/__init__.py` correctly re-export the classes from the sub-modules (`models.py`, `core.py`).
    *   Consumers should ideally import from the public API (the facade or `__init__`) rather than internal modules (`models`), but consistent use of either is fine as long as the import *root* (`src` vs no `src`) is consistent.

## Reproduction
To reproduce and verify the fix:
```bash
uv run pytest tests/io/test_warehouse_loader.py
```
