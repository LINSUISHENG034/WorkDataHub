# Non-Functional Requirements

### Performance (NFR §1001-1015)

| Requirement | Target | Verification |
|-------------|--------|--------------|
| Full monthly processing | <30 min | Epic 7 Story 7.4 (performance testing) |
| Single domain (50K rows) | <5 min | Epic 4 Story 4.7 (annuity perf test) |
| File discovery | <10 sec | Epic 3 Story 3.6 (discovery perf) |
| Company enrichment (5-layer) | Variable (API-dependent) | Epic 6 (full implementation, budget-controlled) |

**Architecture Support:**
- **Decision #3:** DataFrame steps for vectorized operations (10-100x faster than row iteration)
- **Decision #1:** Fast version detection (no filesystem stat calls for performance)
- **Decision #6:** 5-layer enrichment with budget control limits EQC API calls per run

### Reliability (NFR §1016-1026)

| Requirement | Target | Verification |
|-------------|--------|--------------|
| Success rate | >98% | Epic 8 Story 8.3 (reliability monitoring) |
| Data corruption | 0% | Epic 6 Story 6.3 (parity tests, CI-enforced) |
| Legacy parity | 100% | Epic 4 Story 4.6, Epic 9 parity tests |

**Architecture Support:**
- **Decision #4:** Structured error context enables root cause analysis
- **Strangler Fig pattern:** Parity tests prevent regressions

### Maintainability (NFR §1027-1032)

| Requirement | Target | Verification |
|-------------|--------|--------------|
| Type coverage (mypy) | 100% | CI enforces strict mode |
| Test coverage | >80% | CI blocks <80% coverage |
| File size limit | MAX 800 lines | Pre-commit hook enforcement |
| Function size limit | MAX 50 lines | Ruff PLR max-statements=50 |
| Cyclomatic complexity | MAX 12 branches | Ruff PLR max-branches=12 |
| Documentation | All public APIs | Epic 1 Story 1.2 (API docs) |

**Architecture Support:**
- **Decision #7:** Naming conventions ensure consistency
- **Decision #3:** Clear protocols for DataFrame vs Row steps
- **Decision #10:** Infrastructure layer extraction enables reuse across domains
- **Epic 7:** Package modularization enforces 800-line limit via pre-commit hooks

### Security (NFR §1033-1045)

| Requirement | Implementation | Verification |
|-------------|----------------|--------------|
| No secrets in git | `.env` gitignored, gitleaks CI scan | Epic 1 Story 1.1 |
| Parameterized queries | `warehouse_loader.py` uses psycopg2 params | Epic 1 Story 1.8 |
| Sensitive data sanitization | **Decision #8:** structlog sanitization rules | Epic 8 Story 8.1 |
| Audit logging | All mutations logged with user context | Epic 8 Story 8.2 |

---
