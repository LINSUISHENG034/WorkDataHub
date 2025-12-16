# CLI Architecture Validation - Issues Log

**Validation Date**: 2025-12-16
**Guide**: `manual-validation-guide-cli-architecture.md`

---

## Issues Summary

| ID | Severity | Status | Feature | Description |
|----|----------|--------|---------|-------------|
| I001 | Medium | Open | Guide | Windows PowerShell 命令格式不兼容 |
| I002 | High | Open | F2 ETL | Plan-only 模式仍尝试连接数据库并失败 |

---

## Issue Details

### I001: Windows PowerShell 命令格式不兼容

**Severity**: Medium  
**Feature**: Guide Documentation  
**Status**: Open

**Description**:  
指南中使用的 `PYTHONPATH=src uv run ...` 语法在 Windows PowerShell 中不工作。PowerShell 无法识别 `PYTHONPATH=src` 的 Unix shell 语法。

**Impact**:  
Windows 用户无法直接按照指南运行命令。

**Suggested Fix**:  
- 方案 A: 更新指南，添加 Windows PowerShell 格式的替代命令:
  ```powershell
  $env:PYTHONPATH="src"; uv run --env-file .wdh_env python -m work_data_hub.cli ...
  ```
- 方案 B: 创建跨平台的包装脚本

---

### I002: Plan-only 模式仍尝试连接数据库并失败

**Severity**: High  
**Feature**: F2 Single-Domain ETL  
**Status**: Open

**Description**:  
运行 ETL 命令时，即使使用 `--plan-only` 参数或不指定 `--execute`，命令仍会尝试执行 `load_op` 步骤并失败:

```
RUN_FAILURE - Execution of run for "annuity_performance_job" failed. Steps failed: ['load_op'].
```

**Expected Behavior**:  
Plan-only 模式应只显示执行计划，不连接数据库或执行任何实际操作。

**Actual Behavior**:  
命令执行并在 `load_op` 步骤失败。

**Impact**:  
- 无法安全地在没有数据库的环境验证 ETL 命令
- Plan-only 模式失去了"安全预览"的价值

**Suggested Fix**:  
检查 ETL 作业逻辑，确保在 plan-only 模式下跳过数据库操作步骤。

---

## Validation Progress

### Passed ✅
- [x] F1: Unified CLI Entry Point - **PASS** (帮助显示正确，4个子命令都可用)
- [x] F3: Multi-Domain Batch Processing - **PASS** (错误处理：无效域名被正确检测)
- [x] F4: All-Domains Processing - **PASS** (互斥检查：`--domains` 和 `--all-domains` 同时使用时正确报错)
- [x] F5: Auth CLI Migration - **PASS** (命令启动正确，显示 QR code 扫码提示)
- [x] F6: EQC Refresh Integration - **PASS** (`--status` 正确显示数据新鲜度统计)
- [x] F7: Data Cleanse Integration - **PASS** (`--dry-run` 显示 `[DRY RUN]` 前缀)

### Blocked/Failed ❌
- [ ] F2: Single-Domain ETL - **BLOCKED** by I002 (plan-only 模式仍执行 load_op 并失败)

### Summary
- **Total Features**: 7
- **Passed**: 6 / 7
- **Failed/Blocked**: 1 / 7
