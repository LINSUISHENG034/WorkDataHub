# Reference Documentation

This directory stores current technical reference material that supports implementation and operations but is not the primary onboarding path.

Typical contents:
- schema panoramas
- data-processing reference
- reusable architecture patterns that still match current code

## Reference Structure

| Directory | Use For |
|-----------|---------|
| `automation/` | stable notes used by scripts, automation helpers, or GUI support tools |
| `critical/` | operational safety notes that are referenced by code, scripts, or migration procedures |
| `customer/` | customer-domain technical notes that support shared normalization or reference behavior |

## Placement Rules

- Put a document in `docs/reference/` only if it is still current and supports implementation or operations.
- If a note is only useful for historical traceability, move it to `docs/archive/` instead.
- Prefer placing script-facing or code-referenced notes in a specific reference subdirectory rather than at the top of `docs/`.

## Current Reference Notes

- [Data Processing Guide](./data_processing_guide.md)
- [Database Schema Panorama](./database-schema-panorama.md)
- [Critical Downgrade Notes](./critical/001_downgrade_db.md)
- [EQC Automation Notes](./automation/EQC/login_page_elements.md)
- [Customer Name Refactor Notes](./customer/customer-name-normalization-refactor.md)
