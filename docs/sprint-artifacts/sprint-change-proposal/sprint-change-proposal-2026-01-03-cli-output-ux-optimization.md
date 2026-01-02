# Sprint Change Proposal: CLI Output UX Optimization

**Date**: 2026-01-03
**Author**: Correct-Course Workflow
**Status**: Proposed
**Scope**: Minor (Direct Implementation)

---

## 1. Issue Summary

### Problem Statement

ETL 批处理终端输出存在严重的用户体验问题：

> _"运行 ETL 批处理时终端里是信息洪流——Dagster DEBUG 日志、JSON 格式的结构化日志、Rich 进度条，它们像三条河流交织在一起，文字重叠、行序混乱。关键业务信息被技术细节淹没。"_

### Discovery Context

- **Trigger Story**: Story 7.5-4 (Rich Terminal UX Enhancement) 完成后发现的后续优化需求
- **Evidence Document**: `docs/specific/etl-logging/ux-cli-output-optimization.md`

### Current State Analysis

| Problem Type | Manifestation | Severity |
|--------------|---------------|----------|
| **日志级别过于详细** | Dagster DEBUG 消息占据 80% 屏幕 | 🔴 HIGH |
| **多流输出冲突** | Rich 进度条与 JSON 日志同时写入 stdout | 🔴 HIGH |
| **冗长的 ExecutionID** | 每行重复 `43617c7b-7bd7-4e03-b683...` | 🟠 MEDIUM |
| **缺乏用户导向摘要** | 重要信息淹没在技术细节中 | 🟠 MEDIUM |
| **JSON 日志可读性差** | 非 debug 模式仍输出 JSON 格式日志 | 🟡 LOW |

---

## 2. Impact Analysis

### Epic Impact

| Epic | Status | Impact |
|------|--------|--------|
| **Epic 7.5** | in-progress | Add new Story 7.5-6 to implement CLI output optimization |
| **Epic 8** | blocked | No impact on blocking relationship |

### Artifact Conflicts

| Artifact | Impact | Changes Required |
|----------|--------|------------------|
| **CLI Module** (`cli/etl/`) | HIGH | Add `--verbose`, `--quiet` CLI arguments |
| **Logging Module** (`utils/logging.py`) | HIGH | Enhance `reconfigure_for_console()` with verbosity levels |
| **Orchestration** (`orchestration/`) | MEDIUM | Configure Dagster logging suppression |
| **Documentation** | LOW | Update CLI parameter documentation |

### Technical Impact

**Files to Modify:**

1. `src/work_data_hub/utils/logging.py` - Verbosity level filtering
2. `src/work_data_hub/cli/etl/main.py` - New CLI arguments
3. `src/work_data_hub/cli/etl/console.py` - Channel separation (Rich → stderr)
4. `src/work_data_hub/orchestration/config.py` - Dagster log level control

---

## 3. Recommended Approach

### Selected Path: **Option 1 - Direct Adjustment**

Add Story 7.5-6 to Epic 7.5 for CLI Output UX Optimization.

### Rationale

1. **Technical Solution Ready**: UX design document provides complete implementation approach
2. **Low Risk**: Changes are additive, not modifying existing functionality
3. **Low Effort**: Estimated 8-16 hours implementation time
4. **Clear Scope**: Well-defined acceptance criteria in design document

### Effort & Risk Assessment

| Metric | Value | Notes |
|--------|-------|-------|
| **Effort** | Low (8-16 hours) | Clear implementation path |
| **Risk** | Low | Additive changes, backward compatible |
| **Timeline Impact** | None | Parallel work possible |

---

## 4. Detailed Change Proposals

### Story Addition: Story 7.5-6

**Title**: CLI Output UX Optimization (Verbosity Levels)

**Description**: Implement progressive disclosure output architecture with verbosity levels to improve CLI terminal UX.

**Acceptance Criteria**:

- [ ] **AC-1**: Default mode is clean (no JSON logs, no Dagster DEBUG)
- [ ] **AC-2**: `--quiet` flag shows only errors and final summary
- [ ] **AC-3**: `--verbose` flag adds INFO-level structlog output
- [ ] **AC-4**: `--debug` flag enables full Dagster and DEBUG output
- [ ] **AC-5**: Rich spinners don't overlap with log text
- [ ] **AC-6**: `--no-rich` backward compatibility preserved

**Priority Breakdown** (from UX Design):

| Priority | Task | Description |
|----------|------|-------------|
| 🔴 P0 | Suppress Dagster DEBUG | Configure Dagster logger to WARNING in default mode |
| 🟠 P1 | Add `--verbose` flag | Enable INFO-level output on demand |
| 🟡 P2 | Add `--quiet` flag | Minimal output mode |
| 🟢 P3 | Channel separation | Rich → stderr, logs → stdout |

### Technical Implementation

#### 1. Dagster Log Level Control

```python
# In orchestration/config.py or similar
import logging

def configure_dagster_logging(debug: bool = False):
    dagster_logger = logging.getLogger("dagster")
    if debug:
        dagster_logger.setLevel(logging.DEBUG)
    else:
        dagster_logger.setLevel(logging.WARNING)  # Only WARN and above
```

#### 2. Structlog Verbosity Filtering

```python
# In utils/logging.py - enhance reconfigure_for_console
def reconfigure_for_console(debug: bool = False, verbose: bool = False) -> None:
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING  # Default: quiet mode

    logging.root.setLevel(level)
```

#### 3. New CLI Arguments

```python
# In main.py argument parser
parser.add_argument(
    "--verbose", "-v",
    action="store_true",
    help="Show diagnostic information (INFO-level logs)"
)

parser.add_argument(
    "--quiet", "-q",
    action="store_true",
    help="Minimal output (errors and final summary only)"
)
```

---

## 5. Implementation Handoff

### Scope Classification: **Minor**

This change can be implemented directly by the development team.

### Deliverables

1. **Story File**: `docs/sprint-artifacts/stories/7.5-6-cli-output-ux-optimization.md`
2. **Implementation**: Code changes per technical specification above
3. **Tests**: Unit tests for verbosity level behavior
4. **Documentation**: Update CLI parameter reference in `docs/project-context.md`

### Sprint Status Update

```yaml
# Add to sprint-status.yaml under Epic 7.5
7.5-6-cli-output-ux-optimization: backlog  # CLI Output UX Optimization
```

### Success Criteria

1. Running ETL without flags produces clean, user-friendly output
2. Verbosity levels work as specified (`--quiet`, `--verbose`, `--debug`)
3. All existing tests pass
4. Backward compatibility with `--debug` and `--no-rich` preserved

---

## 6. References

- **UX Design Document**: `docs/specific/etl-logging/ux-cli-output-optimization.md`
- **Related Story**: Story 7.5-4 (Rich Terminal UX Enhancement)
- **Related Story**: Story 7.5-5 (Unified Failed Records Logging)

---

## Approval

- [x] **User Approval**: Approved 2026-01-03
- [x] **Sprint Status Updated**: Story 7.5-6 added to sprint-status.yaml
- [x] **Story File Created**: `docs/sprint-artifacts/stories/7.5-6-cli-output-ux-optimization.md`
