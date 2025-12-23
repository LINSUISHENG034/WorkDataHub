# Story 6.4: Internal Mapping Resolver (Multi-Tier Lookup)

Status: Done

## Context & Business Value

- Epic 6 builds a resilient company enrichment service: internal mappings → EQC sync (budgeted, cached) → async queue → temporary IDs as safety net.
- Story 6.1 created the `enterprise` schema with 3 tables (`company_master`, `company_mapping`, `enrichment_requests`).
- Story 6.2 implemented deterministic temporary ID generation (HMAC-SHA1).
- Story 6.3 created `CompanyMappingRepository` for database access and `load_company_id_overrides()` for multi-file YAML loading.
- **This story** enhances `CompanyIdResolver` to integrate YAML overrides (5 priority levels) + database cache lookup + EQC sync (budget-limited, cached), creating a unified multi-tier resolution system.
- Business value: 90%+ of lookups resolved locally with zero API cost and sub-millisecond latency, while EQC sync fills gaps and caches results for future runs. Enables gradual cache hit rate improvement through backflow mechanism.

## Story

As a **data engineer**,
I want **CompanyIdResolver to support multi-tier lookup with YAML overrides and database cache**,
so that **company ID resolution uses a unified hierarchical strategy with automatic backflow to improve cache hit rates over time**.

## Acceptance Criteria

1. **AC1**: `CompanyIdResolver.__init__` accepts new optional parameters: `yaml_overrides: Dict[str, Dict[str, str]]` and `mapping_repository: CompanyMappingRepository`.
2. **AC2**: Resolution priority: YAML (5 levels) → Database cache → Existing column → EQC sync (budgeted, cached) → Temp ID.
3. **AC3**: YAML lookup checks all 5 priority levels in order (plan → account → hardcode → name → account_name) before falling back to database.
4. **AC4**: Database lookup uses `CompanyMappingRepository.lookup_batch()` for batch-optimized single SQL round-trip.
5. **AC5**: EQC sync path: honors `sync_lookup_budget`, caches results to `enterprise.company_mapping`, never blocks pipeline on EQC failure; budget exhaustion stops further EQC calls.
6. **AC6**: Backflow mechanism: when existing company_id column resolves a row, automatically insert new mappings to database cache via `insert_batch_with_conflict_check()`.
7. **AC7**: `ResolutionStatistics` extended with YAML hit breakdown (`yaml_hits: Dict[str, int]`), `db_cache_hits`, `eqc_sync_hits`, `backflow_stats`, and budget consumption.
8. **AC8**: Backward compatible: all new parameters optional; legacy callers unchanged.
9. **AC9**: Batch resolution performance <100ms for 1,000 rows without EQC calls; EQC path measured separately with budgeted cap.
10. **AC10**: API contracts documented for `lookup_batch`, `insert_batch_with_conflict_check`, `ResolutionStrategy`, and stats payload; `enterprise.company_mapping` schema/index and ops steps documented.
11. **AC11**: All new code has >85% unit test coverage.

## Dependencies & Interfaces

- **Prerequisite**: Story 6.1 (enterprise schema) - DONE
- **Prerequisite**: Story 6.2 (temporary ID generation) - DONE
- **Prerequisite**: Story 6.3 (mapping repository + YAML loader) - DONE
- **Epic 6 roster (for alignment)**: 6.1 schema, 6.2 temp IDs, 6.3 DB cache, 6.3.1 backflow, **6.4 EQC sync (this story)**, 6.5 async queue enqueue, 6.6 Dagster job consumption, 6.7 observability/export.
- **Tech Spec**: `docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md` (Story 6.3, 6.3.1, 6.4 sections)
- **Integration Point**: Story 6.5 will add async queue enqueue for unresolved (after temp IDs)
- **Database**: PostgreSQL `enterprise.company_mapping` table

## Tasks / Subtasks

- [x] Task 1: Extend CompanyIdResolver constructor (AC1, AC7)
  - [x] 1.1: Add `yaml_overrides` parameter with auto-load from `load_company_id_overrides()` if not provided
  - [x] 1.2: Add `mapping_repository` parameter (optional, enables database lookup)
  - [x] 1.3: Deprecate `plan_override_mapping` parameter (keep for backward compatibility)
  - [x] 1.4: Update docstrings and type hints

- [x] Task 2: Implement multi-tier YAML lookup (AC2, AC3)
  - [x] 2.1: Create `_resolve_via_yaml_overrides()` method checking all 5 priority levels
  - [x] 2.2: Implement vectorized lookup for each priority level
  - [x] 2.3: Track hits per priority level for statistics

- [x] Task 3: Implement database cache lookup (AC2, AC4)
  - [x] 3.1: Create `_resolve_via_db_cache()` method using `mapping_repository.lookup_batch()`
  - [x] 3.2: Integrate into `resolve_batch()` after YAML lookup, before existing column
  - [x] 3.3: Handle missing repository gracefully (skip database lookup)

- [x] Task 4: Implement EQC sync (AC2, AC5)
  - [x] 4.1: Honor `sync_lookup_budget` per batch; decrement and stop when exhausted
  - [x] 4.2: On EQC success, cache results into `enterprise.company_mapping` via repository
  - [x] 4.3: EQC failures degrade gracefully (no pipeline block); log counts only, no PII
  - [x] 4.4: Add metrics/log fields for budget consumption and EQC hit count

- [x] Task 5: Implement backflow mechanism (AC6)
  - [x] 5.1: Create `_backflow_new_mappings()` method per Tech Spec design
  - [x] 5.2: Collect backflow candidates from existing column hits (non-temp IDs only)
  - [x] 5.3: Use `insert_batch_with_conflict_check()` for conflict detection
  - [x] 5.4: Log conflicts as warnings (existing_id vs new_id)

- [x] Task 6: Extend ResolutionStatistics (AC7)
  - [x] 6.1: Add `yaml_hits: Dict[str, int]` field (breakdown by priority level)
  - [x] 6.2: Add `db_cache_hits: int` field
  - [x] 6.3: Add `eqc_sync_hits: int`, `budget_consumed: int`, `budget_remaining: int`
  - [x] 6.4: Add `backflow_stats: Dict[str, int]` field (inserted, skipped, conflicts)
  - [x] 6.5: Update `to_dict()` method

- [x] Task 7: Contracts, schema, ops (AC10)
  - [x] 7.1: Document `lookup_batch` / `insert_batch_with_conflict_check` request/response schema and errors
  - [x] 7.2: Document `ResolutionStrategy` fields and `match_type`/priority enums
  - [x] 7.3: Document `enterprise.company_mapping` columns, indexes, and ON CONFLICT policy
  - [x] 7.4: Add env + smoke/runbook steps (migrations, DB URL, mapping dir, EQC token)

- [x] Task 8: Unit tests (AC9, AC11)
  - [x] 8.1: Test YAML multi-tier lookup (all 5 levels)
  - [x] 8.2: Test database cache lookup (with mocked repository)
  - [x] 8.3: Test backflow mechanism (insert, skip, conflict scenarios)
  - [x] 8.4: Test backward compatibility (existing tests unchanged)
  - [x] 8.5: Test performance guard (1000 rows < 100ms) without EQC; separate EQC budget test
  - [x] 8.6: Test statistics accuracy (yaml/db/eqc/backflow/budget)
  - [x] 8.7: Test EQC failure graceful degradation (no blocking, budget decrement rules)
  - [x] 8.8: Test schema/contract invariants (match_type enums, priority ordering)

## Dev Notes

### Architecture Context

- **Layer**: Infrastructure (enrichment subsystem)
- **Pattern**: Strategy pattern for hierarchical resolution
- **Clean Architecture**: No domain imports; only stdlib + pandas + SQLAlchemy
- **Reference**: AD-010 in `docs/architecture/architectural-decisions.md`

### Resolution Priority (Updated - Dual Layer Architecture)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Company ID Resolution Priority                │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: YAML Configuration (version-controlled, supplements DB)│
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ P1: company_id_overrides_plan.yml      (计划代码)          │ │
│  │ P2: company_id_overrides_account.yml   (账户号)            │ │
│  │ P3: company_id_overrides_hardcode.yml  (硬编码特殊)        │ │
│  │ P4: company_id_overrides_name.yml      (客户名称)          │ │
│  │ P5: company_id_overrides_account_name.yml (年金账户名)     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              ↓ Not found                         │
│  Layer 2: Database Cache (enterprise.company_mapping)            │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ - Legacy migrated data (bulk historical mappings)          │ │
│  │ - EQC query result cache (dynamic growth)                  │ │
│  │ - Pipeline backflow (auto-populated from existing data)    │ │
│  │ - Query: ORDER BY priority ASC (highest priority first)    │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              ↓ Not found                         │
│  Layer 3: Existing company_id Column (passthrough)               │
│           + BACKFLOW: Insert new mappings to DB cache            │
│                              ↓ Not found                         │
│  Layer 4: EQC Sync Lookup (budget-limited, Story 6.5)            │
│                              ↓ Not found                         │
│  Layer 5: Temporary ID Generation (IN<16-char-Base32>)          │
│           + Queue for async enrichment (Story 6.7)               │
└─────────────────────────────────────────────────────────────────┘
```

### Runtime Dependencies & Versions

- SQLAlchemy 2.0.43 — use 2.x APIs (`text()`, `Connection.execute` returns `Result`)
- pandas 2.2.3 — vectorized operations for batch processing
- structlog 25.4.0 — reuse `utils/logging.get_logger`, follow Decision #8 sanitization
- pytest 8.4.2 — prefer fixtures/marks over ad-hoc setup

### File Locations

| File | Purpose | Status |
|------|---------|--------|
| `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py` | Main resolver class | MODIFY |
| `src/work_data_hub/infrastructure/enrichment/types.py` | ResolutionStatistics extension | MODIFY |
| `src/work_data_hub/infrastructure/enrichment/mapping_repository.py` | Database repository | EXISTING (Story 6.3) |
| `src/work_data_hub/config/mapping_loader.py` | YAML loader | EXISTING (Story 6.3) |
| `tests/unit/infrastructure/enrichment/test_company_id_resolver.py` | Resolver unit tests | MODIFY |

### Design Details

**Extended CompanyIdResolver Constructor:**
```python
# src/work_data_hub/infrastructure/enrichment/company_id_resolver.py
class CompanyIdResolver:
    def __init__(
        self,
        enrichment_service: Optional["CompanyEnrichmentService"] = None,
        plan_override_mapping: Optional[Dict[str, str]] = None,  # DEPRECATED
        yaml_overrides: Optional[Dict[str, Dict[str, str]]] = None,  # NEW
        mapping_repository: Optional["CompanyMappingRepository"] = None,  # NEW
    ) -> None:
        """
        Initialize the CompanyIdResolver.

        Args:
            enrichment_service: Optional CompanyEnrichmentService for EQC lookup.
            plan_override_mapping: DEPRECATED - Use yaml_overrides instead.
                Kept for backward compatibility; merged into yaml_overrides["plan"].
            yaml_overrides: Dict of priority level -> {alias: company_id} mappings.
                If not provided, auto-loads from load_company_id_overrides().
            mapping_repository: Optional CompanyMappingRepository for database cache.
                If not provided, database lookup is skipped.
        """
        # Auto-load YAML if not provided
        if yaml_overrides is None:
            from work_data_hub.config import load_company_id_overrides
            self.yaml_overrides = load_company_id_overrides()
        else:
            self.yaml_overrides = yaml_overrides

        # Backward compatibility: merge plan_override_mapping into yaml_overrides
        if plan_override_mapping:
            logger.warning(
                "plan_override_mapping is deprecated, use yaml_overrides instead"
            )
            self.yaml_overrides["plan"].update(plan_override_mapping)

        self.mapping_repository = mapping_repository
        self.enrichment_service = enrichment_service
        ...
```

**Multi-Tier YAML Lookup:**
```python
def _resolve_via_yaml_overrides(
    self,
    df: pd.DataFrame,
    strategy: ResolutionStrategy,
) -> Tuple[pd.Series, Dict[str, int]]:
    """
    Resolve company_id via YAML overrides (5 priority levels).

    Returns:
        Tuple of (resolved_series, hits_by_priority)
    """
    resolved = pd.Series(pd.NA, index=df.index)
    hits_by_priority: Dict[str, int] = {}

    # Priority order: plan (1) → account (2) → hardcode (3) → name (4) → account_name (5)
    priority_columns = {
        "plan": strategy.plan_code_column,
        "account": strategy.account_number_column,  # NEW field in ResolutionStrategy
        "hardcode": strategy.plan_code_column,  # Same as plan for hardcode
        "name": strategy.customer_name_column,
        "account_name": strategy.account_name_column,
    }

    for priority, column in priority_columns.items():
        if column not in df.columns:
            continue

        mappings = self.yaml_overrides.get(priority, )
        if not mappings:
            continue

        # Vectorized lookup for unresolved rows
        mask_unresolved = resolved.isna()
        if not mask_unresolved.any():
            break

        lookup_values = df.loc[mask_unresolved, column].map(mappings)
        new_hits = lookup_values.notna()

        resolved.loc[mask_unresolved] = resolved.loc[mask_unresolved].fillna(
            lookup_values
        )
        hits_by_priority[priority] = new_hits.sum()

    return resolved, hits_by_priority
```

**Database Cache Lookup:**
```python
def _resolve_via_db_cache(
    self,
    df: pd.DataFrame,
    mask_unresolved: pd.Series,
    strategy: ResolutionStrategy,
) -> Tuple[pd.Series, int]:
    """
    Resolve company_id via database cache.

    Returns:
        Tuple of (resolved_series, hit_count)
    """
    if not self.mapping_repository:
        return pd.Series(pd.NA, index=df.index), 0

    # Collect all potential lookup values from unresolved rows
    lookup_columns = [
        strategy.plan_code_column,
        strategy.account_number_column,
        strategy.customer_name_column,
        strategy.account_name_column,
    ]

    alias_names = set()
    for col in lookup_columns:
        if col in df.columns:
            values = df.loc[mask_unresolved, col].dropna().astype(str).unique()
            alias_names.update(values)

    if not alias_names:
        return pd.Series(pd.NA, index=df.index), 0

    # Batch lookup from database
    results = self.mapping_repository.lookup_batch(list(alias_names))

    # Apply results to DataFrame
    resolved = pd.Series(pd.NA, index=df.index)
    hit_count = 0

    for idx in df[mask_unresolved].index:
        row = df.loc[idx]
        for col in lookup_columns:
            if col not in row:
                continue
            value = row[col]
            if pd.isna(value):
                continue
            str_value = str(value)
            if str_value in results:
                resolved.loc[idx] = results[str_value].company_id
                hit_count += 1
                break

    return resolved, hit_count
```

**Backflow Mechanism:**
```python
def _backflow_new_mappings(
    self,
    df: pd.DataFrame,
    resolved_mask: pd.Series,
    strategy: ResolutionStrategy,
) -> Dict[str, int]:
    """
    Backflow new mappings to database cache.

    Collects mappings from rows resolved via existing column and inserts
    them into the database for future cache hits.

    Returns:
        Dict with keys: inserted, skipped, conflicts
    """
    if not self.mapping_repository:
        return {"inserted": 0, "skipped": 0, "conflicts": 0}

    new_mappings = []
    backflow_fields = [
        (strategy.account_number_column, "account", 2),
        (strategy.customer_name_column, "name", 4),
        (strategy.account_name_column, "account_name", 5),
    ]

    for idx in df[resolved_mask].index:
        row = df.loc[idx]
        company_id = str(row[strategy.output_column])

        # Skip temporary IDs
        if company_id.startswith("IN_"):
            continue

        for column, match_type, priority in backflow_fields:
            if column not in row:
                continue
            alias_value = row[column]
            if pd.isna(alias_value) or not str(alias_value).strip():
                continue

            new_mappings.append({
                "alias_name": str(alias_value).strip(),
                "canonical_id": company_id,
                "match_type": match_type,
                "priority": priority,
                "source": "pipeline_backflow",
            })

    if not new_mappings:
        return {"inserted": 0, "skipped": 0, "conflicts": 0}

    result = self.mapping_repository.insert_batch_with_conflict_check(new_mappings)

    if result.conflicts:
        logger.warning(
            "company_id_resolver.backflow.conflicts_detected",
            conflict_count=len(result.conflicts),
            sample_conflicts=result.conflicts[:5],  # Log first 5 only
        )

    logger.info(
        "company_id_resolver.backflow.completed",
        inserted=result.inserted_count,
        skipped=result.skipped_count,
        conflicts=len(result.conflicts),
    )

    return {
        "inserted": result.inserted_count,
        "skipped": result.skipped_count,
        "conflicts": len(result.conflicts),
    }
```

**EQC Sync Path (budgeted, cached):**
```python
def _resolve_via_eqc_sync(
    self,
    df: pd.DataFrame,
    mask_unresolved: pd.Series,
    strategy: ResolutionStrategy,
) -> Tuple[pd.Series, int, int]:
    """
    Resolve via EQC within budget; cache results to enterprise.company_mapping.

    Returns:
        resolved_series, eqc_hits, budget_remaining
    """
    if not self.enrichment_service or strategy.sync_lookup_budget <= 0:
        return pd.Series(pd.NA, index=df.index), 0, strategy.sync_lookup_budget

    budget_remaining = strategy.sync_lookup_budget
    resolved = pd.Series(pd.NA, index=df.index)
    eqc_hits = 0

    for idx in df[mask_unresolved].index:
        if budget_remaining <= 0:
            break
        name = df.loc[idx, strategy.customer_name_column]
        if pd.isna(name):
            continue

        match = self.enrichment_service.lookup(name)
        budget_remaining -= 1
        if match:
            resolved.loc[idx] = match.company_id
            eqc_hits += 1
            if self.mapping_repository:
                self.mapping_repository.insert_batch_with_conflict_check(
                    [{
                        "alias_name": str(name),
                        "canonical_id": match.company_id,
                        "match_type": "eqc",
                        "priority": 6,  # lower priority than YAML/DB, higher than temp
                        "source": "eqc_sync",
                    }]
                )

    return resolved, eqc_hits, budget_remaining
```

**Extended ResolutionStatistics:**
```python
# src/work_data_hub/infrastructure/enrichment/types.py
@dataclass
class ResolutionStatistics:
    total_rows: int = 0
    plan_override_hits: int = 0  # DEPRECATED - use yaml_hits["plan"]
    existing_column_hits: int = 0
    enrichment_service_hits: int = 0
    temp_ids_generated: int = 0
    unresolved: int = 0

    # NEW fields for Story 6.4
    yaml_hits: Dict[str, int] = field(default_factory=dict)  # {priority: count}
    db_cache_hits: int = 0
    eqc_sync_hits: int = 0
    budget_consumed: int = 0
    budget_remaining: int = 0
    backflow_stats: Dict[str, int] = field(default_factory=dict)  # {inserted, skipped, conflicts}

    def to_dict(self) -> Dict[str, Any]:
        """Convert statistics to dictionary for logging."""
        return {
            "total_rows": self.total_rows,
            "yaml_hits": self.yaml_hits,
            "yaml_hits_total": sum(self.yaml_hits.values()),
            "db_cache_hits": self.db_cache_hits,
            "eqc_sync_hits": self.eqc_sync_hits,
            "budget_consumed": self.budget_consumed,
            "budget_remaining": self.budget_remaining,
            "existing_column_hits": self.existing_column_hits,
            "enrichment_service_hits": self.enrichment_service_hits,
            "temp_ids_generated": self.temp_ids_generated,
            "unresolved": self.unresolved,
            "backflow": self.backflow_stats,
            # Backward compatibility
            "plan_override_hits": self.yaml_hits.get("plan", 0),
        }
```

**ResolutionStrategy Extension:**
```python
# Add new field to ResolutionStrategy
@dataclass
class ResolutionStrategy:
    plan_code_column: str = "计划代码"
    customer_name_column: str = "客户名称"
    account_name_column: str = "年金账户名"
    account_number_column: str = "年金账户号"  # NEW for account priority lookup
    company_id_column: str = "公司代码"
    output_column: str = "company_id"
    use_enrichment_service: bool = False
    sync_lookup_budget: int = 0  # EQC budget per batch
    generate_temp_ids: bool = True
    enable_backflow: bool = True  # NEW: control backflow behavior
```

### API Contracts (must implement)

- `CompanyMappingRepository.lookup_batch(alias_names: List[str], match_types: Optional[List[str]]) -> Dict[str, MatchResult]`
  - Input: alias_names (required, unique), match_types optional filter (`["plan","account","hardcode","name","account_name","eqc"]`)
  - Output: `{alias_name: MatchResult(company_id: str, match_type: str, priority: int, source: str)}`
  - Behavior: single SQL round-trip, ordered by `priority ASC`, returns highest-priority match per alias.
- `CompanyMappingRepository.insert_batch_with_conflict_check(mappings: List[MappingPayload]) -> InsertBatchResult`
  - MappingPayload keys: `alias_name:str`, `canonical_id:str`, `match_type:str`, `priority:int`, `source:str`
  - Result: `inserted_count:int`, `skipped_count:int`, `conflicts: List[{alias_name, match_type, existing_id, new_id}]`
  - Conflict rule: conflict when alias_name + match_type exists with different canonical_id; use `ON CONFLICT DO NOTHING`.
- `ResolutionStrategy.match_type / priority enums`
  - `plan`=1, `account`=2, `hardcode`=3, `name`=4, `account_name`=5, `eqc`=6, `temp`=7 (implicit), lower number = higher priority.
- `ResolutionStatistics` payload
  - Required keys: `yaml_hits`, `db_cache_hits`, `eqc_sync_hits`, `budget_consumed`, `budget_remaining`, `existing_column_hits`, `temp_ids_generated`, `backflow`, `unresolved`, `total_rows`.
- EQC path contract
  - Budget decremented per request; stop at zero.
  - Success: cache to DB via repository with `match_type="eqc"`, `priority=6`, `source="eqc_sync"`.
  - Failure/timeouts: log counts only; do not block; keep unresolved for temp ID path.

### Schema & Ops (enterprise.company_mapping)

- Columns: `alias_name (text, not null)`, `canonical_id (text, not null)`, `match_type (text, not null)`, `priority (int, not null)`, `source (text, not null)`, `created_at (timestamptz default now())`.
- Indexes: `(alias_name, match_type) unique`, `(priority ASC)` for ordering; ensure query uses `ORDER BY priority ASC`.
- ON CONFLICT: `DO NOTHING` on `(alias_name, match_type)`; conflicts reported via repository.
- Migrations: ensure `io/schema/migrations/versions/20251206_000001_create_enterprise_schema.py` applied; rerun `uv run alembic upgrade head` before tests.
- Env:
  - `DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/workdatahub`
  - `WDH_MAPPINGS_DIR=data/mappings`
  - `WDH_ALIAS_SALT=<production_salt>`
  - `EQC_TOKEN` (or existing auth flow) available to enrichment service.
- Smoke:
  - `uv run pytest -m unit tests/unit/infrastructure/enrichment/test_company_id_resolver.py -k yaml` (YAML path)
  - `uv run pytest -m unit tests/unit/infrastructure/enrichment/test_company_id_resolver.py -k db` (DB path, repository mocked)
  - `uv run pytest -m unit tests/unit/infrastructure/enrichment/test_company_id_resolver.py -k eqc` (budget + cache path)
  - `uv run alembic current` to confirm schema before integration tests.

### Security & Performance Guardrails

- Logging: bind counts only; never log alias_name/company_id/EQC tokens; follow Decision #8 sanitization.
- Secrets: `WDH_ALIAS_SALT`, `EQC_TOKEN` sourced from env; never persisted.
- Budget control: `sync_lookup_budget` must be enforced strictly; budget exhaustion halts EQC calls.
- PII: treat alias_name/company_name as PII; mask or omit in logs/metrics.
- Performance measurement: benchmark `resolve_batch` on 1,000 rows without EQC <100ms; EQC path measured separately with mocked latency; DB lookup single round-trip; YAML lookup vectorized.
- Backpressure: if repository unavailable, skip DB/EQC caching/backflow and proceed with temp IDs.

### LLM Quick Brief (developer-ready)

1) Priority: YAML (plan/account/hardcode/name/account_name) → DB cache → existing column → EQC sync (budgeted, cached) → temp ID.  
2) Constructor params: `yaml_overrides?`, `mapping_repository?`, `enrichment_service?`, `sync_lookup_budget`, `enable_backflow`, `plan_override_mapping` (deprecated). All optional/backward compatible.  
3) Contracts: `lookup_batch` returns highest-priority match per alias; `insert_batch_with_conflict_check` reports conflicts; `match_type` enum priority 1-7.  
4) Stats: track yaml/db/eqc hits, budget consumed/remaining, backflow (inserted/skipped/conflicts), temp IDs, unresolved.  
5) Ops: ensure `enterprise.company_mapping` schema + unique `(alias_name, match_type)`, env vars set, migrations applied; EQC failures must not block.  
6) Tests: YAML order, DB lookup, EQC budget/caching, backflow, backward compatibility, stats integrity, perf gate <100ms (no EQC).  
7) Guardrails: no PII in logs; enforce budget; no new deps or schema changes; conflict warnings limited to counts/samples.

### Testing Strategy

**Unit Tests (mocked database):**
- `test_yaml_lookup_plan_priority`: Plan code lookup works
- `test_yaml_lookup_all_priorities`: All 5 priority levels checked in order
- `test_yaml_lookup_priority_order`: Higher priority wins over lower
- `test_db_cache_lookup_batch`: Database batch lookup works
- `test_db_cache_lookup_no_repository`: Graceful skip when no repository
- `test_backflow_inserts_new_mappings`: New mappings inserted
- `test_backflow_skips_temp_ids`: Temporary IDs not backflowed
- `test_backflow_detects_conflicts`: Conflicts logged as warnings
- `test_backward_compatibility_plan_override`: Old API still works
- `test_statistics_yaml_breakdown`: Statistics include YAML breakdown
- `test_performance_1000_rows`: <100ms for 1000 rows

**Integration Tests (deferred to Story 6.5):**
- Full pipeline with database connection
- EQC sync lookup integration

### Previous Story Learnings (Stories 6.1, 6.2, 6.3)

1. Keep migrations idempotent and reversible (Story 6.1).
2. Prefer explicit constraints (CHECK, UNIQUE) to prevent data drift (Story 6.1).
3. Keep enrichment optional; pipelines must not block when cache unavailable (Story 6.1).
4. Use `normalize_for_temp_id()` for consistent normalization (Story 6.2).
5. Never log sensitive data (salt, tokens, alias values) (Story 6.2, 6.3).
6. Use dataclasses for result types (`MatchResult`, `InsertBatchResult`) (Story 6.3).
7. Use SQLAlchemy text() for raw SQL with parameterized queries (Story 6.3).
8. YAML loader: missing file → empty dict (no exception), invalid YAML → raise ValueError (Story 6.3).
9. Repository: caller owns transaction; log counts only, never alias/company_id values (Story 6.3).
10. CI regressions surfaced on mypy/ruff (Story 6.3) — keep signatures precise and imports minimal.
11. Legacy parity checks flagged strict schema expectations (Story 6.1) — do not relax constraints.

### Git Intelligence (Recent Commits)

```
85f48e3 feat(story-6.3): finalize mapping repository and yaml overrides
78e4d11 fix(ci): resolve mypy, ruff-lint and ruff-format failures
8b01df7 docs(story-6.2): finalize temporary company ID story
8467f08 fix(story-6.1): harden enterprise schema migration and finalize review
```

**Patterns to follow:**
- Use dataclasses for new types
- Use structlog for logging with context binding
- Follow existing test patterns in `tests/unit/infrastructure/enrichment/`
- Use `field(default_factory=dict)` for mutable default values
- Commit impact summary:
  - `85f48e3`: repository API shape + YAML loader; reuse patterns and conflict handling.
  - `78e4d11`: lint/format/mypy rules tightened—ensure compliance.
  - `8b01df7`: temp ID doc—keep deterministic HMAC rules intact.
  - `8467f08`: schema hardening—respect enterprise schema constraints.

### CRITICAL: Do NOT Reinvent

- **DO NOT** create alternative resolution strategies - extend existing `CompanyIdResolver`
- **DO NOT** create new repository classes - use existing `CompanyMappingRepository`
- **DO NOT** modify database schema - use existing `enterprise.company_mapping`
- **DO NOT** add external dependencies - use stdlib + pandas + SQLAlchemy only
- **DO NOT** break backward compatibility - all new parameters must be optional

### Performance Requirements

| Operation | Target | Measurement |
|-----------|--------|-------------|
| `resolve_batch(1000 rows)` | <100ms | Unit test with mock |
| YAML lookup (5 levels) | <10ms | Unit test |
| DB cache lookup (1000 aliases) | <50ms | Unit test with mock |
| EQC sync (budgeted) | Respect budget; latency bounded by mock | Unit test with mock budget + latency |
| Backflow insert (100 mappings) | <50ms | Unit test with mock |

### Environment Variables

```bash
# Optional - defaults to data/mappings
WDH_MAPPINGS_DIR=data/mappings

# Required for database operations
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/workdatahub

# Required for temporary ID generation
WDH_ALIAS_SALT=<production_salt>
```

### Database Access & Transactions

- Repository accepts upstream `Connection`; caller owns commit/rollback
- No implicit autocommit; wrap inserts in explicit transaction
- Always parameterize via `text()`; no f-strings
- Bind logger context with counts only; never log alias/company_id values

## References

- Tech Spec: `docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md` (Story 6.3, 6.3.1, 6.4)
- Epic: `docs/epics/epic-6-company-enrichment-service.md` (Story 5.4 in epic index)
- Architecture Decision: `docs/architecture/architectural-decisions.md` (AD-010)
- Database Schema: `io/schema/migrations/versions/20251206_000001_create_enterprise_schema.py`
- Mapping Repository: `src/work_data_hub/infrastructure/enrichment/mapping_repository.py`
- YAML Loader: `src/work_data_hub/config/mapping_loader.py`
- CompanyIdResolver: `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py`

### Quick Start (Dev Agent Checklist)

1. **Files to modify**: `company_id_resolver.py`, `types.py`, `test_company_id_resolver.py`
2. **Files to reference**: `mapping_repository.py`, `mapping_loader.py` (Story 6.3 outputs)
3. **Env**: `WDH_MAPPINGS_DIR`, `DATABASE_URL`, `WDH_ALIAS_SALT`
4. **Performance gates**: `resolve_batch(1000)` <100ms (no EQC); YAML <10ms; DB <50ms; EQC obeys budget
5. **Commands**: `uv run pytest tests/unit/infrastructure/enrichment/test_company_id_resolver.py -v`; `uv run ruff check`; `uv run mypy --strict src/`
6. **Logging**: `utils.logging.get_logger(__name__)`; bind counts only; never log alias/company_id or EQC token
7. **EQC**: `sync_lookup_budget` enforced; cache successes to DB via repository; failures degrade gracefully
8. **Backward compatibility**: All existing tests must pass without modification

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 40 unit tests pass (28 existing + 12 new Story 6.4 tests)
- Ruff check: All checks passed
- Mypy: Success, no issues found

### Completion Notes List

- Implemented multi-tier YAML lookup with 5 priority levels (plan → account → hardcode → name → account_name)
- Added database cache lookup via CompanyMappingRepository.lookup_batch()
- Implemented EQC sync path with budget enforcement and automatic caching
- Added backflow mechanism to populate database cache from existing column hits
- Extended ResolutionStatistics with yaml_hits breakdown, db_cache_hits, eqc_sync_hits, budget tracking, and backflow_stats
- Maintained full backward compatibility - all 28 existing tests pass unchanged
- Added deprecation warning for plan_override_mapping parameter
- Performance verified: 1000 rows processed in <100ms without EQC

### File List

- `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py` - MODIFIED (multi-tier lookup implementation)
- `src/work_data_hub/infrastructure/enrichment/types.py` - MODIFIED (ResolutionStatistics, ResolutionStrategy extensions)
- `tests/unit/infrastructure/enrichment/test_company_id_resolver.py` - MODIFIED (12 new tests for Story 6.4)
- `docs/sprint-artifacts/sprint-status.yaml` - UPDATED (story status)
- `docs/sprint-artifacts/stories/validation-report-20251207-004530.md` - NEW (validation report artifact)

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-07 | Story drafted with comprehensive context for dev readiness | Claude Opus 4.5 |
| 2025-12-07 | Implementation complete: multi-tier lookup, DB cache, EQC sync, backflow, extended stats | Claude Opus 4.5 |
