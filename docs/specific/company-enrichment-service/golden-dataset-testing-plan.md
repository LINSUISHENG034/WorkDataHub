# Golden Dataset 测试框架规划

> **文档状态**: 初步规划 - Epic 6 回顾讨论产出
> **创建日期**: 2025-12-08
> **来源**: Epic 6 Retrospective 讨论

---

## 1. 背景与目标

### 1.1 问题陈述

Epic 6 (Company Enrichment Service) 是 WorkDataHub 项目中最关键和最复杂的部分，它决定了业务明细记录能否正确匹配企业客户身份信息。为确保：

1. 每个实现细节都有清晰的掌握
2. 新增成员能够完全掌握企业客户身份识别的完整流程
3. 任何代码变更不会破坏现有识别逻辑

我们需要建立一套**独立于现有单元测试**的验证机制。

### 1.2 目标

1. **建立 Golden Dataset** - 一套完整的边缘测试案例，覆盖每种识别情况
2. **可视化决策路径** - 记录详细的"尝试路径"（如 `P1:MISS→P2:MISS→P3:MISS→P4:HIT`）
3. **随时验证** - 通过 CSV 表格和验证脚本，随时验证识别流程的准确性
4. **文档化** - 测试案例本身就是最好的文档

---

## 2. Golden Dataset CSV 结构

### 2.1 字段定义

```csv
test_id,category,description,plan_code,customer_name,account_name,account_number,existing_company_id,expected_company_id,expected_source,expected_decision_path,actual_company_id,actual_source,actual_decision_path,pass_fail,notes
```

### 2.2 字段说明

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `test_id` | string | 测试案例编号 | TC001 |
| `category` | string | 测试类别 | P1_PLAN_CODE, TEMP_ID |
| `description` | string | 案例描述 | 计划代码直接命中 |
| `plan_code` | string | 输入：计划代码 | FP0001 |
| `customer_name` | string | 输入：客户名称 | 公司A有限公司 |
| `account_name` | string | 输入：年金账户名 | 账户A |
| `account_number` | string | 输入：年金账户号 | ACC001 |
| `existing_company_id` | string | 输入：已有公司代码 | (空或已有值) |
| `expected_company_id` | string | 预期：公司ID | 614810477 |
| `expected_source` | string | 预期：命中来源 | yaml_p1, db_cache, temp_id |
| `expected_decision_path` | string | 预期：决策路径 | P1:HIT 或 P1:MISS→P2:MISS→DB:HIT |
| `actual_company_id` | string | 实际：程序输出 | (运行后填充) |
| `actual_source` | string | 实际：命中来源 | (运行后填充) |
| `actual_decision_path` | string | 实际：决策路径 | (运行后填充) |
| `pass_fail` | string | 通过/失败 | PASS / FAIL |
| `notes` | string | 备注 | 边缘案例说明 |

### 2.3 决策路径格式

详细的"尝试路径"格式：

```
# Layer 1 (YAML) 命中
P1:HIT
P1:MISS→P2:MISS→P3:MISS→P4:HIT

# Layer 2 (DB Cache - 增强版多优先级) 命中
P1:MISS→P2:MISS→P3:MISS→P4:MISS→P5:MISS→DB-P1:HIT
P1:MISS→P2:MISS→P3:MISS→P4:MISS→P5:MISS→DB-P1:MISS→DB-P2:MISS→DB-P3:HIT
P1:MISS→P2:MISS→P3:MISS→P4:MISS→P5:MISS→DB-P1:MISS→DB-P2:MISS→DB-P3:MISS→DB-P4:HIT

# Layer 3 (Existing Column) 命中
P1:MISS→...→P5:MISS→DB-P1:MISS→...→DB-P5:MISS→EXISTING:HIT

# Layer 5 (Temporary ID) 生成
P1:MISS→...→P5:MISS→DB-P1:MISS→...→DB-P5:MISS→EXISTING:MISS→EQC:SKIP→TEMP:GEN

# 简化格式 (用于报告)
YAML:P4:HIT
DB:P3:HIT
EXISTING:HIT
TEMP:GEN
```

---

## 3. 测试案例分类

### 3.1 Layer 1: YAML Configuration

| 类别 | 描述 | 最少案例数 |
|------|------|-----------|
| P1_PLAN_CODE_HIT | 计划代码直接命中 | 3 |
| P1_PLAN_CODE_MISS | 计划代码未命中 | 2 |
| P2_ACCOUNT_NAME_HIT | 年金账户名命中 | 3 |
| P3_ACCOUNT_NUMBER_HIT | 年金账户号命中 | 3 |
| P4_CUSTOMER_NAME_HIT | 客户名称命中 (normalized) | 3 |
| P4_CUSTOMER_NAME_NORM | 客户名称规范化测试 | 5 |
| P5_PLAN_CUSTOMER_HIT | 计划代码+客户名称组合命中 | 3 |
| YAML_PRIORITY_OVERRIDE | 高优先级覆盖低优先级 | 3 |

### 3.2 Layer 2: Database Cache (增强版 - 多优先级)

| 类别 | 描述 | 最少案例数 |
|------|------|-----------|
| DB_P1_PLAN_CODE_HIT | DB 计划代码命中 | 3 |
| DB_P1_PLAN_CODE_MISS | DB 计划代码未命中 | 2 |
| DB_P2_ACCOUNT_NAME_HIT | DB 年金账户名命中 | 3 |
| DB_P3_ACCOUNT_NUMBER_HIT | DB 年金账户号命中 | 3 |
| DB_P4_CUSTOMER_NAME_HIT | DB 客户名称命中 (normalized) | 3 |
| DB_P4_CUSTOMER_NAME_NORM | DB 客户名称规范化测试 | 3 |
| DB_P5_PLAN_CUSTOMER_HIT | DB 计划代码+客户名称组合命中 | 3 |
| DB_PRIORITY_OVERRIDE | DB 高优先级覆盖低优先级 | 3 |
| DB_CACHE_MISS_ALL | 所有 DB 优先级均未命中 | 2 |
| DB_SOURCE_CONFIDENCE | 不同 source 的 confidence 优先级 | 3 |

### 3.3 Layer 3: Existing Column + Backflow

| 类别 | 描述 | 最少案例数 |
|------|------|-----------|
| EXISTING_COLUMN_HIT | 已有公司代码直接使用 | 3 |
| EXISTING_COLUMN_INVALID | 已有公司代码无效 (IN_* 临时ID) | 2 |
| BACKFLOW_CANDIDATE | Backflow 候选记录 | 3 |

### 3.4 Layer 4: EQC Sync (需要 Mock)

| 类别 | 描述 | 最少案例数 |
|------|------|-----------|
| EQC_SYNC_HIT | EQC API 命中 (Mock) | 2 |
| EQC_BUDGET_EXHAUSTED | EQC 预算耗尽 | 2 |
| EQC_DISABLED | EQC 未启用 | 1 |

### 3.5 Layer 5: Temporary ID

| 类别 | 描述 | 最少案例数 |
|------|------|-----------|
| TEMP_ID_GENERATED | 临时 ID 生成 | 3 |
| TEMP_ID_DETERMINISTIC | 同一名称生成相同 ID | 2 |
| TEMP_ID_ASYNC_QUEUED | 异步队列入队 | 2 |

### 3.6 Domain Learning (自学习机制)

| 类别 | 描述 | 最少案例数 |
|------|------|-----------|
| DOMAIN_LEARNING_EXTRACT | 从 Domain 表提取有效映射 | 3 |
| DOMAIN_LEARNING_FILTER_TEMP | 过滤临时 ID (IN_*) | 2 |
| DOMAIN_LEARNING_MULTI_TYPE | 多 lookup_type 学习 | 5 |
| DOMAIN_LEARNING_CONFIDENCE | 学习数据 confidence 设置 | 3 |
| DOMAIN_LEARNING_CONFLICT | 冲突处理 (已存在映射) | 3 |
| DOMAIN_LEARNING_HIT | 学习后下次运行命中 | 3 |

### 3.7 Edge Cases (边缘案例)

| 类别 | 描述 | 最少案例数 |
|------|------|-----------|
| EMPTY_CUSTOMER_NAME | 客户名称为空 | 2 |
| WHITESPACE_HANDLING | 空格处理 | 3 |
| SPECIAL_CHARS | 特殊字符处理 | 3 |
| UNICODE_HANDLING | 中文字符处理 | 3 |
| FULL_WIDTH_CHARS | 全角/半角字符 | 2 |

---

## 4. 验证脚本设计

### 4.1 架构选择：独立验证脚本

**选择理由**：
1. 不修改生产代码，避免引入 bug
2. 测试与生产分离，符合最佳实践
3. 灵活性高，可以添加更多验证逻辑
4. 渐进式开发，不需要一次性完成

### 4.2 脚本结构

```
scripts/
└── validate_enrichment/
    ├── __init__.py
    ├── validator.py          # EnrichmentValidator 类
    ├── csv_handler.py        # CSV 读写处理
    ├── report_generator.py   # 验证报告生成
    └── run_validation.py     # 主入口脚本
```

### 4.3 核心类设计

```python
# scripts/validate_enrichment/validator.py

from dataclasses import dataclass
from typing import Optional, List

@dataclass
class ValidationResult:
    """单个测试案例的验证结果"""
    test_id: str
    company_id: Optional[str]
    source: str
    decision_path: str
    passed: bool
    error_message: Optional[str] = None

class EnrichmentValidator:
    """
    独立的企业客户识别验证器

    不修改生产代码，通过逐层调用解析逻辑记录决策路径
    """

    def __init__(
        self,
        yaml_overrides: dict,
        db_connection: Optional[Connection] = None,
        eqc_enabled: bool = False,
    ):
        self.yaml_overrides = yaml_overrides
        self.db_connection = db_connection
        self.eqc_enabled = eqc_enabled

    def validate_single(self, test_case: dict) -> ValidationResult:
        """
        逐层验证单个测试案例，记录完整决策路径
        """
        decision_path = []

        # Layer 1: YAML 配置检查 (P1-P5)
        for priority in ["P1", "P2", "P3", "P4", "P5"]:
            result = self._check_yaml_layer(test_case, priority)
            decision_path.append(f"{priority}:{result.status}")
            if result.hit:
                return ValidationResult(
                    test_id=test_case["test_id"],
                    company_id=result.company_id,
                    source=f"yaml_{priority.lower()}",
                    decision_path="→".join(decision_path),
                    passed=True
                )

        # Layer 2: DB Cache 检查 (增强版 - 多优先级)
        if self.db_connection:
            for db_priority in ["DB-P1", "DB-P2", "DB-P3", "DB-P4", "DB-P5"]:
                result = self._check_db_cache_layer(test_case, db_priority)
                decision_path.append(f"{db_priority}:{result.status}")
                if result.hit:
                    return ValidationResult(
                        test_id=test_case["test_id"],
                        company_id=result.company_id,
                        source=f"db_{db_priority.lower()}",
                        decision_path="→".join(decision_path),
                        passed=True
                    )
        else:
            decision_path.append("DB:SKIP")

        # Layer 3: Existing Column 检查
        result = self._check_existing_column(test_case)
        decision_path.append(f"EXISTING:{result.status}")
        if result.hit:
            return ValidationResult(...)

        # Layer 4: EQC Sync (通常跳过)
        decision_path.append("EQC:SKIP")

        # Layer 5: Temporary ID 生成
        temp_id = self._generate_temp_id(test_case)
        decision_path.append("TEMP:GEN")

        return ValidationResult(
            test_id=test_case["test_id"],
            company_id=temp_id,
            source="temp_id",
            decision_path="→".join(decision_path),
            passed=True
        )

    def validate_batch(self, test_cases: List[dict]) -> List[ValidationResult]:
        """批量验证测试案例"""
        return [self.validate_single(tc) for tc in test_cases]
```

### 4.4 使用方式

```bash
# 运行验证
uv run python -m scripts.validate_enrichment.run_validation \
    --input tests/fixtures/enrichment_golden_dataset.csv \
    --output reports/enrichment_validation_report.csv

# 仅验证 YAML 层 (不需要数据库)
uv run python -m scripts.validate_enrichment.run_validation \
    --input tests/fixtures/enrichment_golden_dataset.csv \
    --yaml-only

# 生成 HTML 报告
uv run python -m scripts.validate_enrichment.run_validation \
    --input tests/fixtures/enrichment_golden_dataset.csv \
    --format html
```

---

## 5. Legacy 数据迁移计划

### 5.1 数据源

| 表 | 数据量 | 位置 |
|----|--------|------|
| `legacy.company_id_mapping` | ~19,141 行 | `reference/archive/db_migration/sqls/enterprise/company_id_mapping_converted.sql` |
| `legacy.eqc_search_result` | ~11,820 行 | `reference/archive/db_migration/sqls/enterprise/eqc_search_result_converted.sql` |

### 5.2 目标表

```sql
enterprise.company_name_index (
    normalized_name VARCHAR(255) PRIMARY KEY,
    company_id VARCHAR(50) NOT NULL,
    match_type VARCHAR(20),
    confidence DECIMAL(3,2),
    source VARCHAR(50),
    created_at TIMESTAMP
)
```

### 5.3 迁移规则

1. **company_id_mapping 迁移**：
   - `company_name` → 规范化后作为 `normalized_name`
   - `company_id` → `company_id`
   - `type='current'` 优先于 `type='former'`
   - `match_type` = 'legacy_mapping'
   - `confidence` = 1.00 (current) / 0.90 (former)
   - `source` = 'legacy_migration'

2. **eqc_search_result 迁移**：
   - `key_word` → 规范化后作为 `normalized_name`
   - `company_id` → `company_id`
   - 仅迁移 `result='Success'` 的记录
   - `match_type` = 'eqc_api'
   - `confidence` = 1.00
   - `source` = 'legacy_eqc'

3. **去重规则**：
   - 同一 `normalized_name` 保留最高 confidence 的记录
   - 如果 confidence 相同，优先保留 `source='legacy_mapping'`

### 5.4 Alembic 迁移脚本

```python
# io/schema/migrations/versions/YYYYMMDD_HHMM_migrate_legacy_company_mappings.py

"""Migrate legacy company mappings to enterprise.company_name_index

Revision ID: YYYYMMDD_HHMM
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # 1. 从 company_id_mapping 迁移 (current 类型)
    op.execute("""
        INSERT INTO enterprise.company_name_index
            (normalized_name, company_id, match_type, confidence, source, created_at)
        SELECT
            LOWER(TRIM(company_name)) as normalized_name,
            company_id,
            'legacy_mapping' as match_type,
            1.00 as confidence,
            'legacy_migration' as source,
            NOW() as created_at
        FROM legacy.company_id_mapping
        WHERE type = 'current'
        ON CONFLICT (normalized_name) DO NOTHING
    """)

    # 2. 从 company_id_mapping 迁移 (former 类型，较低优先级)
    op.execute("""
        INSERT INTO enterprise.company_name_index
            (normalized_name, company_id, match_type, confidence, source, created_at)
        SELECT
            LOWER(TRIM(company_name)) as normalized_name,
            company_id,
            'legacy_mapping' as match_type,
            0.90 as confidence,
            'legacy_migration' as source,
            NOW() as created_at
        FROM legacy.company_id_mapping
        WHERE type = 'former'
        ON CONFLICT (normalized_name) DO NOTHING
    """)

    # 3. 从 eqc_search_result 迁移
    op.execute("""
        INSERT INTO enterprise.company_name_index
            (normalized_name, company_id, match_type, confidence, source, created_at)
        SELECT
            LOWER(TRIM(key_word)) as normalized_name,
            company_id,
            'eqc_api' as match_type,
            1.00 as confidence,
            'legacy_eqc' as source,
            NOW() as created_at
        FROM legacy.eqc_search_result
        WHERE result = 'Success' AND company_id IS NOT NULL
        ON CONFLICT (normalized_name) DO NOTHING
    """)

def downgrade():
    op.execute("""
        DELETE FROM enterprise.company_name_index
        WHERE source IN ('legacy_migration', 'legacy_eqc')
    """)
```

---

## 6. 实施计划

### 阶段 1：基础框架 (建议作为 Story)

| 任务 | 描述 | 优先级 |
|------|------|--------|
| 1.1 | 创建 Golden Dataset CSV 模板 | P0 |
| 1.2 | 设计初始测试案例 (YAML 层) | P0 |
| 1.3 | 创建 EnrichmentValidator 基础类 | P0 |
| 1.4 | 实现 YAML 层验证逻辑 | P0 |

### 阶段 2：Legacy 迁移 (建议作为 Story)

| 任务 | 描述 | 优先级 |
|------|------|--------|
| 2.1 | 创建 Alembic 迁移脚本 | P0 |
| 2.2 | 数据清洗和规范化 | P0 |
| 2.3 | 执行迁移并验证 | P0 |
| 2.4 | 添加 DB Cache 层测试案例 | P1 |

### 阶段 3：完整验证 (建议作为 Story)

| 任务 | 描述 | 优先级 |
|------|------|--------|
| 3.1 | 实现所有层的验证逻辑 | P1 |
| 3.2 | 添加边缘案例 | P1 |
| 3.3 | 生成验证报告 | P1 |
| 3.4 | CI/CD 集成 | P2 |

---

## 7. 预期成果

1. **Golden Dataset CSV** - `tests/fixtures/enrichment_golden_dataset.csv`
   - 50+ 测试案例
   - 覆盖所有解析层和边缘情况

2. **验证脚本** - `scripts/validate_enrichment/`
   - 独立于生产代码
   - 输出详细决策路径
   - 生成验证报告

3. **Legacy 数据迁移** - ~30,000 条初始缓存数据
   - Layer 2 (DB Cache) 立即可用
   - 显著提高缓存命中率

4. **技术文档** - `docs/guides/company-enrichment-service.md`
   - 完整的架构说明
   - 运维手册
   - 测试验证章节

---

## 8. 相关文档

- 技术文档: `docs/guides/company-enrichment-service.md`
- Layer 2 增强设计: `docs/specific/company-enrichment-service/layer2-enrichment-index-enhancement.md`
- Epic 定义: `docs/epics/epic-6-company-enrichment-service.md`
- Story 文件: `docs/sprint-artifacts/stories/6-*.md`
- Legacy 数据: `reference/archive/db_migration/sqls/enterprise/`

---

## 变更历史

| 日期 | 版本 | 变更内容 | 作者 |
|------|------|----------|------|
| 2025-12-08 | 0.1 | 初始规划，Epic 6 回顾讨论产出 | Epic 6 Retrospective |
| 2025-12-08 | 0.2 | 同步 Layer 2 多优先级增强设计 (DB-P1 to DB-P5)，新增 Domain Learning 测试类别 | Layer 2 Enhancement |
