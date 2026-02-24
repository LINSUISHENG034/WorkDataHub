# References

**Research Documents:**
- `docs/initial/research-deep-prompt*.md` - Original Research Prompt for AI Platforms

**Architecture & Patterns Documentation:**
- `docs/architecture-patterns/` - Pipeline integration guide, tiered retry, error message quality
- `docs/guides/infrastructure/` - Company enrichment, DB connection, EQC token, schemas deep-dive, transforms
- `docs/guides/domain-migration/` - Code mapping, development guide, workflow, troubleshooting

**Business Context:**
- `docs/business-background/` - Annuity plan types, customer MDM backfill analysis, 战客身份定义
- `docs/cleansing-rules/` - Annuity income, annuity performance cleansing rules

**Development Standards:**
- `docs/context-engineering/` - Core dev philosophy, debugging tools, dev environment, error handling, git workflow, monitoring, performance, security, style, testing

**Operational Guides:**
- `docs/runbooks/` - Annuity performance, intranet migration verification, legacy parity validation
- `docs/guides/troubleshooting/` - Troubleshooting guides
- `docs/database-migrations.md` - Database migration guide
- `docs/database-schema-panorama.md` - Full database schema overview

**Planning Artifacts:**
- `_bmad-output/planning-artifacts/architecture/` - Full architecture documentation (12 files)
- `_bmad-output/planning-artifacts/epics/` - Epic 1-6 + Epic 5.5
- `_bmad-output/planning-artifacts/plans/` - Implementation plans (CLI, customer MDM, etc.)

**Existing Codebase:**
- `src/work_data_hub/` - 8 business domains, infrastructure layer, CLI, GUI, orchestration
- `legacy/annuity_hub/` - Original monolithic implementation (quarantined, import ban enforced)

**Configuration:**
- `config/data_sources.yml` - Domain file discovery patterns (schema v1.2)
- `config/mappings/` - Business mapping YAML files
- `config/seeds/` - Seed data (CSV + dump files)

---
