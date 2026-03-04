# Domain Migration Guides

This directory contains all documentation related to migrating legacy domains to the WorkDataHub architecture.

> [!IMPORTANT]
> **v2.0 架构更新**: 从 2026-01-14 起，domain 实现需要包含 `adapter.py` 文件实现 `DomainServiceProtocol`。详见 [Development Guide](./development-guide.md)。

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
# Create 8 files: __init__.py, adapter.py, constants.py, models.py, schemas.py, helpers.py, service.py, pipeline_builder.py
# Use: docs/guides/domain-migration/development-guide.md

# Step 5: Register Protocol adapter
# Edit domain/registry.py to register your {Domain}Service (5 domains currently registered)

# Step 6: Validate mappings (critical!)
# Verify all mappings from legacy are present and correctly handled
# Reference: docs/guides/domain-migration/mapping-validation-best-practices.md

# Step 7: Validate parity (1-2 days)
# Compare new implementation with legacy output
PYTHONPATH=src uv run python scripts/validation/CLI/cleaner_compare.py {domain} --month {YYYYMM} --export
# Target: 100% match
```

**Example in Action:** See how `annuity_income` was migrated:
- Documentation: [annuity-income.md](../../cleansing-rules/annuity-income.md)
- Code: `src/work_data_hub/domain/annuity_income/`

## Documents

### Phase 1: Initial Preparation
| Document | Purpose | When to Use |
|----------|---------|-------------|
| [Workflow](./workflow.md) | End-to-end migration process | **Start here** - Follow phases 1-4 |
| [Plan Code Migration](./initial-preparation/plan-code-migration.md) | Plan code mapping migration to enrichment_index | When migrating plan code mappings from Legacy |

### Phase 2-4: Migration Process
| Document | Purpose | When to Use |
|----------|---------|-------------|
| [Development Guide](./development-guide.md) | Implementation patterns and code templates | Phase 3 - Writing domain code |
| [Foreign Key Backfill (section)](./development-guide.md#foreign-key-backfill-configuration-configdatasourcesyml) | FK 配置示例、依赖约束、最佳实践 | When adding/updating `foreign_keys` 配置 |
| [Code Mapping](./code-mapping.md) | Document → Code translation | Phase 3 - Converting docs to code |
| [Mapping Validation Best Practices](./mapping-validation-best-practices.md) | Mapping integrity and validation strategies | **Critical** - Before and after implementation |

### General
| Document | Purpose | When to Use |
|----------|---------|-------------|
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
