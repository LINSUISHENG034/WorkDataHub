# Domain Migration Guides

This directory contains all documentation related to migrating legacy domains to the WorkDataHub architecture.

## Quick Start

**New to domain migration?** Start with the [Workflow Guide](./workflow.md).

### 🚀 5-Minute Quick Overview

```bash
# Step 1: Analyze dependencies (1-2 days)
grep -r "SELECT.*FROM\|MAPPING" legacy/annuity_hub/data_handler/data_cleaner.py
# Document dependencies in cleansing-rules/{domain}.md (Sections 2-4)

# Step 2: Migrate dependencies (hours)
PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py

# Step 3: Document cleansing rules (1-2 days)
# Complete all 10 sections of cleansing-rules/{domain}.md
# Reference: docs/templates/cleansing-rules-template.md

# Step 4: Implement domain (2-3 days)
# Create 6 files: models.py, schemas.py, service.py, etc.
# Use: docs/guides/domain-migration/development-guide.md

# Step 5: Validate parity (1-2 days)
# Compare new implementation with legacy output
# Target: 100% match
```

**Example in Action:** See how `annuity_income` was migrated:
- Documentation: [annuity-income.md](../../cleansing-rules/annuity-income.md)
- Code: `src/work_data_hub/domain/annuity_income/`

## Documents

| Document | Purpose | When to Use |
|----------|---------|-------------|
| [Workflow](./workflow.md) | End-to-end migration process | **Start here** - Follow phases 1-4 |
| [Development Guide](./development-guide.md) | Implementation patterns and code templates | Phase 3 - Writing domain code |
| [Code Mapping](./code-mapping.md) | Document → Code translation | Phase 3 - Converting docs to code |
| [Troubleshooting](./troubleshooting.md) | Common issues and solutions | When you encounter problems |

## Migration Phases

```
Phase 1: Dependency Preparation
    └─► Phase 2: Documentation
        └─► Phase 3: Implementation
            └─► Phase 4: Validation
```

## Related Resources

| Resource | Location |
|----------|----------|
| Cleansing Rules Template | [templates/cleansing-rules-template.md](../../templates/cleansing-rules-template.md) |
| Example: annuity-income | [cleansing-rules/annuity-income.md](../../cleansing-rules/annuity-income.md) |
| Parity Validation Guide | [runbooks/legacy-parity-validation.md](../../runbooks/legacy-parity-validation.md) |
