# INITIAL.md — C-026: Annuity Performance (规模明细) — Generate Postgres DDL from JSON

This INITIAL defines a generator to produce a faithful Postgres DDL for the real Chinese table/columns of “规模明细” from `reference/db_migration/db_structure.json` (lines 1444–1715), including indexes and foreign keys.

---

## FEATURE
Generate Postgres DDL from the JSON spec for 规模明细 and save it to `scripts/dev/annuity_performance_real.sql` using quoted Chinese identifiers.

## SCOPE
- In-scope:
  - Add a one-off generator script: `scripts/dev/gen_postgres_ddl_from_json.py`
  - Input: `reference/db_migration/db_structure.json` (lines 1444–1715 for 规模明细)
  - Output: `scripts/dev/annuity_performance_real.sql`
  - Type mapping: MySQL→Postgres (see below), quoting Chinese identifiers, and producing PK/INDEX/FK
  - Allow staged FK application (if referenced tables are missing)
- Non-goals:
  - Pipeline integration (plan-only/execute)
  - End-to-end tests (covered later)

## CONTEXT SNAPSHOT
```bash
reference/db_migration/db_structure.json   # source of truth
scripts/dev/
  gen_postgres_ddl_from_json.py            # new
  annuity_performance_real.sql             # generated output
```

## EXAMPLES
- Snippet (pseudocode):
```python
import json, re
src = json.load(open('reference/db_migration/db_structure.json', 'r', encoding='utf-8'))
table = src["business"]["规模明细"]  # adjust per actual tree
# emit CREATE TABLE with quoted identifiers
# map types, then indexes, then FKs; order carefully or split into phases
```

## DOCUMENTATION
- File: `PRPs/templates/INITIAL.template.md` — DoR template
- File: `README.md` — instructions to apply DDL locally and optional staged FK application

## INTEGRATION POINTS
- Generator script in `scripts/dev/`
- Output DDL in `scripts/dev/annuity_performance_real.sql`

## DATA CONTRACTS
- Chinese table and column names preserved exactly as in JSON (quoted in Postgres)
- Type mapping guidelines:
  - `VARCHAR(n)`, `TEXT` → same (drop MySQL COLLATE)
  - `DATE`, `DATETIME` → `DATE`, `TIMESTAMP`
  - `DOUBLE` → `double precision` (or `numeric(p,s)` if JSON specifies precision)
  - `TINYINT` → `boolean` (if semantic flag) else `smallint`
  - Index/Unique/Foreign Keys → emit as per JSON; FKs may be staged

## GOTCHAS & LIBRARY QUIRKS
- Ensure UTF‑8 and quoted identifiers: "表名"."列名"
- FK order may require staging; provide separate sections or a flag to include/exclude FKs
- Windows shell quoting differences; provide both `psql` and `apply_sql.py` examples

## IMPLEMENTATION NOTES
- Keep generator small and deterministic; include comments in the output DDL for provenance
- Provide an option (flag) to skip FKs when applying locally

## VALIDATION GATES
```bash
uv run ruff check src/ --fix
uv run mypy src/

# Generate and preview
uv run python scripts/dev/gen_postgres_ddl_from_json.py --table 规模明细 --json reference/db_migration/db_structure.json --out scripts/dev/annuity_performance_real.sql --include-fk

# Apply locally (either tool)
uv run python -m scripts.create_table.apply_sql --sql scripts/dev/annuity_performance_real.sql --dry-run
uv run python -m scripts.create_table.apply_sql --sql scripts/dev/annuity_performance_real.sql
```

## ACCEPTANCE CRITERIA
- [ ] `scripts/dev/gen_postgres_ddl_from_json.py` exists and produces `scripts/dev/annuity_performance_real.sql`
- [ ] Generated DDL preserves Chinese identifiers and includes PK/INDEX/FK per JSON
- [ ] DDL applies locally (FKs may be staged if referenced tables are missing)
- [ ] README documents how to apply DDL

## ROLLOUT & RISK
- No pipeline/CI impact; local-only DDL generation and application
- Risk: Type mapping mismatches → log and keep mappings minimal, iterate in next stages

## APPENDICES
```bash
# Example invocation
uv run python scripts/dev/gen_postgres_ddl_from_json.py \
  --table 规模明细 \
  --json reference/db_migration/db_structure.json \
  --out scripts/dev/annuity_performance_real.sql \
  --include-fk
```

