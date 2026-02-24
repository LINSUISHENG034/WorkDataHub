# Novel Patterns

This section documents unique technical patterns specific to WorkDataHub.

### Pattern 1: File-Pattern-Aware Version Detection

**Problem Domain:** Monthly data governance with version control

**Novel Aspect:** Unlike traditional "highest version wins," this scopes version detection to specific file patterns per domain, enabling partial corrections without data loss.

**When to Use:**
- Multi-domain data ingestion from shared folder structures
- Version corrections that don't cover all domains
- Regulatory environments requiring version audit trails

**Implementation:** See Decision #1

---

### Pattern 2: Legacy-Compatible Temporary ID Generation

**Problem Domain:** Gradual enrichment with stable cross-domain joins

**Novel Aspect:** Combines cryptographic stability (HMAC) with legacy normalization parity (29 status marker patterns) to ensure consistent temporary IDs across brownfield/greenfield systems.

**When to Use:**
- Brownfield migrations requiring backward compatibility
- Enrichment services with async resolution
- Chinese company name normalization

**Implementation:** See Decision #2

---

### Pattern 3: Hybrid Pipeline Step Protocol

**Problem Domain:** Performance vs. validation trade-offs

**Novel Aspect:** Single pipeline supports both DataFrame-level (vectorized performance) and row-level (detailed validation) steps, allowing optimal pattern selection per transformation type.

**When to Use:**
- Data pipelines requiring both bulk operations and per-row validation
- Integration with multiple validation libraries (pandera + Pydantic)
- External API enrichment mixed with bulk transformations

**Implementation:** See Decision #3

---

### Pattern 4: Strangler Fig with Parity Enforcement

**Problem Domain:** Risk-free legacy system replacement

**Novel Aspect:** CI-enforced parity tests block deployment if new implementation deviates from legacy, ensuring zero business logic regression during migration.

**When to Use:**
- Mission-critical system migrations
- Regulatory environments requiring output consistency
- Brownfield refactoring with zero tolerance for deviations

**Implementation:**
```python
# tests/e2e/test_pipeline_vs_legacy.py
def test_annuity_pipeline_parity():
    """Enforce 100% output parity between new and legacy annuity pipeline."""
    # Run new pipeline
    new_output = run_annuity_pipeline(test_month="202501")

    # Run legacy pipeline
    legacy_output = run_legacy_annuity_hub(test_month="202501")

    # Assert exact match (CI blocks on failure)
    pd.testing.assert_frame_equal(
        new_output.sort_values(by=['计划代码', '月度']),
        legacy_output.sort_values(by=['计划代码', '月度']),
        check_dtype=False,  # Allow type improvements
        check_exact=False,  # Allow float precision improvements
        rtol=1e-5
    )
```

---
