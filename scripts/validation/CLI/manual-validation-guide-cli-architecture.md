# Manual Validation Guide: CLI Architecture Unification & Multi-Domain Batch Processing

**Sprint Change Proposal**: `sprint-change-proposal-2025-12-14-cli-architecture.md`
**Story**: 6.2-P6
**Date**: 2025-12-16
**Validator**: [Your Name]

---

## 1. Overview

This guide provides step-by-step manual validation procedures for the CLI Architecture Unification feature implemented in Story 6.2-P6. The validation focuses on **actually running commands and examining real output data** rather than running automated tests.

### 1.1 Core Features to Validate

| Feature ID | Feature Description | Priority |
|------------|---------------------|----------|
| F1 | Unified CLI entry point (`python -m work_data_hub.cli`) | Critical |
| F2 | ETL CLI with single-domain processing | Critical |
| F3 | ETL CLI with multi-domain batch processing | Critical |
| F4 | ETL CLI with `--all-domains` flag | High |
| F5 | Auth CLI migration | Medium |
| F6 | EQC refresh integration | Medium |
| F7 | Data cleanse integration | Medium |

### 1.2 Prerequisites

```bash
# 1. Ensure virtual environment is active
cd E:\Projects\WorkDataHub

# 2. Verify database connection (PostgreSQL)
# Check .wdh_env file has correct database credentials

# 3. Verify test data exists
ls tests/fixtures/real_data/
# Expected: 202311, 202411, 202412, 202501, 202502, 202510 directories
```

---

## 2. Validation Procedures

### 2.1 [F1] Unified CLI Entry Point Validation

**Objective**: Verify the unified CLI entry point works and displays help correctly.

#### Step 1: Verify CLI Entry Point Exists

```bash
PYTHONPATH=src uv run python -m work_data_hub.cli --help
```

**Expected Output**:
```
usage: work_data_hub.cli [-h] {etl,auth,eqc-refresh,cleanse} ...

WorkDataHub CLI - Unified command-line interface

commands:
  {etl,auth,eqc-refresh,cleanse}
    etl                 Run ETL jobs (single or multi-domain)
    auth                Authentication operations
    eqc-refresh         EQC data refresh operations
    cleanse             Data cleansing operations
```

**Validation Criteria**:
- [ ] Command executes without import errors
- [ ] All 4 subcommands listed (etl, auth, eqc-refresh, cleanse)
- [ ] Help text displays examples

#### Step 2: Verify Each Subcommand Help

```bash
# ETL help
PYTHONPATH=src uv run python -m work_data_hub.cli etl --help

# Auth help
PYTHONPATH=src uv run python -m work_data_hub.cli auth --help

# EQC refresh help
PYTHONPATH=src uv run python -m work_data_hub.cli eqc-refresh --help

# Cleanse help
PYTHONPATH=src uv run python -m work_data_hub.cli cleanse --help
```

**Validation Criteria**:
- [ ] Each subcommand displays its own help without errors
- [ ] ETL help shows `--domains`, `--all-domains`, `--period`, `--execute` options
- [ ] Auth help shows `refresh` subcommand

---

### 2.2 [F2] Single-Domain ETL Processing Validation

**Objective**: Verify single-domain ETL works identically to the old command format.

#### Step 1: Plan-Only Mode (Safe Test)

```bash
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl \
    --domains annuity_performance \
    --period 202411 \
    --mode delete_insert
```

**Expected Output**:
```
🚀 Starting annuity_performance job...
   Domain: annuity_performance
   Mode: delete_insert
   Execute: False
   Plan-only: True
   ...

📋 SQL Execution Plan:
------------------------------
1. delete_insert:
   DELETE FROM business."规模明细" WHERE ...
   Parameters: X values
...
```

**Validation Criteria**:
- [ ] Job starts without import errors
- [ ] Shows "Plan-only: True" (default safe mode)
- [ ] Displays SQL execution plan without database changes
- [ ] Discovers files from `tests/fixtures/real_data/202411/收集数据/数据采集/V1/`

#### Step 2: Verify File Discovery Output

**Check the discovered files message**:
- [ ] File pattern matches `*规模收入数据*.xlsx`
- [ ] Version folder `V1` correctly selected (highest_number strategy)
- [ ] Sheet `规模明细` correctly identified

#### Step 3: Execute Mode (Database Changes)

> **WARNING**: This modifies the database. Ensure test database is used.

```bash
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl \
    --domains annuity_performance \
    --period 202411 \
    --mode delete_insert \
    --execute
```

**Validation Criteria**:
- [ ] Shows "Execute: True", "Plan-only: False"
- [ ] Connects to database successfully
- [ ] Reports rows deleted and inserted
- [ ] Job completes with "✅ Job completed successfully: True"

#### Step 4: Verify Database Changes

```sql
-- Run this in psql or database client
SELECT COUNT(*) FROM business."规模明细" WHERE 月度 = '202411';
```

**Validation Criteria**:
- [ ] Row count > 0 indicates data was loaded
- [ ] Data has expected columns (月度, 计划代码, 组合代码, etc.)

---

### 2.3 [F3] Multi-Domain Batch Processing Validation

**Objective**: Verify comma-separated domains are processed sequentially.

#### Step 1: Multi-Domain Plan Mode

```bash
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl \
    --domains annuity_performance,annuity_income \
    --period 202411 \
    --mode delete_insert
```

**Expected Output**:
```
📋 Multi-domain batch processing: annuity_performance, annuity_income
   Total: 2 domains
==================================================

==================================================
Processing domain 1/2: annuity_performance
==================================================
🚀 Starting annuity_performance job...
...
✅ Domain annuity_performance completed successfully

==================================================
Processing domain 2/2: annuity_income
==================================================
🚀 Starting annuity_income job...
...
✅ Domain annuity_income completed successfully

==================================================
📊 MULTI-DOMAIN BATCH PROCESSING SUMMARY
==================================================
Total domains: 2
Successful: 2
Failed: 0

Per-domain results:
  ✅ annuity_performance: SUCCESS
  ✅ annuity_income: SUCCESS
==================================================
🎉 Multi-domain processing completed successfully
```

**Validation Criteria**:
- [ ] Shows "Multi-domain batch processing" header
- [ ] Processes domains sequentially (1/2, 2/2)
- [ ] Each domain shows its own job start message
- [ ] Summary shows per-domain results
- [ ] Exit code 0 when all succeed

#### Step 2: Multi-Domain with Failure Handling

> Test resilience by using an invalid domain in the mix.

```bash
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl \
    --domains annuity_performance,invalid_domain,annuity_income \
    --period 202411
```

**Expected Output**:
```
❌ Invalid domains for multi-domain processing: invalid_domain
   Multi-domain runs only support configured data domains from config/data_sources.yml
```

**Validation Criteria**:
- [ ] Invalid domain detected before processing starts
- [ ] Error message explains valid domains are from config
- [ ] No partial processing occurs

---

### 2.4 [F4] All-Domains Processing Validation

**Objective**: Verify `--all-domains` processes all configured domains.

#### Step 1: List All Configured Domains

```bash
# First check what domains are configured
cat config/data_sources.yml | grep -E "^  [a-z_]+:" | head -10
```

**Expected domains**: `sample_trustee_performance`, `annuity_performance`, `annuity_income`

#### Step 2: Execute All-Domains (Plan Mode)

```bash
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl \
    --all-domains \
    --period 202411
```

**Expected Output**:
```
📋 Processing all configured domains: sample_trustee_performance, annuity_performance, annuity_income
   Total: 3 domains
==================================================
...
```

**Validation Criteria**:
- [ ] All configured data domains are listed
- [ ] Special orchestration domains (company_mapping, etc.) are excluded
- [ ] Each domain is processed sequentially
- [ ] Summary shows total count

#### Step 3: Mutual Exclusivity Check

```bash
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl \
    --domains annuity_performance \
    --all-domains \
    --period 202411
```

**Expected Output**:
```
error: Cannot specify both --domains and --all-domains
```

**Validation Criteria**:
- [ ] Error raised when both flags used
- [ ] Clear error message

---

### 2.5 [F5] Auth CLI Migration Validation

**Objective**: Verify auth commands work through unified CLI.

#### Step 1: Auth Help Display

```bash
PYTHONPATH=src uv run python -m work_data_hub.cli auth --help
```

**Expected Output**:
```
usage: work_data_hub.cli auth [-h] {refresh} ...

operations:
  {refresh}
    refresh             Refresh EQC authentication token via QR code login
```

#### Step 2: Auth Refresh (Non-Interactive Check)

> Note: Actual token refresh requires QR code scanning, so we only verify the command starts correctly.

```bash
# This will start browser automation - cancel with Ctrl+C after verifying it starts
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli auth refresh --timeout 5
```

**Validation Criteria**:
- [ ] Command starts without import errors
- [ ] Shows "🔐 Starting EQC Authentication Token Refresh..."
- [ ] Displays timeout value (5 seconds)
- [ ] Mentions QR code scanning instructions

---

### 2.6 [F6] EQC Refresh Integration Validation

**Objective**: Verify EQC refresh works through unified CLI.

#### Step 1: Status Check (Safe, Read-Only)

```bash
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli eqc-refresh --status
```

**Expected Output**:
```
============================================================
EQC Data Freshness Status
============================================================
Threshold: 30 days
Total Companies: XXX
Fresh (within threshold): XXX
Stale (older than threshold): XXX
Never Updated: XXX
============================================================
```

**Validation Criteria**:
- [ ] Connects to database successfully
- [ ] Shows freshness statistics
- [ ] No errors during execution

#### Step 2: Dry Run Refresh

```bash
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli eqc-refresh \
    --refresh-stale \
    --dry-run
```

**Validation Criteria**:
- [ ] Shows "[DRY RUN]" prefix
- [ ] Lists companies that would be refreshed
- [ ] No database changes made

---

### 2.7 [F7] Data Cleanse Integration Validation

**Objective**: Verify data cleansing works through unified CLI.

#### Step 1: Cleanse Help Display

```bash
PYTHONPATH=src uv run python -m work_data_hub.cli cleanse --help
```

**Expected Output**:
```
usage: work_data_hub.cli.cleanse_data [-h] --table {business_info,biz_label,all} ...
```

#### Step 2: Dry Run Cleanse

```bash
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli cleanse \
    --table business_info \
    --batch-size 10 \
    --limit 5 \
    --dry-run
```

**Validation Criteria**:
- [ ] Shows "[DRY RUN]" prefix
- [ ] Processes limited records (5 max)
- [ ] Reports success/failure counts
- [ ] No database changes made

---

## 3. Command Migration Verification

### 3.1 Old vs New Command Comparison

| Test Case | Old Command | New Command | Status |
|-----------|-------------|-------------|--------|
| Single domain ETL | `python -m work_data_hub.orchestration.jobs --domain X` | `python -m work_data_hub.cli etl --domains X` | [ ] Verified |
| Auth refresh | `python -m work_data_hub.io.auth.auto_eqc_auth` | `python -m work_data_hub.cli auth refresh` | [ ] Verified |
| Multi-domain | N/A | `python -m work_data_hub.cli etl --domains X,Y` | [ ] NEW |
| All domains | N/A | `python -m work_data_hub.cli etl --all-domains` | [ ] NEW |

### 3.2 Old Command Removal Verification

```bash
# These commands should NO LONGER work (main() removed):
PYTHONPATH=src uv run python -m work_data_hub.orchestration.jobs --help
```

**Expected**: Should fail or show deprecation notice.

**Validation Criteria**:
- [ ] Old entry point in `orchestration/jobs.py` no longer has `main()` function
- [ ] Direct execution fails appropriately

---

## 4. Issues and Findings Log

### 4.1 Issues Discovered

| Issue ID | Severity | Description | Location | Suggested Fix |
|----------|----------|-------------|----------|---------------|
| I001 | | | | |
| I002 | | | | |

### 4.2 Pseudo-Implementation Detection

| Component | Expected Behavior | Actual Behavior | Status |
|-----------|------------------|-----------------|--------|
| ETL multi-domain | Sequential processing with summary | | [ ] |
| Domain validation | Reject invalid domains | | [ ] |
| All-domains exclusion | Exclude special domains | | [ ] |

---

## 5. Database Verification Queries

After running ETL commands with `--execute`, verify data in database:

```sql
-- Check annuity_performance data loaded
SELECT COUNT(*), 月度
FROM business."规模明细"
GROUP BY 月度
ORDER BY 月度 DESC
LIMIT 5;

-- Check annuity_income data loaded
SELECT COUNT(*), 月度
FROM business."收入明细"
GROUP BY 月度
ORDER BY 月度 DESC
LIMIT 5;

-- Check sample_trustee_performance data
SELECT COUNT(*) FROM sample.sample_trustee_performance;

-- Verify reference backfill (年金计划)
SELECT COUNT(*) FROM mapping."年金计划";

-- Verify reference backfill (组合计划)
SELECT COUNT(*) FROM mapping."组合计划";
```

---

## 6. Validation Summary

### 6.1 Feature Validation Matrix

| Feature | Plan Mode | Execute Mode | Error Handling | Documentation |
|---------|-----------|--------------|----------------|---------------|
| F1: Unified CLI | [ ] | N/A | [ ] | [ ] |
| F2: Single-domain | [ ] | [ ] | [ ] | [ ] |
| F3: Multi-domain | [ ] | [ ] | [ ] | [ ] |
| F4: All-domains | [ ] | [ ] | [ ] | [ ] |
| F5: Auth CLI | [ ] | [ ] | [ ] | [ ] |
| F6: EQC refresh | [ ] | [ ] | [ ] | [ ] |
| F7: Data cleanse | [ ] | [ ] | [ ] | [ ] |

### 6.2 Overall Validation Status

- **Total Features**: 7
- **Validated**: __ / 7
- **Passed**: __ / 7
- **Failed**: __ / 7
- **Blocked**: __ / 7

### 6.3 Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Validator | | | |
| Reviewer | | | |

---

## 7. Appendix

### 7.1 Environment Setup Checklist

- [ ] Python 3.11+ installed
- [ ] `uv` package manager installed
- [ ] PostgreSQL database running
- [ ] `.wdh_env` file configured with database credentials
- [ ] Test data exists in `tests/fixtures/real_data/`

### 7.2 Quick Reference Commands

```bash
# ETL single domain
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --period 202411

# ETL multi-domain
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance,annuity_income --period 202411 --execute

# ETL all domains
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl --all-domains --period 202411 --execute

# Auth refresh
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli auth refresh

# EQC status
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli eqc-refresh --status

# Data cleanse
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli cleanse --table all --dry-run
```
