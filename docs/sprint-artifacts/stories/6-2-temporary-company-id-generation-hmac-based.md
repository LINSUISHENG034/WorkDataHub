# Story 6.2: Temporary Company ID Generation (HMAC-based)

Status: completed

## Context & Business Value

- Epic 6 aims to deliver a resilient company enrichment service: internal mappings → EQC sync (budgeted) → async backfill → temporary IDs as safety net.
- Temporary IDs guarantee pipelines never block; the same unresolved company name maps to the same ID across runs, ensuring consistent joins and safe backfill later.
- Must align with Clean Architecture: cryptographic generation stays in the infrastructure enrichment layer; no new external dependencies.

## Acceptance Criteria

1. **AC1**: Deterministic ID format — `HMAC_SHA1(WDH_ALIAS_SALT, normalized_name)` → Base32 (first 10 bytes) → `IN_<16 chars>`.
2. **AC2**: Idempotent — identical input + salt returns identical ID.
3. **AC3**: Collision resistance — 10,000 distinct names produce unique IDs.
4. **AC4**: Joins safe — storing the temporary ID in DB yields consistent joins for the same name across runs.
5. **AC5**: Future resolution — when enrichment later finds a real `company_id`, pipelines replace the temporary ID without breaking joins.
6. **AC6**: Legacy-compatible normalization — whitespace removal, status marker removal (29 patterns), bracket normalization (English→Chinese), full-width→half-width, business pattern removal, lowercase for hash stability.
7. **AC7**: Security — salt `WDH_ALIAS_SALT` stays secret (env only), never committed or logged.
8. **AC8**: Performance — generating IDs for 1,000 names runs in <100ms CPU time; no external calls.
9. **AC9**: Integration contract — used as the final fallback in `CompanyIdResolver`; no new libraries beyond stdlib (`hmac`, `hashlib`, `base64`); keep functions in `src/work_data_hub/infrastructure/enrichment/normalizer.py`.

## Dependencies & Interfaces

- Epic: `docs/epics/epic-6-company-enrichment-service.md` (Story 5.2 in epic index).
- Tech Spec: `docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md` (temporary ID format, salt handling, pipeline placement).
- Pipeline integration: `CompanyIdResolver` (fallback when YAML/database/EQC miss; does not spend EQC budget).
- Async/backfill path: temporary IDs later replaced via async enrichment queue (outside this story but must remain compatible).
- Data stores: IDs may be written to `enterprise` schema tables; ensure width supports `IN_` prefix + 16 chars (19 total).

## Tasks / Subtasks

- [x] Task 1: Implement name normalization (AC6) in `infrastructure/enrichment/normalizer.py`
  - [x] Whitespace removal
  - [x] Status marker removal (29 patterns)
  - [x] Bracket normalization (English→Chinese)
  - [x] Full-width → half-width conversion
  - [x] Business pattern removal
  - [x] Lowercase conversion for hash stability
- [x] Task 2: Implement HMAC-based ID generation (AC1, AC2, AC3, AC9)
  - [x] `generate_temp_company_id()` uses HMAC-SHA1 + Base32 (first 10 bytes)
  - [x] Prefix with `IN_`; format length 19
  - [x] Handle empty normalized names with `"__empty__"` guard
- [x] Task 3: Unit tests for normalization (AC6)
  - [x] Whitespace handling (10 cases)
  - [x] Status markers (29 parametrized)
  - [x] Bracket + full-width normalization
  - [x] Legacy parity (10 cases)
- [x] Task 4: Unit tests for ID generation (AC1–AC3, AC8)
  - [x] Format validation (`IN_` + 16 chars)
  - [x] Consistency + uniqueness + salt sensitivity
  - [x] Empty name handling
  - [x] Throughput guard (no external calls; CPU-only)
- [x] Task 5: Integration & documentation (AC4–AC7, AC9)
  - [x] Verify integration with `CompanyIdResolver` fallback (no EQC budget impact)
  - [x] Document env var requirements (WDH_ALIAS_SALT secret)
  - [x] Note DB field length expectations (≥19 chars) for temp IDs
  - [x] Record algorithm + file boundaries in architecture notes

## Dev Notes

- **Implementation Status:** COMPLETE — algorithm and tests exist; pipelines use it as fallback.
- **Re-use, no reinvention:** Extend/adjust `normalize_for_temp_id` and `generate_temp_company_id` only; do not create parallel implementations.
- **Clean Architecture:** Lives in infrastructure layer; no domain/IO imports; only stdlib crypto/base32.

## Architecture Context

- **Location:** `src/work_data_hub/infrastructure/enrichment/normalizer.py`
- **Layer:** Infrastructure (I/O layer per Clean Architecture)
- **Integration Point:** Consumed by `CompanyIdResolver` during pipeline processing; no EQC calls triggered.
- **Reference:** AD-002 in `docs/architecture/architectural-decisions.md`

## File Locations

| File | Purpose | Status |
|------|---------|--------|
| `src/work_data_hub/infrastructure/enrichment/normalizer.py` | Normalization + temp ID generator | ✅ EXISTING |
| `src/work_data_hub/infrastructure/enrichment/__init__.py` | Module exports | ✅ EXISTING |
| `tests/unit/infrastructure/enrichment/test_normalizer.py` | Unit tests (60 tests) | ✅ EXISTING |
| `tests/fixtures/legacy_normalized_names.py` | Legacy parity fixtures | ✅ EXISTING |

## Algorithm Details

**Temporary ID Format:** `IN_<16-char-Base32>`

```python
def generate_temp_company_id(customer_name: str, salt: str) -> str:
    normalized = normalize_for_temp_id(customer_name)
    if not normalized:
        normalized = "__empty__"
    digest = hmac.new(
        salt.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    encoded = base64.b32encode(digest[:10]).decode("ascii")
    return f"IN_{encoded}"
```

**Normalization Operations (order):**
1. Remove all whitespace
2. Remove business patterns (及下属子企业, -养老, etc.)
3. Remove status markers (29+ patterns)
4. Full-width → half-width conversion
5. Normalize brackets to Chinese
6. Remove trailing punctuation
7. Lowercase (hash stability)

### IMPORTANT: `normalize_for_temp_id` vs `normalize_company_name`

本模块的 `normalize_for_temp_id` **仅用于 HMAC 哈希计算**，其目的是确保同一公司的不同写法变体能生成相同的临时 ID。标准化后的结果**不会存入数据库**。

与之对比，`infrastructure/cleansing/rules/string_rules.py` 中的 `normalize_company_name` 用于**数据库存储的客户名称规范化**，遵循中国企业名称规范：

| 函数 | 用途 | 全角/半角处理 | 结果去向 |
|------|------|--------------|----------|
| `normalize_for_temp_id` | HMAC 哈希输入 | 全角ASCII→半角，括号→中文全角，最后 lowercase | 仅用于哈希，不存储 |
| `normalize_company_name` | 数据库存储规范化 | 全角ASCII→半角，**括号半角→全角** (中国企业名称规范) | 存入数据库 |

**示例对比：**
```python
# normalize_company_name (数据库存储)
"中国平安(集团)" → "中国平安（集团）"  # 括号转全角，符合中国企业名称规范

# normalize_for_temp_id (仅用于哈希)
"中国平安(集团)" → "中国平安（集团）" → lowercase → 用于 HMAC 计算
```

两者的括号处理结果相同（都转为中文全角），但 `normalize_for_temp_id` 额外做了 lowercase 以确保哈希稳定性。

## Test Coverage

- 60 unit tests:
  - `TestNormalizeForTempId` (edge cases)
  - `TestNormalizationConsistency` (variants)
  - `TestGenerateTempCompanyId` (format/determinism/uniqueness/salt sensitivity)
  - `TestAllStatusMarkers` (29 parametrized)
  - `TestLegacyParity` (legacy compatibility)
- Command:
```bash
PYTHONPATH=src uv run pytest tests/unit/infrastructure/enrichment/test_normalizer.py -v
```

## Security & Operational Considerations

1. **Salt Management:** `WDH_ALIAS_SALT` environment variable
   - Secret only; not in git or logs
   - Changing salt invalidates historical temporary IDs
2. **Determinism & Stability:** No randomness; CPU-only; no network/API calls
3. **Database Width:** Columns storing temp IDs must allow 19 chars (`IN_` + 16)
4. **Logging:** Never log raw salt or raw HMAC inputs

## Integration with CompanyIdResolver

```python
# In CompanyIdResolver.resolve_batch()
if strategy.generate_temp_ids and mask_still_missing.any():
    temp_ids = result_df.loc[mask_still_missing, strategy.customer_name_column].apply(
        lambda x: generate_temp_company_id(x, self.salt)
    )
    result_df.loc[mask_still_missing, strategy.output_column] = temp_ids
```

- Fallback only; does not consume EQC sync budget.
- Compatible with async enrichment queue replacing temporary IDs later.
- Backfill logic must accept `IN_` IDs without blocking pipeline flow.

## Performance & Observability

- Generation is pure CPU; expected <100ms for 1,000 names on baseline dev hardware.
- No new metrics required; reuse existing pipeline logging. If timing is added, avoid logging sensitive inputs.

## Risks & Boundaries

- Do **not** create alternative generators or move the function to new modules.
- Do **not** introduce non-stdlib crypto or base32 libraries.
- Keep normalization rules aligned with legacy parity; modifying patterns requires updating fixtures/tests.
- Ensure DB schema fields that store temp IDs are wide enough (≥19 chars) before deployment.

## Previous Story Learnings (Story 6.1)

1. Keep migrations idempotent and reversible.
2. Prefer explicit constraints (CHECK, UNIQUE) to prevent data drift.
3. Keep enrichment optional; pipelines must not block when cache unavailable.
4. Document indexes to avoid accidental duplicates in future migrations.

## References

- Tech Spec: `docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md`
- Epic: `docs/epics/epic-6-company-enrichment-service.md` (Story 5.2)
- Architecture Decision: `docs/architecture/architectural-decisions.md` (AD-002)
- Legacy Analysis: `docs/supplement/03_clean_company_name_logic.md`
- Implementation: `src/work_data_hub/infrastructure/enrichment/normalizer.py`

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

- All 60 unit tests passing
- Implementation verified against legacy behavior

### Completion Notes List

- Implementation complete and in production use
- 60 unit tests covering all acceptance criteria
- Legacy parity verified with 10 test cases
- Integration with CompanyIdResolver confirmed

### File List

- `src/work_data_hub/infrastructure/enrichment/normalizer.py` (EXISTING - core implementation)
- `src/work_data_hub/infrastructure/enrichment/__init__.py` (EXISTING - exports)
- `tests/unit/infrastructure/enrichment/test_normalizer.py` (EXISTING - 60 tests)
- `tests/fixtures/legacy_normalized_names.py` (EXISTING - test data)

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-06 | Story drafted - validates existing implementation | Claude Opus 4.5 |
| 2025-12-06 | Context and guardrails strengthened for dev readiness | Bob (Scrum Master) |
