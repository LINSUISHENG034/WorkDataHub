# CLI Migration Guide - Story 6.2-P6

**Version**: 1.0
**Date**: 2025-12-14
**Story**: 6.2-P6 CLI Architecture Unification & Multi-Domain Batch Processing

## Overview

This guide helps you migrate from the old CLI commands to the new unified CLI architecture introduced in Story 6.2-P6.

## What Changed?

### Unified Entry Point

All CLI commands now use a single entry point with subcommands:

```bash
# New unified entry point
python -m work_data_hub.cli <command> [options]
```

### Command Structure

**Before (Old)**:
```bash
# Each module had its own entry point
python -m work_data_hub.orchestration.jobs --domain <domain> [options]
python -m work_data_hub.cli.eqc_refresh [options]
python -m work_data_hub.cli.cleanse_data [options]
python -m work_data_hub.io.auth.auto_eqc_auth
```

**After (New)**:
```bash
# All commands use unified entry point
python -m work_data_hub.cli etl --domains <domain> [options]
python -m work_data_hub.cli eqc-refresh [options]
python -m work_data_hub.cli cleanse [options]
python -m work_data_hub.cli auth refresh [options]
```

## Migration Examples

### ETL Jobs

#### Single Domain Processing

**Old Command**:
```bash
python -m work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --period 202411 \
  --mode delete_insert \
  --execute
```

**New Command**:
```bash
python -m work_data_hub.cli etl \
  --domains annuity_performance \
  --period 202411 \
  --mode delete_insert \
  --execute
```

**Key Changes**:
- Entry point: `orchestration.jobs` → `cli etl`
- Parameter: `--domain` → `--domains` (still accepts single value)
- All other options remain the same

#### Multi-Domain Processing (NEW Feature)

**New Capability**:
```bash
# Process multiple domains in one command
python -m work_data_hub.cli etl \
  --domains annuity_performance,annuity_income \
  --period 202411 \
  --mode append \
  --execute

# Process all configured domains
python -m work_data_hub.cli etl \
  --all-domains \
  --period 202411 \
  --mode append \
  --execute
```

**Behavior**:
- Domains are processed sequentially
- Continues on failure (logs error, proceeds to next domain)
- Returns exit code 1 if any domain fails
- Returns exit code 0 if all domains succeed
- Returns exit code 130 on user cancellation (Ctrl+C)

### EQC Data Refresh

**Old Command**:
```bash
python -m work_data_hub.cli.eqc_refresh --status
python -m work_data_hub.cli.eqc_refresh --refresh-stale
```

**New Command**:
```bash
python -m work_data_hub.cli eqc-refresh --status
python -m work_data_hub.cli eqc-refresh --refresh-stale
```

**Key Changes**:
- Entry point: `cli.eqc_refresh` → `cli eqc-refresh`
- All options remain the same

### Data Cleansing

**Old Command**:
```bash
python -m work_data_hub.cli.cleanse_data \
  --table business_info \
  --domain eqc_business_info \
  --dry-run
```

**New Command**:
```bash
python -m work_data_hub.cli cleanse \
  --table business_info \
  --domain eqc_business_info \
  --dry-run
```

**Key Changes**:
- Entry point: `cli.cleanse_data` → `cli cleanse`
- All options remain the same

### Authentication (EQC Token Refresh)

**Old Command**:
```bash
python -m work_data_hub.io.auth.auto_eqc_auth
```

**New Command**:
```bash
python -m work_data_hub.cli auth refresh
python -m work_data_hub.cli auth refresh --timeout 300
python -m work_data_hub.cli auth refresh --no-save
```

**Key Changes**:
- Entry point: `io.auth.auto_eqc_auth` → `cli auth refresh`
- New options: `--timeout`, `--no-save`, `--env-file`
- Better error messages and user feedback

## Domain Selection Rules

### Single-Domain Runs

Single-domain runs support both:
- **Configured data domains**: From `config/data_sources.yml` (e.g., `annuity_performance`, `annuity_income`)
- **Special orchestration domains**: `company_mapping`, `company_lookup_queue`, `reference_sync`

Example:
```bash
# Configured domain - OK
python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --execute

# Special orchestration domain - OK
python -m work_data_hub.cli etl --domains company_mapping --execute
```

### Multi-Domain Runs

Multi-domain runs only support:
- **Configured data domains**: From `config/data_sources.yml`

Special orchestration domains are **not allowed** in multi-domain runs:

```bash
# This will FAIL with validation error
python -m work_data_hub.cli etl --domains annuity_performance,company_mapping --execute
# Error: Invalid domains for multi-domain processing: company_mapping
```

### All-Domains Flag

The `--all-domains` flag automatically:
- Discovers all configured data domains from `config/data_sources.yml`
- Excludes special orchestration domains by design
- Processes domains in deterministic order

Example:
```bash
python -m work_data_hub.cli etl --all-domains --period 202411 --execute
# Processes: sample_trustee_performance, annuity_performance, annuity_income
# Excludes: company_mapping, company_lookup_queue, reference_sync
```

## Getting Help

### Command-Level Help

```bash
# Top-level help
python -m work_data_hub.cli --help

# Command-specific help
python -m work_data_hub.cli etl --help
python -m work_data_hub.cli auth --help
python -m work_data_hub.cli eqc-refresh --help
python -m work_data_hub.cli cleanse --help
```

### Subcommand Help

```bash
# Auth subcommand help
python -m work_data_hub.cli auth refresh --help
```

## Common Migration Patterns

### Pattern 1: Simple ETL Job

**Old**:
```bash
PYTHONPATH=src uv run --env-file .wdh_env \
  python -m work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --period 202411 \
  --execute
```

**New**:
```bash
PYTHONPATH=src uv run --env-file .wdh_env \
  python -m work_data_hub.cli etl \
  --domains annuity_performance \
  --period 202411 \
  --execute
```

### Pattern 2: Plan-Only Mode (Default)

**Old**:
```bash
python -m work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --period 202411 \
  --plan-only
```

**New**:
```bash
python -m work_data_hub.cli etl \
  --domains annuity_performance \
  --period 202411 \
  --plan-only
```

### Pattern 3: Batch Processing Multiple Domains (NEW)

**New Feature**:
```bash
# Process specific domains
python -m work_data_hub.cli etl \
  --domains annuity_performance,annuity_income \
  --period 202411 \
  --mode append \
  --execute

# Process all domains
python -m work_data_hub.cli etl \
  --all-domains \
  --period 202411 \
  --mode append \
  --execute
```

### Pattern 4: EQC Token Refresh

**Old**:
```bash
python -m work_data_hub.io.auth.auto_eqc_auth
```

**New**:
```bash
python -m work_data_hub.cli auth refresh
```

## Backward Compatibility

### Breaking Changes (AC7 Compliance)

The old ETL command entry point has been **removed** per AC7 requirement:

```bash
# This NO LONGER WORKS - main() removed from jobs.py
python -m work_data_hub.orchestration.jobs --domain annuity_performance --period 202411 --execute
```

**You MUST migrate to the new unified CLI:**

```bash
# Use this instead
python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --execute
```

### Other Commands Still Work (Deprecated)

These old entry points still work but are deprecated:

```bash
# These still work (but deprecated - use unified CLI instead)
python -m work_data_hub.cli.eqc_refresh --status
python -m work_data_hub.cli.cleanse_data --table business_info --domain eqc_business_info
python -m work_data_hub.io.auth.auto_eqc_auth
```

### Migration Status

| Old Command | Status | New Command |
|-------------|--------|-------------|
| `python -m work_data_hub.orchestration.jobs` | **REMOVED** | `python -m work_data_hub.cli etl` |
| `python -m work_data_hub.cli.eqc_refresh` | Deprecated | `python -m work_data_hub.cli eqc-refresh` |
| `python -m work_data_hub.cli.cleanse_data` | Deprecated | `python -m work_data_hub.cli cleanse` |
| `python -m work_data_hub.io.auth.auto_eqc_auth` | Deprecated | `python -m work_data_hub.cli auth refresh` |

## Troubleshooting

### Issue: "Command not found"

**Problem**:
```bash
python -m work_data_hub.cli etl --domains annuity_performance
# Error: No module named 'work_data_hub.cli'
```

**Solution**:
Ensure `PYTHONPATH=src` is set:
```bash
PYTHONPATH=src python -m work_data_hub.cli etl --domains annuity_performance
```

### Issue: "Invalid domains for multi-domain processing"

**Problem**:
```bash
python -m work_data_hub.cli etl --domains annuity_performance,company_mapping
# Error: Invalid domains for multi-domain processing: company_mapping
```

**Solution**:
Special orchestration domains can only be used in single-domain runs:
```bash
# Run separately
python -m work_data_hub.cli etl --domains annuity_performance --execute
python -m work_data_hub.cli etl --domains company_mapping --execute
```

### Issue: "Either --domains or --all-domains must be specified"

**Problem**:
```bash
python -m work_data_hub.cli etl --period 202411 --execute
# Error: Either --domains or --all-domains must be specified
```

**Solution**:
Always specify either `--domains` or `--all-domains`:
```bash
python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --execute
# OR
python -m work_data_hub.cli etl --all-domains --period 202411 --execute
```

## Testing Your Migration

### Step 1: Test with Plan-Only Mode

Always test with `--plan-only` first (default behavior):

```bash
python -m work_data_hub.cli etl \
  --domains annuity_performance \
  --period 202411 \
  --plan-only
```

### Step 2: Verify Output

Check that the execution plan looks correct:
- File discovery works
- Data processing completes
- SQL statements are generated
- No unexpected errors

### Step 3: Execute Against Database

Once verified, add `--execute` flag:

```bash
python -m work_data_hub.cli etl \
  --domains annuity_performance \
  --period 202411 \
  --execute
```

## New Features Summary

### 1. Multi-Domain Batch Processing

Process multiple domains in a single command:
```bash
python -m work_data_hub.cli etl --domains domain1,domain2,domain3 --execute
```

### 2. All-Domains Flag

Process all configured domains automatically:
```bash
python -m work_data_hub.cli etl --all-domains --execute
```

### 3. Unified Auth Command

Cleaner authentication workflow:
```bash
python -m work_data_hub.cli auth refresh
```

### 4. Better Error Messages

More informative error messages and validation:
- Domain validation with helpful suggestions
- Clear distinction between configured and special domains
- Better help text and examples

### 5. Consistent Command Structure

All commands follow the same pattern:
```bash
python -m work_data_hub.cli <command> [subcommand] [options]
```

## Questions or Issues?

If you encounter any issues during migration:

1. Check this guide for common patterns
2. Use `--help` to see available options
3. Test with `--plan-only` mode first
4. Report issues to the development team

## Related Documentation

- Story 6.2-P6: CLI Architecture Unification & Multi-Domain Batch Processing
- `docs/sprint-artifacts/stories/6.2-p6-cli-architecture-unification.md`
- Architecture documentation (to be updated)

---

**Last Updated**: 2025-12-14
**Story**: 6.2-P6
**Version**: 1.0
