# Developer Guides

This directory contains all developer guides for WorkDataHub.

## Guide Categories

### Domain Migration

Guides for migrating legacy domains to the new architecture.

| Guide | Description |
|-------|-------------|
| [Domain Migration Workflow](./domain-migration/workflow.md) | **Start here** - End-to-end migration process |
| [Development Guide](./domain-migration/development-guide.md) | Implementation patterns and code templates |
| [Code Mapping](./domain-migration/code-mapping.md) | Document → Code translation |

**[View all domain migration guides →](./domain-migration/)**

### Infrastructure

Guides for infrastructure components and services.

| Guide | Description |
|-------|-------------|
| [Company Enrichment Service](./infrastructure/company-enrichment-service.md) | Company ID resolution and enrichment |
| [Database Connection Usage](./infrastructure/database-connection-usage.md) | Database connection patterns |
| [EQC Token Guide](./infrastructure/eqc-token-guide.md) | EQC API token management |

**[View all infrastructure guides →](./infrastructure/)**

## Quick Links

| Task | Guide |
|------|-------|
| Migrate a new domain | [Domain Migration Workflow](./domain-migration/workflow.md) |
| Understand company ID resolution | [Company Enrichment Service](./infrastructure/company-enrichment-service.md) |
| Create cleansing rules document | [Cleansing Rules Template](../templates/cleansing-rules-template.md) |
| Validate parity with legacy | [Legacy Parity Validation](../runbooks/legacy-parity-validation.md) |

## Directory Structure

```
docs/guides/
├── index.md                          # This file
├── domain-migration/                 # Domain migration guides
│   ├── index.md
│   ├── workflow.md
│   ├── development-guide.md
│   └── code-mapping.md
└── infrastructure/                   # Infrastructure guides
    ├── index.md
    ├── company-enrichment-service.md
    ├── database-connection-usage.md
    └── eqc-token-guide.md
```
