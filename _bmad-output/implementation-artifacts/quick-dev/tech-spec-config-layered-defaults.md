# Tech-Spec: Configuration Layered Defaults Architecture

**Created:** 2025-12-12
**Status:** Ready for Development (Post-Current Epic)
**Domain:** Infrastructure - Configuration Management
**Complexity:** Medium
**Estimated Effort:** 2-3 days

---

## Overview

### Problem Statement

The current `config/data_sources.yml` configuration requires full configuration for each domain, leading to significant duplication:

**Current Pain Points:**
- Every domain repeats `version_strategy: "highest_number"`
- Every domain repeats `fallback: "error"`
- Every domain repeats `exclude_patterns: ["~$*", "*回复*", "*.eml"]`
- Every domain repeats `output.schema_name: "business"`
- Global policy changes require updating multiple domain definitions
- High risk of configuration drift between domains
- Violates DRY (Don't Repeat Yourself) principle

**Example of Current Duplication:**
```yaml
domains:
  annuity_performance:
    base_path: "tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集"
    file_patterns: ["*年金终稿*.xlsx"]
    exclude_patterns: ["~$*", "*回复*", "*.eml"]  # Repeated
    sheet_name: "规模明细"
    version_strategy: "highest_number"  # Repeated
    fallback: "error"  # Repeated
    output:
      table: "规模明细"
      schema_name: "business"  # Repeated

  annuity_income:
    base_path: "tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集"
    file_patterns: ["*年金终稿*.xlsx"]
    exclude_patterns: ["~$*", "*回复*", "*.eml"]  # Repeated
    sheet_name: "收入明细"
    version_strategy: "highest_number"  # Repeated
    fallback: "error"  # Repeated
    output:
      table: "收入明细"
      schema_name: "business"  # Repeated
```

### Solution

Implement a **layered configuration architecture** with global defaults and domain-level overrides:

**Proposed Architecture:**
```yaml
schema_version: "1.0"

# Global defaults - inherited by all domains
defaults:
  version_strategy: "highest_number"
  fallback: "error"
  exclude_patterns: ["~$*", "*回复*", "*.eml"]
  output:
    schema_name: "public"

# Domain-specific configurations - inherit defaults, override as needed
domains:
  annuity_performance:
    base_path: "tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集"
    file_patterns: ["*年金终稿*.xlsx"]
    sheet_name: "规模明细"
    output:
      table: "规模明细"
      # schema_name inherited from defaults

  annuity_income:
    base_path: "tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集"
    file_patterns: ["*年金终稿*.xlsx"]
    sheet_name: "收入明细"
    output:
      table: "收入明细"
    # All other fields inherited from defaults
```

**Key Benefits:**
- ✅ Eliminate configuration duplication (DRY principle)
- ✅ Single source of truth for global policies
- ✅ Domain configurations focus on differences only
- ✅ Easier to maintain and evolve
- ✅ Reduced risk of configuration drift

### Scope

**In Scope:**
- ✅ Add `defaults` section to `DataSourceConfigV2` schema
- ✅ Implement inheritance and override logic in domain config loading
- ✅ Refactor `config/data_sources.yml` to use layered structure
- ✅ Update all tests to support new schema
- ✅ Delete Legacy schema (DomainConfig, DataSourcesConfig) - Clean Break
- ✅ Update validation scripts to use new schema
- ✅ Update documentation and examples

**Out of Scope:**
- ❌ Grouped defaults (e.g., annuity-specific defaults)
- ❌ Environment-specific defaults (dev/staging/prod)
- ❌ Dynamic defaults based on conditions
- ❌ Backward compatibility with Legacy schema
- ❌ Migration scripts (manual migration acceptable)

**Explicitly Excluded (Clean Break Strategy):**
- ❌ Maintaining Legacy `DomainConfig` schema
- ❌ Maintaining Legacy `DataSourcesConfig` schema
- ❌ Maintaining `DataSourceConnector` (lines 51-564 in file_connector.py)
- ❌ Maintaining `src/work_data_hub/config/data_sources.yml` (Legacy config)

---

## Context for Development

### Codebase Patterns

**1. Pydantic Validation Pattern**
- All configuration uses Pydantic v2 models for validation
- Validation happens at startup in `Settings.load_and_validate_data_sources()`
- Fail-fast approach: invalid config prevents application startup
- Security validators prevent path traversal and injection attacks

**2. Settings Singleton Pattern**
- `get_settings()` returns cached singleton instance
- Configuration loaded once at startup
- All modules access config via `settings.data_sources.domains[domain_name]`

**3. Epic 3 Architecture (Current)**
- Template-based paths with `{YYYYMM}`, `{YYYY}`, `{MM}` variables
- Version-aware folder scanning (V1, V2, V3)
- Pattern-based file matching with exclusions
- Multi-stage discovery pipeline: config_validation → version_detection → file_matching → excel_reading

**4. Dependency Inversion Principle**
- High-level modules depend on abstractions (Settings, schemas)
- Low-level file I/O isolated in connectors
- Domain services use `get_domain_output_config()` helper

### Files to Reference

**Core Schema and Settings:**
- `src/work_data_hub/infrastructure/settings/data_source_schema.py:14-108` - DomainConfigV2, DataSourceConfigV2, OutputConfig
- `src/work_data_hub/config/settings.py:157-446` - Settings class, load_and_validate_data_sources()
- `config/data_sources.yml:1-101` - Current configuration file

**Configuration Usage:**
- `src/work_data_hub/io/connectors/file_connector.py:586-868` - FileDiscoveryService
- `src/work_data_hub/config/output_config.py:21-108` - get_domain_output_config()
- `src/work_data_hub/orchestration/ops.py:45-146` - Dagster ops

**Tests (High Coverage):**
- `tests/unit/config/test_schema_v2.py:1-518` - Schema validation tests
- `tests/unit/io/connectors/test_file_discovery_service.py:1-767` - Discovery service tests
- `tests/integration/config/test_settings_integration.py` - Settings integration tests

**Legacy Code to Delete:**
- `src/work_data_hub/infrastructure/settings/data_source_schema.py:110-280` - Legacy DomainConfig, DataSourcesConfig
- `src/work_data_hub/io/connectors/file_connector.py:51-564` - Legacy DataSourceConnector
- `tests/config/test_data_sources_schema.py:1-362` - Legacy schema tests
- `src/work_data_hub/config/data_sources.yml` - Legacy config file (if exists)

**Scripts to Update:**
- `scripts/tools/validate/validate_data_source_columns.py:58-131` - Hardcoded DOMAIN_CONFIGS (technical debt)

### Technical Decisions

**Decision 1: Clean Break Strategy (No Backward Compatibility)**
- **Rationale:** Project is in active development (Epic 6), not production. Clean architecture is prioritized over compatibility.
- **Trade-off:** All tests will break initially, but results in cleaner codebase long-term.
- **Mitigation:** High test coverage (84+ files) will quickly identify issues.

**Decision 2: Single-Level Defaults (No Grouping)**
- **Rationale:** YAGNI principle - grouped defaults add complexity without current need.
- **Trade-off:** If future domains need different defaults, must override individually.
- **Future-proofing:** Can add grouped defaults later without breaking changes.

**Decision 3: output.schema_name Default = "public"**
- **Rationale:** User requirement - standardize on "public" schema instead of "business".
- **Impact:** Existing domains using "business" will inherit "public" unless explicitly overridden.
- **Migration:** Must update existing domains to explicitly set `schema_name: "business"` if needed.

**Decision 4: Shallow Merge for Nested Objects**
- **Rationale:** Simple, predictable behavior. Deep merge adds complexity.
- **Example:** If domain defines `output.table`, it must also define `output.schema_name` if different from default.
- **Alternative Considered:** Deep merge (rejected due to complexity and ambiguity).

**Decision 5: TDD Approach**
- **Rationale:** Write tests first to define expected behavior, then implement.
- **Benefit:** Ensures all edge cases covered before implementation.
- **Process:** Write failing tests → Implement schema → Refactor config → All tests pass.

---

## Implementation Plan

### Tasks

**Phase 1: Schema Design and Testing (TDD)**
- [ ] **Task 1.1:** Design `DefaultsConfig` Pydantic model
  - Fields: `version_strategy`, `fallback`, `exclude_patterns`, `output` (optional OutputConfig)
  - Validation: Same rules as DomainConfigV2 for shared fields
  - Location: `src/work_data_hub/infrastructure/settings/data_source_schema.py`

- [ ] **Task 1.2:** Write comprehensive tests for defaults inheritance
  - Test: Domain inherits all defaults when no overrides
  - Test: Domain overrides individual fields (version_strategy, fallback)
  - Test: Domain overrides nested output config (shallow merge)
  - Test: Domain with no defaults defined (backward compat test - should fail gracefully)
  - Test: Invalid defaults (should fail validation at startup)
  - Location: `tests/unit/config/test_schema_v2_defaults.py` (new file)

- [ ] **Task 1.3:** Modify `DataSourceConfigV2` to support defaults
  - Add `defaults: Optional[DefaultsConfig]` field
  - Add `@model_validator` to merge defaults into domain configs
  - Merge logic: Domain fields override defaults, missing fields inherit
  - Shallow merge for nested objects (output)

- [ ] **Task 1.4:** Update `DomainConfigV2` to mark fields as optional
  - Make `version_strategy`, `fallback`, `exclude_patterns` optional (can be inherited)
  - Add validation: If no defaults, these fields must be provided
  - Ensure `base_path`, `file_patterns`, `sheet_name` remain required

**Phase 2: Configuration Migration**
- [ ] **Task 2.1:** Refactor `config/data_sources.yml` to use defaults
  - Add `defaults` section with common configuration
  - Remove duplicated fields from domain definitions
  - Verify schema_version remains "1.0"

- [ ] **Task 2.2:** Update Settings validation logic
  - Ensure `load_and_validate_data_sources()` handles defaults correctly
  - Add logging for inherited vs overridden fields (debug visibility)
  - Test startup with new config structure

**Phase 3: Test Suite Updates**
- [ ] **Task 3.1:** Update all test fixtures using DomainConfigV2
  - Files: `test_file_discovery_service.py`, `test_settings_integration.py`, etc.
  - Strategy: Add defaults to test configs or make domain configs complete
  - Verify all unit tests pass

- [ ] **Task 3.2:** Update integration tests
  - Files: `test_annuity_config.py`, `test_file_discovery_integration.py`
  - Verify end-to-end workflows with new config structure

- [ ] **Task 3.3:** Update E2E tests
  - Files: `test_annuity_overwrite_append_small_subsets.py`, `test_trustee_performance_e2e.py`
  - Verify full pipeline execution with new config

**Phase 4: Legacy Code Removal (Clean Break)**
- [ ] **Task 4.1:** Delete Legacy schema classes
  - Remove `DomainConfig` class (lines ~110-180 in data_source_schema.py)
  - Remove `DataSourcesConfig` class (lines ~182-220)
  - Remove `DiscoveryConfig` class
  - Remove `validate_data_sources_config()` function (Legacy)
  - Remove `get_domain_config()` function (Legacy)

- [ ] **Task 4.2:** Delete Legacy DataSourceConnector
  - Remove `DataSourceConnector` class (lines 51-564 in file_connector.py)
  - Verify no references remain in codebase

- [ ] **Task 4.3:** Delete Legacy tests
  - Remove `tests/config/test_data_sources_schema.py` entirely
  - Remove any other tests referencing Legacy schema

- [ ] **Task 4.4:** Delete Legacy config file (if exists)
  - Remove `src/work_data_hub/config/data_sources.yml` (Legacy location)

**Phase 5: Scripts and Documentation**
- [ ] **Task 5.1:** Refactor validation script
  - File: `scripts/tools/validate/validate_data_source_columns.py`
  - Replace hardcoded `DOMAIN_CONFIGS` with YAML loading
  - Use `get_domain_config_v2()` to read from config file

- [ ] **Task 5.2:** Update documentation
  - Update README.md with new config structure examples
  - Update runbooks referencing configuration
  - Update architecture docs

- [ ] **Task 5.3:** Update .env.example if needed
  - Verify config path references are correct

**Phase 6: Validation and Rollout**
- [ ] **Task 6.1:** Run full test suite
  - Unit tests: `uv run pytest tests/unit/`
  - Integration tests: `uv run pytest tests/integration/`
  - E2E tests: `uv run pytest tests/e2e/`
  - Target: 100% pass rate

- [ ] **Task 6.2:** Manual validation
  - Start application and verify Settings loads correctly
  - Run file discovery for each domain
  - Verify output config retrieval works

- [ ] **Task 6.3:** Git tag and commit
  - Tag current stable version before merge (rollback point)
  - Commit with clear message: "feat: implement layered configuration defaults"

### Acceptance Criteria

**AC1: Schema Validation**
- ✅ Given a config with `defaults` section
- ✅ When a domain omits `version_strategy`, `fallback`, `exclude_patterns`
- ✅ Then the domain inherits these values from defaults
- ✅ And validation passes without errors

**AC2: Domain Override**
- ✅ Given a config with `defaults.fallback = "error"`
- ✅ When a domain defines `fallback: "use_latest_modified"`
- ✅ Then the domain uses its own value, not the default
- ✅ And other fields still inherit from defaults

**AC3: Nested Object Merge (Shallow)**
- ✅ Given `defaults.output.schema_name = "public"`
- ✅ When a domain defines `output.table = "custom_table"`
- ✅ Then the domain must also define `output.schema_name` explicitly
- ✅ Or it will be missing (shallow merge, not deep merge)

**AC4: Backward Incompatibility (Clean Break)**
- ✅ Given Legacy `DomainConfig` schema is deleted
- ✅ When code tries to import `DomainConfig`
- ✅ Then ImportError is raised
- ✅ And no Legacy code remains in codebase

**AC5: Configuration File Simplification**
- ✅ Given the refactored `config/data_sources.yml`
- ✅ When comparing line count to original
- ✅ Then duplicated lines are reduced by ~40%
- ✅ And all domains still function correctly

**AC6: Test Coverage Maintained**
- ✅ Given all tests updated for new schema
- ✅ When running full test suite
- ✅ Then 100% of tests pass
- ✅ And coverage remains ≥ current level

**AC7: Validation Script Updated**
- ✅ Given `validate_data_source_columns.py` refactored
- ✅ When running script with `--domain annuity_performance`
- ✅ Then script reads config from YAML (not hardcoded)
- ✅ And validation results are correct

**AC8: Settings Startup**
- ✅ Given application starts with new config
- ✅ When `get_settings()` is called
- ✅ Then Settings loads without errors
- ✅ And `settings.data_sources.domains` contains all domains with merged config

**AC9: File Discovery Integration**
- ✅ Given FileDiscoveryService uses new config
- ✅ When calling `discover_and_load(domain="annuity_performance", month="202501")`
- ✅ Then discovery succeeds using inherited defaults
- ✅ And correct file is loaded

**AC10: Output Config Retrieval**
- ✅ Given `get_domain_output_config("annuity_performance")`
- ✅ When domain inherits `schema_name` from defaults
- ✅ Then function returns `("规模明细", "public")`
- ✅ And Strangler Fig pattern (_NEW suffix) still works in validation mode

---

## Additional Context

### Dependencies

**Internal Dependencies:**
- Pydantic v2 (already in use)
- PyYAML (already in use)
- No new external dependencies required

**Module Dependencies:**
- `data_source_schema.py` → `settings.py` → All consumers
- Breaking change in schema affects all downstream modules
- High test coverage mitigates risk

**No External API Dependencies:**
- Configuration is file-based, no external services

### Testing Strategy

**1. Test-Driven Development (TDD)**
- Write tests first to define expected behavior
- Implement schema changes to make tests pass
- Refactor with confidence (tests protect against regressions)

**2. Test Pyramid**
- **Unit Tests (Primary):** Test defaults inheritance logic in isolation
  - Test DefaultsConfig validation
  - Test merge logic in DataSourceConfigV2
  - Test edge cases (missing defaults, partial overrides, nested objects)
- **Integration Tests (Secondary):** Test Settings loading with new config
  - Test startup with valid config
  - Test startup with invalid config (should fail fast)
- **E2E Tests (Tertiary):** Test full pipeline with new config
  - Test file discovery end-to-end
  - Test domain service execution

**3. Test Coverage Goals**
- Maintain current coverage level (≥ 85%)
- Add specific tests for defaults inheritance (new functionality)
- Ensure all edge cases covered (missing defaults, invalid overrides)

**4. Manual Testing Checklist**
- [ ] Start application with new config (verify no startup errors)
- [ ] Run file discovery for each domain (verify correct files found)
- [ ] Run domain service for each domain (verify correct output)
- [ ] Check logs for inherited vs overridden fields (debug visibility)

### Notes

**Migration Timing:**
- **Scheduled:** Post-current Epic completion
- **Rationale:** Avoid disrupting active development work
- **Preparation:** Tech-spec ready, can start immediately when Epic completes

**Rollback Plan:**
- Git tag current stable version before starting work
- If critical issues found, revert to tagged version
- Estimated rollback time: < 5 minutes (git revert)

**Performance Considerations:**
- Defaults merge happens once at startup (no runtime overhead)
- No impact on file discovery performance
- Settings singleton ensures config loaded only once

**Security Considerations:**
- Existing security validators remain in place (path traversal prevention)
- Defaults do not introduce new attack vectors
- Template variable validation unchanged

**Future Enhancements (Out of Scope):**
- Grouped defaults (e.g., annuity-specific defaults)
- Environment-specific defaults (dev/staging/prod)
- Dynamic defaults based on conditions
- Configuration hot-reload (currently requires restart)

**Known Limitations:**
- Shallow merge for nested objects (not deep merge)
  - Domain must fully define nested objects if overriding
  - Example: If overriding `output.table`, must also define `output.schema_name`
- No validation for unused defaults (defaults can contain fields not used by any domain)

**Communication Plan:**
- Notify team before starting work (coordinate with current Epic completion)
- Update team documentation with new config structure
- Provide migration guide for future domain additions

---

## Implementation Checklist Summary

**Pre-Implementation:**
- [ ] Current Epic completed
- [ ] Team notified of upcoming changes
- [ ] Git tag created for rollback point

**Implementation (Estimated 2-3 days):**
- [ ] Phase 1: Schema Design and Testing (TDD) - 0.5 day
- [ ] Phase 2: Configuration Migration - 0.5 day
- [ ] Phase 3: Test Suite Updates - 1 day
- [ ] Phase 4: Legacy Code Removal - 0.5 day
- [ ] Phase 5: Scripts and Documentation - 0.5 day
- [ ] Phase 6: Validation and Rollout - 0.5 day

**Post-Implementation:**
- [ ] All tests passing (100%)
- [ ] Documentation updated
- [ ] Team notified of completion
- [ ] Monitor for issues in next sprint

---

**End of Tech-Spec**

*This specification is ready for implementation. All design decisions have been made, risks identified, and implementation path clearly defined. Proceed with confidence.*
