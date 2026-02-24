# CLI Terminal Output UX Optimization Design

**Status**: Draft  
**Author**: UX Designer Agent  
**Date**: 2026-01-02  
**Story**: CLI Output UX Enhancement (Story 7.5-6)

---

## 📖 Problem Statement

### User Story

> _"作为一名数据工程师，我运行 ETL 批处理时只想知道：进度如何？有没有问题？结果怎么样？但终端里却是信息洪流——Dagster 的 DEBUG 日志、JSON 格式的结构化日志、Rich 进度条，它们像三条河流交织在一起，文字重叠、行序混乱。"_

### Current State Analysis

运行 `uv run --env-file .wdh_env python -m work_data_hub.cli etl --all-domains --period 202510 --file-selection newest --execute --no-enrichment` 时观察到：

| 问题类型               | 具体表现                               | 影响程度 |
| ---------------------- | -------------------------------------- | -------- |
| **日志级别过于详细**   | Dagster DEBUG 消息占据 80%屏幕         | 🔴 高    |
| **多流输出冲突**       | Rich 进度条与 JSON 日志同时写入 stdout | 🔴 高    |
| **冗长的 ExecutionID** | 每行重复 `43617c7b-7bd7-4e03-b683...`  | 🟠 中    |
| **缺乏用户导向摘要**   | 重要信息淹没在技术细节中               | 🟠 中    |
| **JSON 日志可读性差**  | 非 debug 模式仍输出 JSON 格式日志      | 🟡 低    |

---

## 🎯 Design Goals

1. **信噪比优化** - 默认只显示用户关心的信息
2. **层次感清晰** - 建立明确的输出层次结构
3. **渐进式详情** - 通过参数控制日志详细程度
4. **通道分离** - 终端 UI 与诊断日志分离

---

## 🏗️ Proposed Output Architecture

### Output Hierarchy Model

```
┌─────────────────────────────────────────────────────────────────┐
│  Level 0: Rich UX Layer (用户交互层)                            │
│  - Progress spinners, status indicators                        │
│  - Domain completion summaries (✅/❌)                          │
│  - File hyperlinks                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓ Separate channel
┌─────────────────────────────────────────────────────────────────┐
│  Level 1: Business Summary (业务摘要层)                         │
│  - Row counts, table names                                      │
│  - Batch processing summary                                     │
│  - Failure log file path                                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓ --verbose
┌─────────────────────────────────────────────────────────────────┐
│  Level 2: Diagnostic Info (诊断信息层)                          │
│  - Structlog INFO/WARNING messages                              │
│  - Column normalization summary                                 │
│  - Reference backfill details                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓ --debug
┌─────────────────────────────────────────────────────────────────┐
│  Level 3: Debug Trace (调试追踪层)                              │
│  - Dagster DEBUG/INFO messages                                  │
│  - Full ExecutionID                                             │
│  - Step-by-step operation logs                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Verbosity Levels

| Flag        | Level | Description                            |
| ----------- | ----- | -------------------------------------- |
| `--quiet`   | 0     | Only errors and final summary          |
| (default)   | 0-1   | Rich UX + Business summary             |
| `--verbose` | 0-2   | Add diagnostic structlog output        |
| `--debug`   | 0-3   | Full debug including Dagster internals |

---

## 📐 Mockup: Ideal Output Experience

### Default Mode (Level 0-1)

```
📋 Processing all configured domains: annuity_performance, annuity_income
   Total: 2 domains
==================================================

⠙ Processing annuity_performance...
✅ Domain annuity_performance completed successfully
   📄 규모明细: 37,127 rows → business.규模明细

⠙ Processing annuity_income...
✅ Domain annuity_income completed successfully
   📄 收入明细: 13,639 rows → business.收入明细

==================================================
📊 MULTI-DOMAIN BATCH PROCESSING SUMMARY
==================================================
Total domains: 2
Successful: 2
Failed: 0

📄 Failure log: logs\wdh_etl_failures_etl_20260102_234406_80ecf2.csv (0 failures)

Per-domain results:
  ✅ annuity_performance: SUCCESS
  ✅ annuity_income: SUCCESS
==================================================
🎉 Multi-domain processing completed successfully
```

### Verbose Mode (`--verbose`)

```
📋 Processing all configured domains: annuity_performance, annuity_income
   Total: 2 domains
==================================================

⠙ Processing annuity_performance...
   [INFO] column_normalizer.summary columns_normalized=23 empty_placeholders_generated=0
   [INFO] Excel reading completed - rows: 37,127
   [INFO] Load operation completed - mode: delete_insert, deleted: 37127, inserted: 37127
✅ Domain annuity_performance completed successfully

...
```

### Debug Mode (`--debug`)

```
📋 Processing all configured domains: annuity_performance, annuity_income
   Total: 2 domains
==================================================

⠙ Processing annuity_performance...
2026-01-02 23:44:13 [debug] dagster.annuity_performance_job.read_excel_op STEP_START
2026-01-02 23:44:13 [debug] dagster.read_excel_op - Excel reading completed - file:...
...
```

---

## 🔧 Technical Implementation Approach

### 1. Dagster Log Level Control

**Problem**: Dagster outputs DEBUG-level messages to stdout by default.

**Solution**: Configure Dagster's Python logging to suppress DEBUG for non-debug mode.

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

### 2. Structlog Output Suppression

**Problem**: Structlog INFO messages appear in terminal even in default mode.

**Solution**: Add log level filtering based on verbosity flag.

```python
# In utils/logging.py - enhance reconfigure_for_console
def reconfigure_for_console(debug: bool = False, verbose: bool = False) -> None:
    if debug:
        # Full output with ConsoleRenderer
        level = logging.DEBUG
    elif verbose:
        # INFO and above with formatted output
        level = logging.INFO
    else:
        # WARNING and above only (default: quiet mode)
        level = logging.WARNING

    logging.root.setLevel(level)
```

### 3. Rich Console Channel Separation

**Problem**: Rich spinners conflict with log output on the same stdout.

**Solution**: Use `stderr` for logs when Rich mode is active.

```python
# In console.py - RichConsole enhancement
class RichConsole(BaseConsole):
    def __init__(self):
        self._console = Console(stderr=True)  # Rich to stderr
        # JSON/text logs go to stdout
```

**Alternative**: Use Rich's `Console.capture()` to buffer log output and render after status updates.

### 4. New CLI Arguments

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

## 📋 Acceptance Criteria

### AC-1: Default Mode is Clean

- [ ] Running ETL without flags shows only Rich UX and business summaries
- [ ] No JSON logs appear in terminal
- [ ] No Dagster DEBUG messages appear

### AC-2: Verbosity Levels Work

- [ ] `--quiet` shows only errors and final summary
- [ ] `--verbose` adds INFO-level structlog output
- [ ] `--debug` enables full Dagster and DEBUG output

### AC-3: Output Doesn't Conflict

- [ ] Rich spinners don't overlap with log text
- [ ] Progress indicators update smoothly

### AC-4: Backward Compatibility

- [ ] `--debug` existing behavior preserved
- [ ] `--no-rich` continues to work

---

## 🔗 Related Stories

- **Story 7.5-4**: Rich Terminal UX Enhancement (completed)
- **Story 7.5-5**: Unified Failed Records Logging (completed)
- **Proposed Story 7.6-1**: CLI Output UX Optimization (this design)

---

## 📝 Notes for Implementation

1. **Dagster Log Suppression** is the highest-impact change - it removes 80% of noise
2. **Channel separation** (Rich→stderr, logs→stdout) may break existing log parsing scripts
3. Consider **log file output** as default for all diagnostic logs (already supported via `LOG_TO_FILE=1`)
4. **Testing**: Need to verify CI/CD mode (`--no-rich`) still works correctly

---

## 🎨 UX Designer Recommendation

> _"用户体验的核心是'恰到好处'——既不让用户困惑于信息过载，也不让他们在需要诊断时无从下手。渐进式披露（progressive disclosure）是解决这个矛盾的关键：默认给用户一个干净的视图，但让详情触手可及。"_

**Priority Recommendation**:

1. 🔴 **P0**: Suppress Dagster DEBUG in default mode
2. 🟠 **P1**: Add `--verbose` flag for INFO-level output
3. 🟡 **P2**: Add `--quiet` flag for minimal output
4. 🟢 **P3**: Channel separation (Rich→stderr)
