# INITIAL.md Template — Definition of Ready (DoR) for PRP

This template helps you write a high‑signal INITIAL.md so an AI coding assistant can generate a strong PRP and implement it successfully in one pass with validation.

Fill all sections concisely and concretely. Prefer runnable commands, exact file paths, precise URLs/sections, and code snippets over prose.

---

## FEATURE
One‑sentence statement of the problem and the desired outcome.

## SCOPE
- In‑scope: What this change must deliver (bullets)
- Non‑goals: What is explicitly out of scope (bullets)

## CONTEXT SNAPSHOT (optional)
Provide a minimal repo snapshot or pointers to the relevant area.

```bash
# Example
src/project/
  feature_x/
    handlers.py
    validators.py
    tests/
      test_handlers.py
```

## EXAMPLES (most important)
List files/snippets to mirror. For each, explain the pattern to follow or adapt.

- Path: `src/.../similar_feature.py` — pattern to reuse (error handling, logging)
- Path: `tests/.../test_similar_feature.py` — test style & fixtures to mirror
- Snippet:
```python
# paste a short snippet showing the pattern to copy
```

## DOCUMENTATION
External docs (exact URLs + sections) and internal standards required for implementation.

- URL: <https://docs.example.com/sdk#init> — initialization & auth
- URL: <https://docs.example.com/api#errors> — known error codes
- File: `docs/api-guidelines.md` — response format & error mapping

## INTEGRATION POINTS
Describe all points this feature touches.

- Data models: new/updated Pydantic/ORM models (fields, types, constraints)
- Database: migrations (SQL/DDL), indexes; link scripts or include statements
- Config/ENV: new keys in `.env`, defaults, secrets handling
- API/Routes: new/changed endpoints, status codes, payloads
- Jobs/Events: background tasks, schedules, event contracts

## DATA CONTRACTS (schemas & payloads)
Define or link exact schemas. Include sample payloads where useful.

```python
# Example Pydantic models (v2)
from pydantic import BaseModel, Field

class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    price_cents: int = Field(ge=0)

class Item(BaseModel):
    item_id: int
    name: str
    price_cents: int
```

```json
// Example request
{
  "name": "Pro Plan",
  "price_cents": 9900
}
```

## GOTCHAS & LIBRARY QUIRKS
Call out traps (versions, timeouts, rate limits, ORM or API constraints). Be specific.

- Pydantic v2 only; do not use v1 `orm_mode`
- Use `rg` (ripgrep) for search, not `grep/find`
- SQLAlchemy JSON + Decimal requires pre‑encoding to str
- External API returns 429 >10 req/sec; backoff required

## IMPLEMENTATION NOTES
Anchor implementation to existing patterns in this repo.

- Follow error handling/logging pattern in: `src/.../utils/errors.py`
- Mirror response format from: `src/.../utils/responses.py`
- Keep functions <50 lines; prefer vertical slice structure
- Ask for clarification when requirements are ambiguous; do not guess

## VALIDATION GATES (must pass)
Commands the assistant must run and make green before marking complete.

```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v
```

Optional:
```bash
uv run pytest --cov=src --cov-report=term-missing
```

## ACCEPTANCE CRITERIA
Make success measurable and testable.

- [ ] Happy paths covered by tests (list)
- [ ] Edge/error cases covered (list)
- [ ] API contract matches docs (status codes, fields)
- [ ] No regressions in adjacent features (list)

## ROLLOUT & RISK
- Feature flags/kill switches (if any)
- Migration/backfill steps and rollback strategy
- Performance or quota considerations

## APPENDICES (optional snippets)

```python
# Test skeleton example
import pytest

@pytest.mark.asyncio
async def test_feature_happy_path(dep_fixture):
    # Arrange
    # Act
    # Assert
    assert True
```

```bash
# Useful search commands (ripgrep)
rg "def target_function" src/
rg --files -g "*.py" | rg validators
```

