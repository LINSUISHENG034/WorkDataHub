# Sprint Change Proposal: ETL Logging and Terminal Output Optimization

**Date:** 2026-01-02
**Triggered By:** Technical improvement proposal (`docs/specific/etl-logging/proposal.md`)
**Mode:** New Feature (Batch insertion as Epic 7.5 Patch)

---

## 1. Issue Summary

### Problem Statement

The current ETL CLI output uses raw `print` statements and `structlog` JSON output mixed together, making terminal output difficult to read for human operators. Additionally, failed record logging is inconsistent - each domain creates fragmented error files without a unified schema.

### Context

- **Discovery:** Identified during post-Epic 7.5 code quality review
- **Impact Level:** Developer Experience (DX) + Operations (Ops) visibility
- **Category:** Technical improvement (not a bug fix)

### Evidence

| Current State              | Proposed State                         |
| -------------------------- | -------------------------------------- |
| Raw `print()` for progress | Rich spinners + progress bars          |
| JSON logs to console       | Human-readable colored logs (dev mode) |
| Per-source error CSVs      | Single unified failure log per session |

---

## 2. Impact Analysis

### 2.1 Epic Impact

| Epic               | Impact     | Notes                                 |
| ------------------ | ---------- | ------------------------------------- |
| Epic 7.5 (Current) | **Direct** | Will be inserted as Patch Story 7.5-4 |
| Epic 8 (Testing)   | None       | No blocking dependency                |

### 2.2 Artifact Conflicts

| Artifact     | Conflict | Required Changes                             |
| ------------ | -------- | -------------------------------------------- |
| PRD          | None     | No scope change                              |
| Architecture | Minor    | Add `rich` dependency, extend logging module |
| UI/UX        | N/A      | CLI-only, no UI impact                       |

### 2.3 Technical Impact

| Component                    | Current Implementation        | Change Required                       |
| ---------------------------- | ----------------------------- | ------------------------------------- |
| `utils/logging.py`           | structlog only                | Add Rich console renderer option      |
| `infrastructure/validation/` | `export_error_csv` per domain | Add session-based unified failure log |
| `cli/etl/`                   | Raw print statements          | Replace with Rich progress display    |
| `pyproject.toml`             | No `rich` dependency          | Add `rich>=13.0.0`                    |

---

## 3. Recommended Approach

### Selected Path: **Direct Adjustment** (Add new stories to current Epic)

**Rationale:**

1. Non-breaking change - existing functionality preserved
2. Minimal blast radius - affects only CLI and logging layers
3. Clear scope - well-defined in proposal document
4. Low risk - can be incrementally validated

**Effort Estimate:**
- Story 7.5-4: ~1.5 hours (Rich integration + CLI replacement)
- Story 7.5-5: ~1.5 hours (Unified logging + Session ID)

**Risk Level:** Low

---

## 4. Detailed Change Proposals

### Story 7.5-4: Rich Terminal UX Enhancement

#### Scope

Integrate `rich` library for improved terminal output experience.

#### Acceptance Criteria

1. **Dependency**: `rich>=13.0.0` added to `pyproject.toml`
2. **Progress Display**: Replace print statements with Rich Live display showing:
   - File discovery tree view
   - Processing phase checklist (Discovery → Transformation → Loading)
   - Live progress indicators
3. **Hyperlinks**: File paths in output are clickable (terminal-dependent)
4. **Console Mode**:
   - Default: Concise mode (hide INFO logs, show only progress + summaries)
   - `--debug`: Enable full structlog console output
5. **Backward Compatibility**: `--no-rich` flag for plain text output (CI/CD environments)
6. **CI Auto-Detection**: When `sys.stdout.isatty() == False`, automatically disable Rich rendering without requiring `--no-rich` flag

#### Files to Modify

| File                                 | Change Type | Description                        |
| ------------------------------------ | ----------- | ---------------------------------- |
| `pyproject.toml`                     | MODIFY      | Add `rich>=13.0.0` dependency      |
| `src/work_data_hub/cli/etl/`         | MODIFY      | Replace print with Rich components |
| `src/work_data_hub/utils/logging.py` | MODIFY      | Add Rich console handler option    |

---

### Story 7.5-5: Unified Failed Records Logging

> **Dependency:** Requires Story 7.5-4 (session_id generation in CLI layer)

#### Scope

Consolidate failed record exports into a single session-based CSV file with standardized schema.

#### Acceptance Criteria

1. **Session ID**: Generate unique session ID per CLI execution (format: `etl_{YYYYMMDD_HHMMSS}_{random}`)
2. **Single File**: All failed records written to `logs/wdh_etl_failures_{session_id}.csv`
3. **Unified Schema**:
   | Field | Type | Description |
   |-------|------|-------------|
   | session_id | string | ETL session identifier |
   | timestamp | ISO-8601 | Record timestamp |
   | domain | string | Business domain (e.g., `annuity_performance`) |
   | source_file | string | Source filename |
   | row_index | int | Row number in source |
   | error_type | string | Error category (e.g., `VALIDATION_FAILED`, `DROPPED_IN_PIPELINE`) |
   | raw_data | JSON string | Serialized raw row data |
4. **Append Mode**: Support appending to existing session file (multi-domain batch runs)
5. **Clickable Output**: Print hyperlink to failure log file at end of execution
6. **Auto-Create Directory**: Automatically create `logs/` directory if it does not exist

#### Files to Modify/Create

| File                                                           | Change Type | Description                                     |
| -------------------------------------------------------------- | ----------- | ----------------------------------------------- |
| `src/work_data_hub/infrastructure/validation/error_handler.py` | MODIFY      | Add session-based export mode                   |
| `src/work_data_hub/cli/etl/executors.py`                       | MODIFY      | Generate session_id, pass to domain services    |
| `src/work_data_hub/domain/*/service.py`                        | MODIFY      | Convert failures to unified FailedRecord format |

---

## 5. Implementation Handoff

### Scope Classification: **Minor**

Changes can be implemented directly by development team without backlog reorganization.

### Handoff Plan

| Role      | Responsibility                    | Deliverables                         |
| --------- | --------------------------------- | ------------------------------------ |
| Dev Agent | Implement Stories 7.5-4 and 7.5-5 | Code changes, unit tests             |
| Dev Agent | Code Review                       | Validate AC coverage, test execution |

### Success Criteria

1. ✅ `uv run --env-file .wdh_env python -m work_data_hub.cli.etl --domain annuity_performance --dry-run` shows Rich progress display
2. ✅ Failed records exported to single CSV with unified schema
3. ✅ All existing tests pass
4. ✅ `--no-rich` flag produces plain text output
5. ✅ `--debug` flag enables verbose logging

---

## 6. Sprint Status Update

### Proposed Changes to `sprint-status.yaml`

```yaml
# Epic 7.5: Empty Customer Name Handling Enhancement
epic-7.5: in-progress
7.5-1-backflow-plan-code-support: done
7.5-2-plan-name-fallback-single-plan: done
7.5-3-empty-customer-name-null-handling: done
7.5-4-rich-terminal-ux-enhancement: backlog        # NEW
7.5-5-unified-failed-records-logging: backlog      # NEW (depends_on: 7.5-4)
```

---

## 7. Checklist Verification

| Section               | Status     | Notes                          |
| --------------------- | ---------- | ------------------------------ |
| 1. Trigger & Context  | ✅ Done    | Technical improvement proposal |
| 2. Epic Impact        | ✅ Done    | Minor impact on Epic 7.5 only  |
| 3. Artifact Conflicts | ✅ Done    | No PRD/Architecture conflicts  |
| 4. Path Forward       | ✅ Done    | Direct Adjustment selected     |
| 5. Change Proposals   | ✅ Done    | 2 stories defined with dependencies |
| 6. Final Review       | ✅ Done    | Reviewed by SM on 2026-01-02        |

---

## Appendix: Original Proposal Reference

See [docs/specific/etl-logging/proposal.md](file:///e:/Projects/WorkDataHub/docs/specific/etl-logging/proposal.md) for full technical design including:

- Technology stack details (Rich + Structlog)
- Terminal UX mockup
- Logging configuration architecture
