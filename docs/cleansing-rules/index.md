# Cleansing Rules Documentation Index

This directory tracks the status of cleansing-rule coverage for active ETL domains.

## Template

Use [cleansing-rules-template.md](../templates/cleansing-rules-template.md) when documenting or expanding a domain.

## Coverage Status

| Domain | Status | Notes |
|--------|--------|-------|
| `annuity_performance` | Present but partial | [annuity-performance.md](./annuity-performance.md) exists, but parts of the migration-era detail still need verification against current code. |
| `annuity_income` | Present but partial | [annuity-income.md](./annuity-income.md) exists but still contains stale migration-era assumptions and needs verification updates. |
| `annual_award` | Missing | No domain-specific cleansing-rules document is checked in yet. |
| `annual_loss` | Missing | No domain-specific cleansing-rules document is checked in yet. |
| `sandbox_trustee_performance` | Missing | No sandbox-specific cleansing-rules document is checked in yet. |

## Status Definitions

- `Active and verified`: references current code/config behavior and can be used operationally.
- `Present but partial`: file exists but needs verification or structural cleanup.
- `Missing`: active domain has no dedicated cleansing-rules document yet.
- `Historical only`: retained for traceability and excluded from active onboarding paths.

## Active Domain References

- Domain contracts live under [docs/domains](../domains/).
- Operator procedures live under [docs/runbooks](../runbooks/).
- Repository-wide standards live in [Documentation Standards](../engineering/documentation-standards.md).
