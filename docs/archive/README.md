# Archive Policy

Archive a document only when at least one of these is true:

- it is a one-off report, retrospective, or validation artifact
- it is superseded by a current active document
- it references repository paths or workflows that no longer exist
- it has no inbound links from `README.md`, active docs, tests, CI, `src/`, or `scripts/`
- it has not been materially verified in the last 6 months

Do not archive:

- active domain contracts
- active runbooks
- current deployment guides
- documentation referenced by tests or CI

## Archive Structure

Use the archive subdirectories consistently instead of creating new top-level buckets.

| Directory | Use For |
|-----------|---------|
| `architecture-patterns/` | historical architecture notes, patterns, and one-off design writeups that no longer describe the active repository layout |
| `deprecations/` | retired designs, replacement notes, and decommissioned technical decisions |
| `guides/` | old migration or transitional guides that are preserved for traceability but are no longer part of the active onboarding path |
| `initial/` | early discovery, planning, and readiness artifacts from project setup phases |
| `notes/` | one-off investigation notes, experience reports, or ad hoc writeups that do not justify a stable active category |
| `vendor/` | third-party, external-environment, or organization-specific reference notes that are kept only for historical context |

## Placement Rules

- If a document is still needed by operators or developers during normal work, keep it out of `docs/archive/`.
- If a document only explains how the repository used to work, place it under the closest archive subdirectory above.
- Prefer updating an existing archive subdirectory over creating a new top-level archive category.
