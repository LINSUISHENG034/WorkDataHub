# Non-Functional Requirements

Focused on **performance, reliability, maintainability, and security** - the attributes critical for an internal data platform.

---

### NFR-1: Performance Requirements
**"Fast enough to complete within business hours"**

**NFR-1.1: Batch Processing Speed**
- **Requirement:** Process a complete monthly data drop (6+ domains, ~50,000 total rows) in <30 minutes
- **Rationale:** Allows processing to complete within work hours if issues require manual intervention
- **Measurement:**
  - Track end-to-end execution time per domain
  - Measure total time from first file read to last database commit
  - 95th percentile must be <30 minutes for full monthly run
- **Acceptance:**
  - ✅ Annuity domain (highest complexity, ~10K rows): <10 minutes
  - ✅ Simple domains (~2K rows): <3 minutes
  - ✅ All 6 domains in parallel: <30 minutes total

**NFR-1.2: Database Write Performance**
- **Requirement:** Bulk insert/upsert of 10,000 rows completes in <60 seconds
- **Rationale:** Database write shouldn't be bottleneck
- **Measurement:**
  - Time database operations separately from transformation
  - Use connection pooling and batch inserts (not row-by-row)
- **Acceptance:**
  - ✅ 10,000 row upsert: <60 seconds
  - ✅ Connection pooling enabled (max 5 connections)
  - ✅ Batch size optimized (test 500, 1000, 5000 row batches)

**NFR-1.3: Memory Efficiency**
- **Requirement:** Process any single domain within 4GB RAM
- **Rationale:** Runs on standard developer workstation or small server
- **Measurement:**
  - Monitor peak memory usage during execution
  - Use memory profiling tools (memory_profiler)
- **Acceptance:**
  - ✅ Peak memory <4GB for largest domain (annuity)
  - ✅ Memory released after each domain (no leaks)
  - ✅ Streaming processing for files >100MB (chunked reading)

**Performance Anti-Goals:**
- ❌ Real-time/streaming performance (monthly batch is sufficient)
- ❌ Horizontal scaling (single-machine execution is fine)
- ❌ Sub-second response times (batch processing acceptable)

---

### NFR-2: Reliability Requirements
**"Data integrity above all else"**

**NFR-2.1: Data Integrity Guarantees**
- **Requirement:** Zero data corruption - incorrect data never written to database
- **Rationale:** PowerBI dashboards drive business decisions; bad data = bad decisions
- **Measurement:**
  - Golden dataset regression tests must pass 100%
  - Validation failures must prevent database writes
  - Transactional rollback on any error
- **Acceptance:**
  - ✅ Multi-layer validation (Bronze/Silver/Gold) catches all schema violations
  - ✅ Database transactions ensure atomicity (all-or-nothing)
  - ✅ Parity tests detect any output changes vs. legacy within 0.01% tolerance
  - ✅ Zero production incidents with data corruption (measured quarterly)

**NFR-2.2: Fault Tolerance**
- **Requirement:** Pipeline failures are recoverable; system resumes from failure point
- **Rationale:** Monthly processing shouldn't restart from scratch if one domain fails
- **Measurement:**
  - Track partial completion states
  - Test recovery scenarios (database down, file missing, network error)
- **Acceptance:**
  - ✅ Domain isolation: failure in domain A doesn't affect domain B
  - ✅ Idempotent operations: re-running same input produces identical output
  - ✅ Clear error messages identify exact failure point (file, row, column)
  - ✅ Manual re-run possible for specific domain without re-processing all domains

**NFR-2.3: Operational Reliability**
- **Requirement:** <2% pipeline failure rate in production (measured monthly)
- **Rationale:** Automation value lost if pipelines frequently require manual fixes
- **Measurement:**
  - Track success/failure ratio per month
  - Classify failures: data quality issues vs. code bugs vs. infrastructure
- **Acceptance:**
  - ✅ >98% success rate for monthly production runs
  - ✅ All failures have root cause identified in logs
  - ✅ Retry logic for transient failures (database connection timeout, etc.)
  - ✅ Graceful degradation: optional services (enrichment) don't block core pipeline

**NFR-2.4: Data Loss Prevention**
- **Requirement:** Bronze layer data preserved indefinitely for re-processing
- **Rationale:** Source Excel files are immutable audit trail
- **Measurement:**
  - Verify Bronze files never modified or deleted
  - Test re-processing from historical Bronze data
- **Acceptance:**
  - ✅ Original Excel files retained in `reference/monthly/YYYYMM/收集数据/`
  - ✅ Re-running pipeline on month-old data produces identical results
  - ✅ Backup strategy: Bronze files backed up to separate location (weekly)

---

### NFR-3: Maintainability Requirements
**"Built for team handoff"**

**NFR-3.1: Code Quality Standards**
- **Requirement:** 100% type coverage with mypy; zero type errors
- **Rationale:** Type safety prevents bugs and improves IDE autocomplete for team
- **Measurement:**
  - Run `mypy src/` in CI/CD
  - Block merges if type errors exist
- **Acceptance:**
  - ✅ All public functions have type hints
  - ✅ `mypy --strict` passes with zero errors
  - ✅ Pydantic models enforce runtime type validation
  - ✅ CI/CD enforces type checking on every commit

**NFR-3.2: Test Coverage**
- **Requirement:** >80% test coverage for domain/ logic; 100% for critical paths
- **Rationale:** Refactoring confidence and regression prevention
- **Measurement:**
  - `pytest --cov=src/work_data_hub/domain`
  - Track coverage trends over time
- **Acceptance:**
  - ✅ Domain services (transformation logic): >90% coverage
  - ✅ Critical paths (validation, database writes): 100% coverage
  - ✅ Integration tests for each domain: end-to-end pipeline execution
  - ✅ Golden dataset regression tests for legacy parity

**NFR-3.3: Documentation Standards**
- **Requirement:** All domain services have docstrings; architecture documented
- **Rationale:** Team member onboarding and knowledge transfer
- **Measurement:**
  - Manual review of docstring presence
  - Architecture diagrams exist and are current
- **Acceptance:**
  - ✅ Every domain service function has docstring (Google style)
  - ✅ Pydantic models document field meanings (especially Chinese fields)
  - ✅ README.md explains: project structure, how to add domain, how to run pipelines
  - ✅ Architecture diagram shows: Bronze/Silver/Gold flow, dependency boundaries

**NFR-3.4: Code Review & CI/CD**
- **Requirement:** All changes require passing CI/CD checks before merge
- **Rationale:** Prevent regressions and maintain code quality
- **Measurement:**
  - CI/CD pipeline results
  - Time to merge (shouldn't block development)
- **Acceptance:**
  - ✅ CI runs: mypy (type check), ruff (lint/format), pytest (tests), parity tests
  - ✅ All checks must pass green before merge allowed
  - ✅ CI execution time: <5 minutes for fast feedback
  - ✅ Code review required for domain changes (single reviewer sufficient)

**NFR-3.5: Dependency Management**
- **Requirement:** Pin all dependency versions; reproducible builds
- **Rationale:** Avoid "works on my machine" issues during team handoff
- **Measurement:**
  - Check `pyproject.toml` for pinned versions
  - Test fresh install in clean environment
- **Acceptance:**
  - ✅ All dependencies pinned: `pandas==2.1.0` (not `pandas>=2.0`)
  - ✅ `requirements.txt` (or Poetry lock file) version-locked
  - ✅ Python version specified: `requires-python = ">=3.10"`
  - ✅ Fresh install + test passes on clean machine

---

### NFR-4: Security Requirements
**"Protect credentials and database access"**

**NFR-4.1: Credential Management**
- **Requirement:** No secrets committed to git; environment variables or secret manager
- **Rationale:** Prevent credential leaks if repository shared
- **Measurement:**
  - Manual code review for hardcoded secrets
  - Use tools like `git-secrets` or `trufflehog`
- **Acceptance:**
  - ✅ Database passwords in environment variables or `.env` (gitignored)
  - ✅ EQC API credentials in environment variables
  - ✅ `.env.example` template provided (without actual secrets)
  - ✅ Pre-commit hook prevents committing `.env` or credential files

**NFR-4.2: Database Access Control**
- **Requirement:** Database credentials grant minimum required privileges
- **Rationale:** Limit blast radius if credentials compromised
- **Measurement:**
  - Review database user permissions
  - Test with read-only user (should fail on writes)
- **Acceptance:**
  - ✅ Production database user: INSERT, UPDATE, SELECT on specific tables only (no DROP, CREATE)
  - ✅ Development database user: full permissions on dev database
  - ✅ Connection strings environment-specific (dev vs. prod databases different)
  - ✅ SSL/TLS enforced for database connections

**NFR-4.3: Input Validation (Security)**
- **Requirement:** All external inputs validated against injection attacks
- **Rationale:** Prevent SQL injection or malicious file paths
- **Measurement:**
  - Code review for SQL concatenation (should use parameterized queries)
  - Test with malicious inputs
- **Acceptance:**
  - ✅ All SQL queries use parameterized statements (no string concatenation)
  - ✅ File paths validated: no `../` traversal, must be within `reference/` directory
  - ✅ Excel data treated as untrusted: validated before processing
  - ✅ No `eval()` or `exec()` on user-provided data

**NFR-4.4: Audit Trail Security**
- **Requirement:** Pipeline execution logs are tamper-evident
- **Rationale:** Investigate issues or suspicious activity
- **Measurement:**
  - Log integrity checks (append-only, no modification)
  - Retention policy enforced
- **Acceptance:**
  - ✅ Logs written append-only (cannot be edited after creation)
  - ✅ Execution history in database includes: user, timestamp, input files
  - ✅ Log retention: 2 years minimum
  - ✅ Access controls: only authorized users can read production logs

**Security Anti-Goals:**
- ❌ Encryption at rest (database/filesystem already secured by IT)
- ❌ OAuth/SSO (internal tool, Windows authentication sufficient)
- ❌ Penetration testing (not external-facing)
- ❌ GDPR compliance (internal enterprise data, not personal consumer data)

---

### NFR-5: Usability Requirements (Developer/Operator)
**"Easy to operate and debug"**

**NFR-5.1: Clear Error Messages**
- **Requirement:** Every error includes actionable guidance
- **Rationale:** Reduce mean time to resolution (MTTR)
- **Measurement:**
  - Manual review of error message quality
  - Track time to resolve incidents
- **Acceptance:**
  - ✅ Errors specify: what failed, where (file/row/column), why, how to fix
  - ✅ Example: "Bronze validation failed: file 'annuity_202501.xlsx', row 15, column '月度' contains 'INVALID' - expected date format"
  - ✅ Validation errors link to docs/examples
  - ✅ No cryptic stack traces shown to end users (log full trace, show summary)

**NFR-5.2: Debuggability**
- **Requirement:** Failed pipeline state is inspectable for troubleshooting
- **Rationale:** Fix issues quickly without guessing
- **Measurement:**
  - Test debugging scenarios (inspect failed rows, replay specific step)
  - Developer feedback on debug experience
- **Acceptance:**
  - ✅ Failed rows exported to CSV with original values + error reasons
  - ✅ Dagster UI shows: execution graph, step-by-step logs, duration per step
  - ✅ Replay capability: re-run specific domain without re-processing all
  - ✅ Dry-run mode: validate without database writes

**NFR-5.3: Operational Simplicity**
- **Requirement:** Common operations require single command
- **Rationale:** Reduce operator burden and training time
- **Measurement:**
  - Task analysis: how many steps for common operations?
  - Operator feedback on ease of use
- **Acceptance:**
  - ✅ Process monthly data: `dagster job launch annuity_performance_job --config month=202501`
  - ✅ View pipeline status: Dagster UI dashboard
  - ✅ Re-run failed domain: Single button click in Dagster UI
  - ✅ No manual SQL scripts required for normal operations

---

**Non-Functional Requirements Summary:**

| Category | Key Metrics | Critical Requirements |
|----------|-------------|----------------------|
| **Performance** | <30 min full monthly run, <10 min per domain, <4GB RAM | Batch processing speed sufficient for business hours |
| **Reliability** | >98% success rate, 0% data corruption, 100% parity | Data integrity guaranteed through multi-layer validation |
| **Maintainability** | 100% type coverage, >80% test coverage, docs complete | Team-ready for handoff with clear architecture |
| **Security** | No secrets in git, parameterized queries, audit logs | Credentials protected, SQL injection prevented |
| **Usability** | Actionable errors, single-command ops, inspectable failures | Easy to debug and operate |

**Total NFRs:** 17 specific requirements across 5 categories

---
