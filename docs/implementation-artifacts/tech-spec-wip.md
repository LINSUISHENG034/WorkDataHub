---
title: 'Post-ETL Hook Infrastructure for Contract Status Sync'
slug: 'post-etl-hook-contract-sync'
created: '2026-01-17'
status: 'review'
stepsCompleted: [1, 2, 3]
tech_stack: ['Python 3.12', 'PostgreSQL 15+', 'Alembic', 'Dagster', 'Rich', 'argparse']
files_to_modify:
  - 'io/schema/migrations/versions/008_create_customer_plan_contract.py'
  - 'src/work_data_hub/cli/etl/hooks.py'
  - 'src/work_data_hub/cli/etl/main.py'
  - 'src/work_data_hub/cli/etl/executors.py'
  - 'src/work_data_hub/cli/__main__.py'
  - 'src/work_data_hub/customer_mdm/__init__.py'
  - 'src/work_data_hub/customer_mdm/contract_sync.py'
  - 'src/work_data_hub/cli/customer_mdm/__init__.py'
  - 'src/work_data_hub/cli/customer_mdm/sync.py'
  - 'config/customer_mdm.yaml'
code_patterns:
  - 'CLI subpackage pattern (cli/etl/, cli/auth/)'
  - 'Alembic migration with DO $$ idempotent DDL'
  - 'JOB_REGISTRY for domain routing'
  - 'argparse flag pattern (--no-xxx)'
  - 'console abstraction (RichConsole/PlainConsole)'
test_patterns:
  - 'pytest in tests/cli/etl/'
  - 'Unit tests for console, error formatter'
---

# Tech-Spec: Post-ETL Hook Infrastructure for Contract Status Sync

**Created:** 2026-01-17

## Overview

### Problem Statement

Customer MDM 系统需要在业务 ETL (`annuity_performance`) 完成后自动同步客户-计划合约状态到 `customer.customer_plan_contract` 表，实现 SCD Type 2 历史追踪。当前缺乏：
1. 自动触发机制 (Post-ETL Hook)
2. 客户-计划合约关系表
3. 手动同步 CLI 命令

### Solution

实现 Post-ETL Hook 模式，包含：
1. **Alembic 迁移** - 创建 `customer.customer_plan_contract` 表
2. **Hook 基础架构** - `cli/etl/hooks.py` 模块注册和执行 hooks
3. **合约同步服务** - `customer_mdm/contract_sync.py` 业务逻辑
4. **CLI 集成** - `customer-mdm sync` 手动触发 + `--no-post-hooks` 标志

### Scope

**In Scope:**
- Alembic 迁移 `008_create_customer_plan_contract.py`
- Post-ETL Hook 基础架构
- 合约同步服务（v1 简化逻辑）
- Customer MDM CLI 子命令
- `--no-post-hooks` 标志

**Out of Scope:**
- `is_strategic`/`is_existing` 完整逻辑 (Story 7.6-9)
- 触发器 `trg_sync_product_line_name` (Story 7.6-9)
- Monthly Snapshot 表 (Story 7.6-7)

## Context for Development

### Codebase Patterns

1. **CLI Argument Pattern**: Use `argparse` with `action="store_true"` for toggle flags
   ```python
   parser.add_argument(
       "--no-post-hooks",
       action="store_true",
       default=False,
       help="Skip post-ETL hooks (debugging/manual control)",
   )
   ```

2. **Hook Insertion Point**: In `executors.py`, line 324 after `if result.success:` block

3. **Alembic Migration Pattern**: Use `DO $$ ... END $$` for idempotent DDL

4. **CLI Subpackage Pattern**: Mirror existing `cli/etl/` structure for `cli/customer_mdm/`

5. **Service Layer Pattern**: Business logic in `src/work_data_hub/customer_mdm/`, CLI in `src/work_data_hub/cli/customer_mdm/`

### Files to Reference

| File | Purpose |
| ---- | ------- |
| [executors.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/cli/etl/executors.py) | Hook insertion point (line 324) |
| [main.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/cli/etl/main.py) | Argument parsing pattern |
| [__main__.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/cli/__main__.py) | CLI subcommand routing |
| [007_add_customer_tags_jsonb.py](file:///e:/Projects/WorkDataHub/io/schema/migrations/versions/007_add_customer_tags_jsonb.py) | Alembic migration pattern |
| [7.6-6-contract-status-sync-post-etl-hook.md](file:///e:/Projects/WorkDataHub/docs/sprint-artifacts/stories/epic-customer-mdm/7.6-6-contract-status-sync-post-etl-hook.md) | Story requirements with DDL |

### Technical Decisions

1. **Clean Slate**: No existing `customer_mdm` package - create new package structure
2. **Reuse Console Abstraction**: Use existing `get_console()` from `cli/etl/console.py`
3. **Idempotent Sync**: Use `ON CONFLICT DO NOTHING` for safe re-runs
4. **v1 Simplified Logic**: `contract_status` based on `期末资产规模 > 0`, placeholders for `is_strategic`/`is_existing`

## Implementation Plan

### Tasks

- [ ] **Task 1: Create Alembic migration for `customer_plan_contract` table**
  - File: `io/schema/migrations/versions/008_create_customer_plan_contract.py`
  - Action: Create migration with table DDL, indexes, constraints
  - Notes: Follow pattern from `007_add_customer_tags_jsonb.py`. Use `DO $$` for idempotency. Include all indexes from Story 7.6-6 Dev Notes.

- [ ] **Task 2: Create `customer_mdm` service package**
  - File: `src/work_data_hub/customer_mdm/__init__.py`
  - Action: Create package init with exports
  - Notes: Export `sync_contract_status` function

- [ ] **Task 3: Implement contract sync service**
  - File: `src/work_data_hub/customer_mdm/contract_sync.py`
  - Action: Implement `sync_contract_status(period: Optional[str] = None) -> dict` function
  - Notes: 
    - Query `business.规模明细` for unique `(company_id, 计划代码, 产品线代码)` combinations
    - Use `ON CONFLICT (company_id, plan_code, product_line_code, valid_to) DO NOTHING`
    - Return `{"inserted": int, "skipped": int, "total": int}`

- [ ] **Task 4: Create Post-ETL Hooks module**
  - File: `src/work_data_hub/cli/etl/hooks.py`
  - Action: Create hook registry and runner
  - Notes:
    - Define `PostEtlHook` dataclass with `name`, `domains`, `hook_fn`
    - Create `POST_ETL_HOOKS` list with `contract_status_sync` hook
    - Implement `run_post_etl_hooks(domain: str, period: Optional[str], console)` function

- [ ] **Task 5: Add `--no-post-hooks` CLI flag**
  - File: `src/work_data_hub/cli/etl/main.py`
  - Action: Add argument after line 277 (after `--check-db`)
  - Notes: Use `action="store_true"`, default=False

- [ ] **Task 6: Integrate hooks into executor**
  - File: `src/work_data_hub/cli/etl/executors.py`
  - Action: Call `run_post_etl_hooks()` after job success (around line 368, before final summary)
  - Notes: Check `getattr(args, 'no_post_hooks', False)` before calling

- [ ] **Task 7: Create Customer MDM CLI package**
  - File: `src/work_data_hub/cli/customer_mdm/__init__.py`
  - Action: Create package init
  - Notes: Empty init, subcommand logic in separate module

- [ ] **Task 8: Implement `customer-mdm sync` subcommand**
  - File: `src/work_data_hub/cli/customer_mdm/sync.py`
  - Action: Implement `main(argv)` function with argparse
  - Notes: Call `sync_contract_status()` and display results

- [ ] **Task 9: Register `customer-mdm` in CLI router**
  - File: `src/work_data_hub/cli/__main__.py`
  - Action: Add `customer-mdm` subparser and routing logic
  - Notes: Follow pattern of existing `auth`, `eqc-refresh` commands

- [ ] **Task 10: Create configuration file**
  - File: `config/customer_mdm.yaml`
  - Action: Create YAML with placeholder configuration
  - Notes: Values for `strategic_threshold`, `whitelist_top_n`, `status_year` (Story 7.6-9)

- [ ] **Task 11: Run migration and test**
  - Action: Run Alembic upgrade and verify table creation
  - Command: `uv run --env-file .wdh_env alembic upgrade head`

- [ ] **Task 12: Integration test**
  - Action: Run ETL with hooks, verify contract data populated
  - Command: `uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --period 202501 --execute`

### Acceptance Criteria

- [ ] **AC-1 (Table Creation)**: Given the migration is run, when querying `customer.customer_plan_contract`, then the table exists with all defined columns and indexes

- [ ] **AC-2 (Data Population)**: Given `business.规模明细` has data, when `sync_contract_status()` is called, then records are inserted into `customer_plan_contract` with correct `contract_status` values

- [ ] **AC-3 (Post-ETL Hook Trigger)**: Given ETL runs for `annuity_performance`, when job succeeds, then `contract_status_sync` hook is automatically executed

- [ ] **AC-4 (Hook Skip Flag)**: Given `--no-post-hooks` flag is used, when ETL runs, then no post-ETL hooks are executed

- [ ] **AC-5 (Manual Sync Command)**: Given CLI command `customer-mdm sync` is run, when sync completes, then results are displayed showing inserted/skipped counts

- [ ] **AC-6 (Idempotency)**: Given sync is run multiple times, when records already exist, then no duplicate records are created (ON CONFLICT DO NOTHING)

- [ ] **AC-7 (FK Validation)**: Given populated data, when querying with LEFT JOIN to `mapping.产品线`, then all `product_line_code` values have matching references

## Additional Context

### Dependencies

- **Stories 7.6-0 ~ 7.6-5**: `customer` schema exists, 中标/流失 data loaded
- **`business.规模明细` table**: Source for contract derivation (populated by `annuity_performance` ETL)
- **`mapping.产品线` table**: FK reference for `product_line_code`

### Testing Strategy

**Automated Tests:**
1. Run Alembic migration: `uv run --env-file .wdh_env alembic upgrade head`
2. Verify table exists: `SELECT COUNT(*) FROM customer.customer_plan_contract;`
3. Run sync: `uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm sync`
4. Run ETL with hooks: `uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --execute`
5. Run ETL without hooks: `uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --execute --no-post-hooks`

**Validation Queries:**
```sql
-- Record count
SELECT COUNT(*) FROM customer.customer_plan_contract;

-- Distribution by status
SELECT contract_status, COUNT(*) FROM customer.customer_plan_contract GROUP BY contract_status;

-- FK validation (should return 0)
SELECT COUNT(*) FROM customer.customer_plan_contract c
LEFT JOIN mapping."产品线" p ON c.product_line_code = p.产品线代码
WHERE p.产品线代码 IS NULL;
```

### Notes

- **Hook execution timing**: After job success, before final summary display
- **Multi-domain batch**: Hooks run after each domain, not at batch end
- **v1 limitations**: `is_strategic` and `is_existing` are placeholder FALSE values (Story 7.6-9 implements full logic)
- **Pre-mortem risk**: Large dataset sync may take time; consider batch processing in Story 7.6-9
