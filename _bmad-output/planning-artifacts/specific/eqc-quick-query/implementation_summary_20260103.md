# EQC Quick Query Tool & Base Info Refactoring Summary

Date: 2026-01-03

## Overview

This document summarizes the enhancements made to the EQC Quick Query tool and the underlying `enterprise.base_info` persistence logic. The primary goals were to standardize data storage, remove duplicate fields, ensure consistency between different lookup methods (Search vs. Direct ID), and fix the null `name` field issue in direct ID lookups.

## Key Changes

### 1. Database Schema Refactor (`001_initial_infrastructure.py`)

The `enterprise.base_info` table schema has been cleaned up to remove legacy duplicate columns that caused confusion and data inconsistency.

- **Removed Legacy Columns**:
  - `company_name` (Duplicate of `company_full_name`)
  - `reg_status` (Duplicate of `registered_status`)
  - `org_code` (Duplicate of `organization_code`)
  - `en_name` (Duplicate of `company_en_name`)
  - `former_name` (Duplicate of `company_former_name`)
- **Retained Standard Columns**:
  - `company_full_name`
  - `registered_status`
  - `organization_code`
  - `company_en_name`
  - `company_former_name`
- **Audit Fields**: Added `score` and `rank_score` to persist search relevance data.

### 2. Unified Parsing Logic (`base_info_parser.py`)

A new `BaseInfoParser` class was introduced to centralize all EQC API response parsing. This replaces ad-hoc parsing scattered across controllers and providers.

- **`parse_from_search_response`**:
  - Used for standard keyword searches.
  - Extracts all fields including `score`, `rank_score`, and `match_type`.
  - Populates `name` from the API's `name` field (if present).
- **`parse_from_find_depart_response`** (Solution C):
  - Used for **Direct ID lookups** (`lookup_by_id`) where full search metadata isn't available.
  - **Crucial Fix**: Explicitly sets the `name` field to equal `company_full_name`.
  - **Reasoning**: The `findDepart` API response structure differs from `search`. Explicit mapping ensures the `name` column in `base_info` is never NULL for these records.

### 3. Enhanced Persistence (`other_ops.py`)

The `upsert_base_info` method in `OtherOpsMixin` was updated to support the new schema and partial updates.

- **New Parameters**: Added `score`, `rank_score`, and `name`.
- **Partial Updates**: The SQL `ON CONFLICT DO UPDATE SET` clause now uses `COALESCE(EXCLUDED.field, base_info.field)`.
  - **Effect**: Existing non-null data in the database is **preserved** if the incoming update has a NULL value for that field. This prevents data loss when updating from a less detailed source.

### 4. Integration Updates

- **`EqcQueryController`**: Updated to use `BaseInfoParser`. When saving results from the GUI, it now passes the fully parsed object (including the fixed `name` field) to the repository.
- **`EqcProvider`**: Refactored to use `BaseInfoParser` for consistent behavior across ETL operations.

## Verification Results

### Name Field Population

- **Scenario**: User performs a Direct ID lookup (e.g., using `1000065057`) and saves the result.
- **Before**: The `name` column in `base_info` would be NULL because `findDepart` response doesn't strictly match the `search` response structure expected by the old logic.
- **After**: The `name` column is correctly populated with the company's full name.

### Data Consistency (Solution C)

Verified via `scripts/validation/verify_gui_base_info_consistency.py`:

- Comparing `raw_data` from Search vs. Direct ID (using `findDepart` as fallback).
- **Conclusion**: While structure differs, critical identification fields (`companyId`, `companyFullName`, `unite_code`) are present in both. The `BaseInfoParser` handles these structural differences transparently, ensuring downstream compatibility.

## Usage Examples

### 1. Keyword Search (Standard)

```python
# Returns ParsedBaseInfo with all search metadata
parsed = BaseInfoParser.parse_from_search_response(raw_search_json, ...)
# persisted: score=0.95, rank_score=0.95, match_type='全称精确匹配'
```

### 2. Direct ID Looup (Legacy/GUI)

```python
# Returns ParsedBaseInfo with direct mapping
parsed = BaseInfoParser.parse_from_find_depart_response(raw_find_depart, ...)
# persisted: score=None, rank_score=None, name='Company Full Name'
```
