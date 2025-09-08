# INITIAL.md — M3 Schedules, Sensors, and Alerting for Trustee Performance

Selected task: ROADMAP.md → Milestone 3 → F‑030 (Add schedules for domain jobs), F‑031 (Add data quality sensors), C‑030 (Configure alerting)

Purpose: Operationalize the trustee_performance pipeline by adding a production schedule, file‑based trigger sensor, and basic data‑quality sensor with alert hooks. Expose these through a Dagster Definitions module so `dagster dev` can discover jobs, schedules, and sensors.

Dependencies: R‑030 (Research Dagster sensors/alerts) is implicitly satisfied by the design below; no external services required.

## FEATURE
Add:
- A daily schedule to run `trustee_performance_multi_file_job` at 02:00 Asia/Shanghai in execute mode.
- A file discovery sensor that triggers the job when new matching trustee files are discovered since the last run.
- A post‑run data quality sensor that checks the last job result and raises an alert when inserted rows == 0.
- A `Definitions` entry point that registers jobs, schedules, and sensors for `dagster dev`.

## SCOPE
- In‑scope:
  - New files under `src/work_data_hub/orchestration/`:
    - `schedules.py`: schedule(s) for trustee_performance job(s).
    - `sensors.py`: file discovery sensor + data-quality sensor.
    - `repository.py`: exports `Definitions` including jobs, schedules, sensors.
  - Unit tests for schedule config and sensor logic (no external services needed).
- Non‑goals:
  - No Slack/email integration (provide alert hooks/logging only).
  - No changes to job/ops behavior beyond run_config injection.
  - No Docker/K8s deployment work (separate task).

## CONTEXT SNAPSHOT
```bash
src/work_data_hub/
  orchestration/
    jobs.py                   # trustee_performance_*_job + build_run_config(args)
    ops.py                    # ops
  io/connectors/file_connector.py   # DataSourceConnector.discover(domain)
  config/
    settings.py               # get_settings(); DB + paths
    data_sources.yml          # domains.trustee_performance.table/pk
```

## EXAMPLES (most important)
- `Definitions` module pattern
```python
# src/work_data_hub/orchestration/repository.py
from dagster import Definitions
from .jobs import trustee_performance_job, trustee_performance_multi_file_job
from .schedules import trustee_daily_schedule
from .sensors import trustee_new_files_sensor, trustee_dq_sensor

defs = Definitions(
    jobs=[trustee_performance_job, trustee_performance_multi_file_job],
    schedules=[trustee_daily_schedule],
    sensors=[trustee_new_files_sensor, trustee_dq_sensor],
)
```

- Daily schedule with run_config
```python
# src/work_data_hub/orchestration/schedules.py
from dagster import schedule
from .jobs import trustee_performance_multi_file_job
from ..config.settings import get_settings
import yaml

def _build_schedule_run_config():
    settings = get_settings()
    with open(settings.data_sources_config, "r", encoding="utf-8") as f:
        ds = yaml.safe_load(f) or {}
    domain_cfg = ds.get("domains", {}).get("trustee_performance", {})
    return {
        "ops": {
            "discover_files_op": {"config": {"domain": "trustee_performance"}},
            "read_and_process_trustee_files_op": {"config": {"sheet": 0, "max_files": 5}},
            "load_op": {
                "config": {
                    "table": domain_cfg.get("table", "trustee_performance"),
                    "mode": "delete_insert",
                    "pk": domain_cfg.get("pk", ["report_date", "plan_code", "company_code"]),
                    "plan_only": False,
                }
            },
        }
    }

@schedule(cron_schedule="0 2 * * *", job=trustee_performance_multi_file_job, execution_timezone="Asia/Shanghai")
def trustee_daily_schedule(_context):
    return _build_schedule_run_config()
```

- File discovery sensor
```python
# src/work_data_hub/orchestration/sensors.py
from dagster import sensor, RunRequest, SkipReason
from ..io.connectors.file_connector import DataSourceConnector
from .jobs import trustee_performance_multi_file_job

@sensor(job=trustee_performance_multi_file_job, minimum_interval_seconds=300)
def trustee_new_files_sensor(context):
    connector = DataSourceConnector()
    files = connector.discover("trustee_performance")
    if not files:
        return SkipReason("No trustee_performance files found")

    # Cursor: last processed mtime
    last_mtime = float(context.cursor) if context.cursor else 0.0
    new_files = [f for f in files if f.metadata.get("modified_time", 0) > last_mtime]
    if not new_files:
        return SkipReason("No new files since last poll")

    max_mtime = max(f.metadata.get("modified_time", 0) for f in new_files)
    context.update_cursor(str(max_mtime))

    run_config = {
        "ops": {
            "discover_files_op": {"config": {"domain": "trustee_performance"}},
            "read_and_process_trustee_files_op": {"config": {"sheet": 0, "max_files": 5}},
            "load_op": {"config": {"table": "trustee_performance", "mode": "delete_insert", "pk": ["report_date","plan_code","company_code"], "plan_only": False}},
        }
    }
    return RunRequest(run_key=str(max_mtime), run_config=run_config)
```

- Simple data‑quality sensor (checks prior run result via instance/run storage is non‑trivial; here we compute a quick health probe by counting planned insert parameters)
```python
from dagster import sensor, SkipReason
from ..io.loader.warehouse_loader import build_insert_sql

@sensor(minimum_interval_seconds=600)
def trustee_dq_sensor(context):
    # Lightweight check: ensure at least some records would be inserted if run now
    # (Plan-only probe avoids DB access.)
    # In practice, you could query the DB or Dagster event log for last run stats.
    from ..io.connectors.file_connector import DataSourceConnector
    from ..io.readers.excel_reader import read_excel_rows
    from ..domain.trustee_performance.service import process

    files = DataSourceConnector().discover("trustee_performance")
    if not files:
        return SkipReason("DQ: No files to process")
    rows = read_excel_rows(files[0].path, sheet=0)
    processed = [m.model_dump() for m in process(rows, data_source=files[0].path)]
    if not processed:
        return SkipReason("DQ: No records would be produced")
    sql, params = build_insert_sql("trustee_performance", sorted(processed[0].keys()), processed[:100])
    if not params:
        return SkipReason("DQ: Insert plan has no parameters")
    return SkipReason("DQ: OK (probe passed)")
```

## DOCUMENTATION
- Dagster schedules: https://docs.dagster.io/concepts/partitions-schedules-sensors/schedules
- Dagster sensors: https://docs.dagster.io/concepts/partitions-schedules-sensors/sensors
- Dagster Definitions: https://docs.dagster.io/deployment/code-locations#definitions
- Timezone: https://docs.dagster.io/concepts/partitions-schedules-sensors/schedules#time-zones

## INTEGRATION POINTS
- Orchestration: imports existing jobs, no changes to ops.
- Config: schedule/sensor run_config must pull table/pk from `data_sources.yml` for consistency.
- IO: File connector used by file sensor and DQ probe; Excel reader + domain service used by DQ probe.
- CLI/Web: Expose Definitions for `dagster dev -m src.work_data_hub.orchestration.repository`.

## DATA CONTRACTS
- No changes to database schema.
- Schedule/sensor run_config must specify:
  - `ops.discover_files_op.config.domain`
  - `ops.read_and_process_trustee_files_op.config.sheet` and `max_files`
  - `ops.load_op.config.table`, `mode`, `pk`, `plan_only=False` for execute paths

## GOTCHAS & LIBRARY QUIRKS
- Dagster schedules/sensors require a Definitions module; ensure imports are lightweight (avoid heavy I/O at import time).
- Keep sensors fast; use `minimum_interval_seconds` and avoid DB calls by default.
- Time zones: set `execution_timezone` to avoid UTC cron surprises.
- Windows paths: use `Path`/OS‑agnostic joins in any file path handling.

## IMPLEMENTATION NOTES
- Create three new modules as outlined (schedules.py, sensors.py, repository.py).
- Reuse `data_sources.yml` to populate table/pk for load config.
- Prefer pure‑python logic; no network calls.
- Keep code consistent with existing logging and error handling patterns.

## VALIDATION GATES (must pass)
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v
```

Manual checks (optional):
```bash
# Start Dagster UI with Definitions
uv run dagster dev -m src.work_data_hub.orchestration.repository

# Verify in UI:
# - Jobs show up
# - trustee_daily_schedule appears on Schedules page
# - Sensors page shows trustee_new_files_sensor and trustee_dq_sensor
```

## ACCEPTANCE CRITERIA
- [ ] `Definitions` exposes jobs, schedule, and sensors without import errors.
- [ ] Daily schedule returns a valid run_config and targets `trustee_performance_multi_file_job`.
- [ ] File discovery sensor triggers when new files appear (cursor advances) and skips otherwise.
- [ ] DQ sensor runs fast (<5s), skips with informative reason, and returns OK when probe passes.
- [ ] All validation gates pass (ruff, mypy, pytest).

## ROLLOUT & RISK
- Default sensors perform plan‑only probes to avoid DB dependency.
- Schedule runs in execute mode, relying on existing DB configuration via .env.
- Low risk: changes are additive. Rollback by removing the new modules from Definitions.

## APPENDICES
Useful ripgrep searches:
```bash
rg -n "Definitions\(|@schedule|@sensor|execution_timezone|RunRequest|SkipReason" src/
```

Test skeletons:
```python
def test_schedule_builds_run_config():
    from src.work_data_hub.orchestration.schedules import _build_schedule_run_config
    cfg = _build_schedule_run_config()
    assert cfg["ops"]["load_op"]["config"]["plan_only"] is False

def test_file_sensor_cursor(monkeypatch, tmp_path):
    # monkeypatch DataSourceConnector.discover to return synthetic files with mtimes
    ...
```

Next steps for Claude:
1) Generate PRP from this INITIAL (F‑030, F‑031, C‑030) and implement schedules.py, sensors.py, repository.py with tests.
2) Run validation gates; optionally verify in Dagster UI via `dagster dev`.
3) Update ROADMAP.md: mark F‑030/F‑031/C‑030 → COMPLETED with PRP link(s).
