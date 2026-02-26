# Customer MDM 模块优化路线图

> **来源**: 基于 `customer_mdm_analysis.md` 分析报告 + BMAD 团队评审 + 代码库深度探查
>
> **日期**: 2026-02-26
>
> **原则**: 所有建议遵循项目既定的 KISS、YAGNI、Zero Legacy Debt 原则

---

## P0 — 必须立即处理

### P0-1: Customer Schema 表名统一重命名

- **来源**: 分析报告 §3.5 + 团队修正
- **问题**: `customer` schema 下表名中英文混用，违反项目"双命名策略"（代码英文、DB 表名中文）
- **决策**: 统一为中文表名，并修正语义不准确的命名（详见 `customer-schema-table-rename-mapping.md`）
- **状态**: 映射文档已完成，待执行实施

### P0-2: 清除脚本中硬编码的数据库密码

- **来源**: 代码库探查新发现
- **问题**: 两个 seed 脚本中存在明文密码 `Post.169828`，违反项目规则"Always load config from `.wdh_env`"
- **涉及文件**:
  - `scripts/seed_data/export_seed_data.py` (line 14-15)
  - `scripts/seed_data/seed_customer_plan_contract.py` (line 21-22)
- **修复方案**: 改为从 `.wdh_env` 加载数据库连接配置，与 `src/` 下的代码保持一致
