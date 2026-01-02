# Proposal: ETL Logging and Terminal Output Optimization

## Background

The current ETL CLI output uses standard `print` statements mixed with `structlog` JSON output. Additionally, failed record logging creates fragmented, inconsistent files for each source, making debugging difficult.

## Objectives

1.  **Improve Human Readability**: Use colors, formatting, and tables for terminal output.
2.  **Separate Concerns**: Distinct "User Interface" (CLI output) from "Application Logs" (debug/audit trail).
3.  **Unify Failed Records**: Consolidate failed records from multiple data sources into a single, standardized CSV file per ETL session.

## Proposed Solution

### 1. Technology Stack

- **[Rich](https://github.com/Textualize/rich)**: For beautiful terminal formatting (tables, progress spinners, panels, colors).
- **[Structlog](https://www.structlog.org/)**: Existing logging library, reconfigured for dual-mode output.

### 2. Design

#### A. Terminal Output (User Interface)

The CLI will use `rich` for interaction.

- **Status Spinners**: For long-running operations.
- **Tables**: For summaries.
- **Panels**: For clear job boundaries.

#### B. Terminal UX Enhancements (New)

We will leverage `rich` capabilities to provide a modern, interactive experience:

1.  **Hierarchy Visualization (Tree View)**:

    - Visualize the file discovery results (Domain -> File -> Sheet).

2.  **Live Progress & Steps**:

    - Instead of simple spinners, use a "Live Display" to show the current phase.
    - Example:
      - [x] Discovery (Found 1 file)
      - [>] **Transformation** (Processing...)
      - [ ] Loading

3.  **Hyperlinks**:

    - Make file paths clickable in supported terminals.
    - Example: `Saved failure log to [link=file:///abs/path/to/log.csv]logs/wdh_etl_failures_....csv[/link]`

4.  **Concise Mode**:
    - By default, hide individual INFO logs from `structlog` in the console (unless `--debug` is used).
    - Show only high-level steps and final summaries to keep the terminal clean.

#### D. Logging Configuration

Refactor `work_data_hub.utils.logging`:

- **Console Handler**: `structlog.dev.ConsoleRenderer` for human-readable development logs (only if `--debug` is on).
- **File Handler**: `structlog.processors.JSONRenderer` for structured machine-readable logs.

#### E. Unified Failed Records Logging

Introduce a session-based approach to handle failed records (e.g., dropped rows).

**Concept:**

- **Session ID**: Generate a unique ID for each CLI execution (e.g., `etl_20260102_181157_req_abc123`).
- **Single File**: Generate ONE failure log per session.
  - Format: `logs/wdh_etl_failures_{YYYYMMDD_HHMMSS}_{session_id}.csv`
- **Unified Schema**: Use a fixed schema that can accommodate any data source by serializing raw data to JSON.

**Schema Definition:**

| Field         | Description                  | Example                               |
| :------------ | :--------------------------- | :------------------------------------ |
| `session_id`  | ETL Session ID               | `req_abc123`                          |
| `timestamp`   | Record Time                  | `2026-01-02T18:12:00`                 |
| `domain`      | Business Domain              | `annuity_performance`                 |
| `source_file` | Source Filename              | `【for年金...】.xlsx`                 |
| `row_index`   | Row Number                   | `1024`                                |
| `error_type`  | Error Category               | `DROPPED_IN_PIPELINE`                 |
| `raw_data`    | **JSON Serialized Raw Data** | `{"PlanCode": "P001", "Amount": 100}` |

### 3. Implementation Details

#### Dependencies

- Add `rich>=13.0.0` to `pyproject.toml`.

#### Code Changes

**1. CLI (`src/work_data_hub/cli`)**

- Generate `session_id` in `main.py`.
- Define `failure_log_path` at startup.
- Pass session context to executors and domain services.

**2. Infrastructure (`src/work_data_hub/infrastructure/validation`)**

- Update `export_error_csv` to:
  - Support "Append Mode".
  - Accept standardized `FailedRecord` objects instead of raw DataFrames.
  - Handle JSON serialization of `raw_data`.

**3. Domain Services (`src/work_data_hub/domain/*/service.py`)**

- Convert failed rows to standard dictionary format.
- Serialize row data to JSON.
- Call the updated export function.

## Example Output (Mockup)

**Terminal:**

```text
╭── ETL Job: annuity_performance ──────────────────────────────╮
│ Mode: delete_insert  |  Session: req_abc123                  │
╰──────────────────────────────────────────────────────────────╯

📂 File Discovery
└── 📄 data.xlsx
    └── 📑 Sheet1 (1000 rows)

[x] 🔍 Discovery completed
[>] 🔄 Transformation (Processing...)
[ ] 💾 Loading

  ! 50 records failed validation
    Saved to 🔗 logs/wdh_etl_failures_....csv (Click to open)

✅ Job completed successfully
```
