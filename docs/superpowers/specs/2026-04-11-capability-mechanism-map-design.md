# System Capability And Mechanism Map Design

## Purpose

Define a standard documentation pattern for describing:

1. what the system does
2. how each capability is implemented
3. how critical fields are derived

This design is intended to reduce black-box behavior for new maintainers and
agents working in the WorkDataHub repository.

## Problem

The current repository already contains the core facts needed to understand the
system, but they are spread across:

- domain adapters and pipeline builders
- shared infrastructure services
- YAML configuration
- SQL and post-ETL hooks
- tests, golden datasets, and runbooks

That distribution makes the project powerful, but it also makes it difficult to
answer simple questions quickly:

- What capabilities does the system actually provide?
- Which mechanism implements a capability?
- Is a rule expressed in code, YAML, SQL, or a hook?
- Why did a final field value become what it is?

## Goals

- Provide one standard template for top-down system mapping.
- Separate business capabilities from implementation mechanisms.
- Add a dedicated field-trace section for explainability.
- Force each documented behavior to point back to concrete repository artifacts.
- Make the result readable for both humans and agents.

## Chosen Structure

The template is organized into three linked views.

### 1. System Capability Map

Business-facing inventory of what the system does.

Each row must answer:

- what problem is solved
- when it runs
- what it consumes
- what it produces
- what it affects
- where the source of truth lives

### 2. Implementation Mechanism Map

Engineering-facing inventory of how each capability is realized.

Each row must answer:

- which stage performs the work
- what the entry point is
- which modules are involved
- whether rules come from code, config, SQL, or hooks
- what side effects happen
- which tests or runbooks protect the behavior

### 3. Key Field Trace Table

Field-level explainability view for the most important outputs.

Each row must answer:

- where the field starts
- which stages mutate it
- which named rules affect it
- where those rules live
- where the final value lands
- how the behavior is verified

### Practical Additions After First Pilot Fill

The first real fill exposed three more needs that are now part of the template:

- a capability dependency view for cross-domain and external coupling
- an execution-order view for gates and hook sequencing
- an explicit place to record config/comment/implementation drift

The second real fill exposed one more recurring need:

- an activation-condition field for mechanisms that are optional or
  context-dependent at runtime

## Design Principles

- One row, one claim. Avoid large narrative paragraphs inside mapping tables.
- Every important claim must have a repository anchor.
- Avoid vague labels such as "data cleansing" unless the actual mechanism is
  also named.
- Prefer capability-to-mechanism linking by ID instead of prose references.
- Treat hooks and SQL as first-class mechanisms, not footnotes.
- Document only stable, reusable facts in the map. Temporary migration notes
  belong elsewhere.

## Scope Guidance

Recommended usage order:

1. start with one domain or one vertical slice
2. fill the capability map
3. map each capability to mechanisms
4. add field-trace rows only for critical fields

Do not attempt to document every field in the repository in the first pass.
Prioritize:

- high-risk business outputs
- fields with heavy cleansing
- fields with cross-table derivation
- fields touched by hooks or backfill flows

## Clarity Acceptance Criteria

The documentation is considered usable only if a new maintainer can:

1. identify the capability responsible for a business outcome
2. locate the implementation stage and source files in three hops or fewer
3. tell whether a rule lives in code, config, SQL, or a hook
4. trace a critical field from raw input to final sink
5. find at least one test, snapshot, or runbook that validates the behavior
6. see open inconsistencies instead of having them hidden inside prose

## Deliverables

- Template file:
  `docs/templates/system-capability-mechanism-map-template.md`
- Optional future outputs:
  domain-specific filled maps under `docs/domains/` or `docs/reference/`

## Notes

This design intentionally optimizes for maintenance and explainability rather
than visual elegance. The first requirement is that the map be operationally
useful.
