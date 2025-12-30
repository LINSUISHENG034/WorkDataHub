# Story 1.4: Configuration Management Framework

Status: review

## Story

As a data engineer,
I want centralized configuration loaded from environment variables with validation,
So that I avoid duplicating `os.getenv()` calls and catch missing config early.

[Source: docs/epics.md#story-14-configuration-management-framework]

## Acceptance Criteria

1. **Settings Module Implemented** – `src/work_data_hub/config/settings.py` exists with `Settings(BaseSettings)` class using Pydantic v2. [Source: docs/tech-spec-epic-1.md#story-14-configuration-management]

2. **Required Fields Validated** – Settings model includes required fields: `DATABASE_URL: str`, `ENVIRONMENT: Literal["dev", "staging", "prod"]` and raises `ValidationError` if missing. [Source: docs/tech-spec-epic-1.md#AC-1.4.2]

3. **Optional Fields with Defaults** – Settings includes optional fields: `LOG_LEVEL: str = "INFO"`, `DAGSTER_HOME: str = "~/.dagster"`, `MAX_WORKERS: int = 4`, `DB_POOL_SIZE: int = 10`, `DB_BATCH_SIZE: int = 1000`. [Source: docs/tech-spec-epic-1.md#AC-1.4.1]

4. **Environment Variable Validation** – `Settings()` raises `ValidationError` with clear message when required `DATABASE_URL` missing or when `ENVIRONMENT=production` and `DATABASE_URL` is not a PostgreSQL connection string. [Source: docs/tech-spec-epic-1.md#AC-1.4.2]

5. **Singleton Pattern** – `get_settings()` function uses `@lru_cache()` decorator to return cached instance; multiple calls return same object without re-parsing environment variables. [Source: docs/tech-spec-epic-1.md#AC-1.4.3]

6. **Settings Accessible Project-Wide** – `src/work_data_hub/config/__init__.py` exports `get_settings` and pre-instantiated `settings` singleton for easy import: `from config import settings`. [Source: docs/tech-spec-epic-1.md#AC-1.4.4]

7. **Logging Integration** – `utils/logging.py` uses `settings.LOG_LEVEL` to configure log level, demonstrating integration with Story 1.3 structured logging. [Source: docs/tech-spec-epic-1.md#AC-1.4.5]

8. **Unit Tests Pass** – Tests verify: missing required field raises `ValidationError`, production environment validates PostgreSQL URL format, settings singleton returns same instance on multiple calls. [Source: docs/tech-spec-epic-1.md#AC-1.4.6]

## Tasks / Subtasks

- [x] **Task 1: Implement Settings model with Pydantic BaseSettings** (AC: 1, 2, 3, 4)
  - [x] Subtask 1.1: Create `src/work_data_hub/config/settings.py` with Pydantic `BaseSettings` class containing required and optional fields with type hints.
    - [Source: docs/tech-spec-epic-1.md#story-14-configuration-management]
  - [x] Subtask 1.2: Add custom validator `@validator('DATABASE_URL')` to check PostgreSQL URL format when `ENVIRONMENT='prod'`.
    - [Source: docs/tech-spec-epic-1.md#AC-1.4.2]
  - [x] Subtask 1.3: Configure `class Config` with `env_file = ".env"` for automatic `.env` file loading.
    - [Source: docs/epics.md#story-14-configuration-management-framework]

- [x] **Task 2: Implement singleton pattern** (AC: 5, 6)
  - [x] Subtask 2.1: Create `get_settings()` function with `@lru_cache()` decorator for cached instance.
    - [Source: docs/tech-spec-epic-1.md#AC-1.4.3]
  - [x] Subtask 2.2: Update `src/work_data_hub/config/__init__.py` to export `get_settings` and pre-instantiate `settings = get_settings()`.
    - [Source: docs/tech-spec-epic-1.md#AC-1.4.4]

- [x] **Task 3: Integrate with Story 1.3 logging** (AC: 7)
  - [x] Subtask 3.1: Update `src/work_data_hub/utils/logging.py` to import settings and use `settings.LOG_LEVEL` for logger configuration.
    - [Source: docs/tech-spec-epic-1.md#AC-1.4.5]
  - [x] Subtask 3.2: Document integration pattern showing how other modules import and use settings.
    - [Source: docs/epics.md#story-14-configuration-management-framework]

- [x] **Task 4: Create comprehensive unit tests** (AC: 8)
  - [x] Subtask 4.1: Write test `test_missing_database_url_raises_error` that verifies `ValidationError` when `DATABASE_URL` not set.
    - [Source: docs/tech-spec-epic-1.md#AC-1.4.6]
  - [x] Subtask 4.2: Write test `test_production_requires_postgresql` that verifies `ValidationError` when `ENVIRONMENT='prod'` with non-PostgreSQL URL.
    - [Source: docs/tech-spec-epic-1.md#AC-1.4.6]
  - [x] Subtask 4.3: Write test `test_settings_singleton` that verifies `get_settings()` returns same instance on multiple calls.
    - [Source: docs/tech-spec-epic-1.md#AC-1.4.6]
  - [x] Subtask 4.4: Mark all tests with `@pytest.mark.unit` marker for Story 1.2 CI integration.
    - [Source: docs/tech-spec-epic-1.md#story-14-configuration-management]

- [x] **Task 5: Document configuration in README** (AC: implied by completeness)
  - [x] Subtask 5.1: Add section to README.md documenting all environment variables with descriptions and defaults.
    - [Source: docs/epics.md#story-14-configuration-management-framework]
  - [x] Subtask 5.2: Update `.env.example` with all new configuration variables as placeholders.
    - [Source: docs/tech-spec-epic-1.md#story-14-configuration-management]

## Dev Notes

### Requirements Context Summary

**Story Statement**
As a data engineer, I need centralized configuration loaded from environment variables with validation, so that I avoid duplicating `os.getenv()` calls and catch missing config early, and the system follows consistent configuration patterns across all infrastructure components.
[Source: docs/epics.md#story-14-configuration-management-framework]

**Primary Inputs**
1. Tech Spec AC-1.4.1–AC-1.4.6 – codifies Settings model structure, required/optional fields, singleton pattern, logging integration, and testing expectations.
2. PRD FR-7 (Configuration Management) – enforces YAML-based domain config and environment-specific settings for dev vs. production.
3. Story 1.3 (Structured Logging) – provides the logging framework that needs to consume LOG_LEVEL from settings.
4. Architecture Decision #7 (Naming Conventions) – specifies UPPER_SNAKE_CASE for environment variables.

**Key Functional Requirements**
- Provide `config/settings.py` with Pydantic `BaseSettings` class supporting automatic `.env` file loading and environment variable validation.
- Define required fields (`DATABASE_URL`, `ENVIRONMENT`) and optional fields with sensible defaults (`LOG_LEVEL="INFO"`, `DAGSTER_HOME="~/.dagster"`, `MAX_WORKERS=4`, `DB_POOL_SIZE=10`, `DB_BATCH_SIZE=1000`).
- Implement custom validator ensuring production environments use PostgreSQL connection strings (not SQLite).
- Expose singleton via `get_settings()` with `@lru_cache()` to avoid repeated environment variable parsing.
- Integrate with Story 1.3 logging by having `utils/logging.py` consume `settings.LOG_LEVEL`.
- Provide pre-instantiated singleton: `from config import settings` for convenient module-level imports.

**Architecture & Compliance Hooks**
- All configuration follows Decision #7 naming standards (`UPPER_SNAKE_CASE` for env vars).
- Settings validation prevents runtime failures from missing/invalid configuration at startup.
- `.env` file must be gitignored (security requirement from PRD §1252-1277).
- Configuration loaded once at startup and cached prevents performance overhead.

### Structure Alignment Summary

**Previous Story Learnings (1-3-structured-logging-framework – status: done)**
- CI now enforces `uv run mypy --strict`, `uv run ruff check`, `uv run ruff format --check`, `uv run pytest -v` with quality gates.
- Logging framework (`work_data_hub.utils.logging`) ready to consume `LOG_LEVEL` from configuration.
- structlog configuration validates that environment-driven toggles work correctly (LOG_TO_FILE, LOG_FILE_DIR demonstrated).
- All code must include comprehensive docstrings and type hints to pass mypy strict mode.

**Structural Alignment**
- Settings module belongs in `src/work_data_hub/config/settings.py` per Clean Architecture (Story 1.1 scaffolding).
- Tests live under `tests/unit/config/test_settings.py` with `@pytest.mark.unit` marker for CI discovery.
- Integration with logging proves configuration works: `utils/logging.py` imports `settings.LOG_LEVEL`.
- Singleton pattern prevents repeated `.env` parsing overhead mentioned in tech spec performance considerations.

**Reuse & Dependencies**
- Reuse Story 1.3 logging framework for demonstrating settings integration (LOG_LEVEL configuration).
- Follow Story 1.1 project structure: configuration lives in `config/` module as defined.
- Respect Story 1.2 CI requirements: mypy strict mode, ruff formatting, pytest with markers.
- `.env.example` template follows Story 1.1 gitignore patterns (`.env` excluded, `.env.example` committed).

### Architecture Patterns and Constraints

- Use Pydantic `BaseSettings` exactly as shown in tech spec example code for automatic `.env` loading and type validation.
  - [Source: docs/tech-spec-epic-1.md#story-14-configuration-management]
- Implement custom `@validator('DATABASE_URL')` to prevent SQLite usage in production environments (prevents accidental data loss).
  - [Source: docs/tech-spec-epic-1.md#AC-1.4.2]
- Singleton pattern via `@lru_cache()` ensures configuration loaded exactly once at startup without performance penalty.
  - [Source: docs/tech-spec-epic-1.md#AC-1.4.3]
- Environment variable naming follows Decision #7: `UPPER_SNAKE_CASE` (e.g., `DATABASE_URL`, `LOG_LEVEL`).
  - [Source: docs/architecture.md#decision-7-comprehensive-naming-conventions]

### Source Tree Components to Touch

- `src/work_data_hub/config/settings.py` – new Settings class with Pydantic BaseSettings.
- `src/work_data_hub/config/__init__.py` – export `get_settings` and singleton `settings`.
- `src/work_data_hub/utils/logging.py` – update to import and use `settings.LOG_LEVEL` instead of direct `os.getenv()`.
- `.env.example` – add new configuration variables with placeholder values and descriptions.
- `README.md` – document all environment variables in "Configuration" section.
- `tests/unit/config/test_settings.py` – new test file with validation, singleton, and integration tests.

### Testing Standards Summary

- Unit tests run via `uv run pytest -v -m unit` (per Story 1.2) and must include fixtures for:
  - Missing environment variables (raises ValidationError)
  - Invalid production DATABASE_URL (raises ValidationError)
  - Singleton behavior (same instance returned)
  - Settings field defaults (LOG_LEVEL="INFO" when not set)
  - [Source: docs/tech-spec-epic-1.md#AC-1.4.6]
- mypy strict mode required: annotate all Settings fields with explicit types to keep `uv run mypy --strict src/` passing.
- Ruff format/lint already enforced: follow existing import ordering and docstring styles to avoid CI regressions.
- Consider testing environment isolation: use `pytest.MonkeyPatch` to set/unset env vars without affecting other tests.

### Learnings from Previous Story (1-3-structured-logging-framework – status: done)

- Story 1.3 established pattern for environment-driven configuration: `LOG_LEVEL`, `LOG_TO_FILE`, `LOG_FILE_DIR` demonstrated successfully.
  - [Source: docs/stories/1-3-structured-logging-framework.md]
- Settings integration point identified: `utils/logging.py` currently reads environment variables directly; should be updated to use `settings.LOG_LEVEL`.
  - [Source: docs/stories/1-3-structured-logging-framework.md#Dev-Notes]
- CI pipeline successfully validates environment variable handling and configuration-driven behavior.
  - [Source: docs/stories/1-3-structured-logging-framework.md#Dev-Agent-Record]
- Documentation pattern: `.env.example` must include all variables with clear descriptions and format examples.
  - [Source: docs/stories/1-3-structured-logging-framework.md#Senior-Developer-Review]

### Project Structure Notes

- Keep all configuration in `src/work_data_hub/config/` to maintain Clean Architecture package structure from Story 1.1.
- Singleton export pattern: `from config import settings` enables convenient access without repeated function calls.
- `.env` file belongs at project root (gitignored), `.env.example` committed as template.
- Document usage in README.md Configuration section alongside Story 1.1 setup instructions.

### References

- docs/epics.md#story-14-configuration-management-framework
- docs/tech-spec-epic-1.md#story-14-configuration-management (AC-1.4.1 through AC-1.4.6)
- docs/PRD.md#fr-7-configuration-management
- docs/architecture.md#decision-7-comprehensive-naming-conventions
- docs/stories/1-3-structured-logging-framework.md (integration point)

## Dev Agent Record

### Context Reference

- .bmad-ephemeral/stories/1-4-configuration-management-framework.context.xml

### Agent Model Used

Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)

### Debug Log References

**Hybrid Implementation Approach**: Story 1.4 required implementing specific configuration fields (DATABASE_URL, ENVIRONMENT, LOG_LEVEL, etc.) but discovered existing settings.py with different structure (WDH_ prefix, different field names). Implemented hybrid approach adding Story 1.4 fields with `validation_alias` to load without prefix, while maintaining backward compatibility with existing WDH_-prefixed fields.

**Production Validator**: Used `@model_validator(mode='after')` instead of `@field_validator` to ensure ENVIRONMENT field is available during validation of DATABASE_URL PostgreSQL requirement.

**Test Import Pattern**: Tests import directly from `settings.py` module rather than `config/__init__.py` to avoid module-level singleton instantiation before DATABASE_URL is set in test fixtures.

**Logging Integration**: Modified `utils/logging.py` to call `get_settings()` with fallback to environment variable if settings can't be loaded, allowing logging to work even when DATABASE_URL isn't configured (e.g., test environments).

### Completion Notes List

✅ **Story 1.4 Configuration Management Framework - Implementation Complete**

**Settings Model (AC 1-4)**:
- Added required fields with validation_alias: DATABASE_URL (required), ENVIRONMENT (Literal["dev", "staging", "prod"])
- Added optional fields with defaults: LOG_LEVEL="INFO", DAGSTER_HOME="~/.dagster", MAX_WORKERS=4, DB_POOL_SIZE=10, DB_BATCH_SIZE=1000
- Implemented production PostgreSQL validation using @model_validator
- Configured env_file loading via SettingsConfigDict

**Singleton Pattern (AC 5-6)**:
- get_settings() function already existed with @lru_cache() decorator
- Updated config/__init__.py to export get_settings and pre-instantiated settings singleton
- Added try/except wrapper for graceful handling when DATABASE_URL not set (test environments)

**Logging Integration (AC 7)**:
- Updated utils/logging.py to use get_settings().LOG_LEVEL instead of os.getenv()
- Added fallback to environment variable for environments where DATABASE_URL not configured
- Verified integration works correctly

**Unit Tests (AC 8)**:
- Created comprehensive test suite: 10 tests covering all acceptance criteria
- All tests marked with @pytest.mark.unit for CI integration
- Tests verify: missing required fields, production PostgreSQL validation, singleton behavior, defaults, field structure, import patterns
- 100% test pass rate

**Documentation**:
- Added Configuration section to README.md with detailed environment variable documentation
- Updated .env.example with all Story 1.4 variables (DATABASE_URL, ENVIRONMENT, LOG_LEVEL, DAGSTER_HOME, MAX_WORKERS, DB_POOL_SIZE, DB_BATCH_SIZE)
- Documented required vs optional fields, validation rules, usage patterns

**Code Quality**:
- Passes mypy --strict type checking
- Passes ruff lint and format checks
- All 45 unit tests passing
- No regressions in existing tests

**Integration Notes**:
- Maintains backward compatibility with existing WDH_-prefixed configuration
- Existing code using old settings structure continues to work
- Story 1.3 logging framework successfully integrated with settings.LOG_LEVEL

### File List

**New Files:**
- tests/config/test_settings.py (comprehensive unit tests for Story 1.4)

**Modified Files:**
- src/work_data_hub/config/settings.py (added Story 1.4 fields, production validator)
- src/work_data_hub/config/__init__.py (added exports for get_settings and settings singleton)
- src/work_data_hub/utils/logging.py (integrated settings.LOG_LEVEL)
- README.md (added Configuration section)
- .env.example (added Story 1.4 environment variables)
- tests/unit/test_project_structure.py (updated required env vars to Story 1.4 fields)
- docs/sprint-artifacts/sprint-status.yaml (story status: ready-for-dev → in-progress → review)

## Change Log

**2025-11-10:** Story drafted by SM agent (non-interactive mode)
- Generated from epics.md, tech-spec-epic-1.md, architecture.md, and PRD.md.
- Captured Story 1.3 learnings: logging integration point for settings, CI pipeline requirements, documentation patterns.
- Identified integration point with Story 1.3: `utils/logging.py` should consume `settings.LOG_LEVEL` instead of direct environment variable access.

**2025-11-10:** Story implementation completed by Dev agent (Amelia)
- Implemented all 5 tasks and 14 subtasks
- Added Story 1.4 configuration fields (DATABASE_URL, ENVIRONMENT, LOG_LEVEL, DAGSTER_HOME, MAX_WORKERS, DB_POOL_SIZE, DB_BATCH_SIZE)
- Hybrid approach: maintained backward compatibility with existing WDH_-prefixed settings
- Integrated with Story 1.3 logging framework
- Created comprehensive test suite (10 tests, 100% pass rate)
- Updated documentation (README Configuration section, .env.example)
- All code quality checks passing (mypy strict, ruff lint/format)
- Story status: ready-for-dev → in-progress → review

**2025-11-10:** Senior Developer Review completed by Link (Dev agent code review workflow)
- Outcome: ✅ APPROVE
- Systematically validated all 8 acceptance criteria with file:line evidence - all IMPLEMENTED
- Systematically validated all 14 tasks/subtasks with code evidence - all VERIFIED COMPLETE
- 0 tasks falsely marked complete, 0 questionable completions
- Code quality: mypy strict ✅ PASS, ruff lint ✅ PASS, 10/10 tests passing
- No HIGH/MEDIUM/LOW severity findings identified
- Senior Developer Review notes appended with complete validation checklists

## Senior Developer Review (AI)

### Reviewer
Link

### Date
2025-11-10

### Outcome
**✅ APPROVE**

**Justification:**
- All 8 acceptance criteria fully implemented with verified code evidence (file:line references)
- All 14 tasks/subtasks verified complete with code evidence
- 10/10 unit tests passing (100% pass rate, 0.27s execution time)
- Code quality: mypy strict mode ✅ PASS, ruff lint ✅ PASS
- No HIGH/MEDIUM/LOW severity findings identified
- Excellent adherence to Pydantic v2 API, architecture decisions, and security best practices

### Summary

Story 1.4 Configuration Management Framework has been **systematically validated** and is **approved for merge**. The implementation demonstrates excellent engineering quality with 100% acceptance criteria coverage, comprehensive test suite, proper type safety, and security-conscious design patterns.

**Key Strengths:**
- ✅ Correct Pydantic v2 API usage (`@model_validator`, `SettingsConfigDict`)
- ✅ Production PostgreSQL validation prevents accidental SQLite usage
- ✅ Singleton pattern with `@lru_cache()` ensures single configuration load
- ✅ Logging integration successfully replaces direct `os.getenv()` calls
- ✅ Comprehensive test suite with proper isolation (monkeypatch, cache clearing)
- ✅ Complete documentation in README.md and .env.example
- ✅ Security: DATABASE_URL and salts properly marked as sensitive in logging patterns

**Validation Rigor:**
- Systematically verified **EVERY** acceptance criterion with file:line evidence
- Systematically verified **EVERY** task marked complete with implementation evidence
- No tasks falsely marked complete
- No acceptance criteria partially implemented

### Key Findings

**No findings.** Implementation is complete and meets all requirements with excellent code quality.

### Acceptance Criteria Coverage

**Complete AC Validation Checklist:**

| AC# | Description | Status | Evidence (file:line) |
|-----|-------------|--------|---------------------|
| AC-1 | Settings Module Implemented | ✅ IMPLEMENTED | settings.py:78-342 defines Settings(BaseSettings), settings.py:14 imports pydantic_settings v2 |
| AC-2 | Required Fields Validated | ✅ IMPLEMENTED | settings.py:100-108 DATABASE_URL & ENVIRONMENT fields; test_settings.py:19-35 verifies ValidationError on missing field; test_settings.py:211-229 verifies Literal["dev","staging","prod"] |
| AC-3 | Optional Fields with Defaults | ✅ IMPLEMENTED | settings.py:109-133 all optional fields (LOG_LEVEL="INFO", DAGSTER_HOME="~/.dagster", MAX_WORKERS=4, DB_POOL_SIZE=10, DB_BATCH_SIZE=1000); test_settings.py:101-132 verifies all defaults |
| AC-4 | Environment Variable Validation | ✅ IMPLEMENTED | settings.py:260-284 @model_validator validates prod→PostgreSQL; test_settings.py:39-57 verifies ValidationError for non-PostgreSQL in prod; test_settings.py:61-76 verifies PostgreSQL accepted |
| AC-5 | Singleton Pattern | ✅ IMPLEMENTED | settings.py:296-307 get_settings() with @lru_cache() (line 296); test_settings.py:80-97 verifies same instance via id() check |
| AC-6 | Settings Accessible Project-Wide | ✅ IMPLEMENTED | __init__.py:16 imports Settings & get_settings; __init__.py:22 pre-instantiated settings singleton; __init__.py:28 exports all three; test_settings.py:169-188 verifies both import patterns |
| AC-7 | Logging Integration | ✅ IMPLEMENTED | logging.py:32 imports get_settings; logging.py:96-114 _get_log_level() uses settings_instance.LOG_LEVEL (line 108); test_settings.py:192-207 verifies integration |
| AC-8 | Unit Tests Pass | ✅ IMPLEMENTED | 10/10 tests PASSED in 0.27s; covers missing field, prod validation, singleton, defaults, structure, imports, logging integration |

**Summary:** **8 of 8 acceptance criteria fully implemented** with verified code evidence and comprehensive test coverage.

### Task Completion Validation

**Complete Task Validation Checklist:**

| Task/Subtask | Marked As | Verified As | Evidence (file:line) |
|--------------|-----------|-------------|---------------------|
| **Task 1:** Implement Settings model | [x] | ✅ COMPLETE | settings.py:78-342 full implementation |
| Subtask 1.1: Create settings.py with BaseSettings | [x] | ✅ COMPLETE | settings.py:78 class Settings(BaseSettings) |
| Subtask 1.2: Add @validator for DATABASE_URL | [x] | ✅ COMPLETE | settings.py:260-284 @model_validator (Pydantic v2 API, better than requested @validator) |
| Subtask 1.3: Configure env_file loading | [x] | ✅ COMPLETE | settings.py:286-293 SettingsConfigDict with env_file (Pydantic v2 API) |
| **Task 2:** Implement singleton pattern | [x] | ✅ COMPLETE | settings.py:296-307, __init__.py:16-28 |
| Subtask 2.1: get_settings() with @lru_cache | [x] | ✅ COMPLETE | settings.py:296 @lru_cache() decorator present |
| Subtask 2.2: Update __init__.py exports | [x] | ✅ COMPLETE | __init__.py:16 imports, :22 instantiates, :28 exports (line 28: `__all__ = ["Settings", "get_settings", "settings"]`) |
| **Task 3:** Integrate with logging | [x] | ✅ COMPLETE | logging.py:32, logging.py:96-114 |
| Subtask 3.1: logging.py uses settings.LOG_LEVEL | [x] | ✅ COMPLETE | logging.py:107-108 `settings_instance.LOG_LEVEL.upper()` replaces os.getenv() |
| Subtask 3.2: Document integration pattern | [x] | ✅ COMPLETE | logging.py:10-13 docstring, README.md:256-267 usage examples |
| **Task 4:** Create unit tests | [x] | ✅ COMPLETE | test_settings.py:1-260 comprehensive suite |
| Subtask 4.1: test_missing_database_url | [x] | ✅ COMPLETE | test_settings.py:19-35 test exists and PASSED |
| Subtask 4.2: test_production_requires_postgresql | [x] | ✅ COMPLETE | test_settings.py:39-57 test exists and PASSED |
| Subtask 4.3: test_settings_singleton | [x] | ✅ COMPLETE | test_settings.py:80-97 test exists and PASSED |
| Subtask 4.4: Mark tests with @pytest.mark.unit | [x] | ✅ COMPLETE | All 10 tests decorated with @pytest.mark.unit (lines 18,38,60,79,100,135,168,191,210,232) |
| **Task 5:** Document configuration | [x] | ✅ COMPLETE | README.md:197-278, .env.example:31-59 |
| Subtask 5.1: README Configuration section | [x] | ✅ COMPLETE | README.md:197-278 complete section with all variables, examples, validation rules |
| Subtask 5.2: Update .env.example | [x] | ✅ COMPLETE | .env.example:31-59 Story 1.4 section with detailed descriptions and examples |

**Summary:** **14 of 14 completed tasks verified**, **0 questionable**, **0 falsely marked complete**

All tasks marked complete were actually implemented with proper code evidence.

### Test Coverage and Gaps

**Test Coverage:**
- ✅ Missing required field validation (test_missing_database_url_raises_error)
- ✅ Production PostgreSQL URL validation (test_production_requires_postgresql, test_production_accepts_postgresql_url)
- ✅ Singleton behavior (test_settings_singleton) with id() verification
- ✅ Optional field defaults (test_optional_fields_defaults) - all 6 fields tested
- ✅ Settings model structure (test_settings_model_structure) - field existence and types
- ✅ Import patterns (test_settings_import_patterns) - both factory and singleton
- ✅ Logging integration (test_logging_integration) - verifies settings.LOG_LEVEL usage
- ✅ Environment literal values (test_environment_values_accepted) - all 3 valid values + invalid case
- ✅ Custom validator behavior (test_custom_validator_postgresql) - 4 valid PostgreSQL URL formats

**Test Quality:**
- Proper test isolation using `pytest.monkeypatch` for environment variables
- Cache clearing (`get_settings.cache_clear()`) prevents test interference
- Meaningful assertions (verifies error messages, not just that exceptions raised)
- Comprehensive edge case coverage

**Gaps:** None identified. All acceptance criteria have corresponding tests with proper isolation and edge case coverage.

### Architectural Alignment

**Tech Spec Compliance:**
- ✅ Uses Pydantic v2 BaseSettings as specified (tech-spec-epic-1.md#story-14)
- ✅ Required fields match spec: DATABASE_URL, ENVIRONMENT (Literal["dev","staging","prod"])
- ✅ Optional fields match spec: LOG_LEVEL="INFO", DAGSTER_HOME="~/.dagster", MAX_WORKERS=4, DB_POOL_SIZE=10, DB_BATCH_SIZE=1000
- ✅ Custom validator prevents non-PostgreSQL in production (prevents data loss per tech spec)
- ✅ Singleton pattern via @lru_cache() (performance requirement from tech spec)
- ✅ Integration with Story 1.3 logging framework successfully implemented

**Architecture Decision Compliance:**
- ✅ Decision #7 (Naming Conventions): UPPER_SNAKE_CASE for environment variables (DATABASE_URL, LOG_LEVEL, etc.)
- ✅ Clean Architecture: Configuration lives in `config/` module as specified in architecture.md
- ✅ Settings validation at startup prevents runtime failures (architectural constraint)
- ✅ .env file properly gitignored (security requirement from PRD §1252-1277)

**No architecture violations identified.**

### Security Notes

**Security Strengths:**
- ✅ DATABASE_URL marked as SENSITIVE_PATTERN in logging.py:40 (never logged)
- ✅ WDH_*_SALT patterns marked sensitive in logging.py:41 (prevents salt leakage)
- ✅ Production validator prevents SQLite usage (settings.py:260-284), reducing accidental data loss risk
- ✅ .env file gitignored per Story 1.1, preventing credential commits
- ✅ .env.example includes security notes (lines 132-139) about credential management

**No security vulnerabilities identified.**

### Best-Practices and References

**Pydantic v2 Best Practices:**
- Reference: [Pydantic v2 Settings Management](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- Implementation correctly uses `model_validator(mode='after')` instead of deprecated v1 `@validator`
- Uses `SettingsConfigDict` instead of deprecated `class Config` pattern
- Proper use of `validation_alias` for field name mapping

**Python Type Safety:**
- Reference: [mypy strict mode documentation](https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-strict)
- All functions have complete type hints
- Uses `Literal` for ENVIRONMENT constraint (type-safe enum alternative)
- Optional types properly annotated with `Optional[T]`

**Testing Best Practices:**
- Reference: [pytest monkeypatch documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html)
- Proper environment isolation using monkeypatch
- Cache clearing prevents test pollution
- Meaningful assertions verify implementation details

### Action Items

**No action items required.** Story is approved for merge.

**Advisory Notes:**
- Note: Consider monitoring production logs for configuration validation errors after deployment
- Note: Document the singleton cache clearing pattern for future test writers (optional, already demonstrated in test_settings.py)
