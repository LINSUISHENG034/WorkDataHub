# Sprint Change Proposal: EQC API Full Coverage & Legacy Schema Alignment

**Date:** 2025-12-14
**Author:** Correct-Course Workflow
**Status:** Pending Approval
**Triggered By:** Story 6.2-P5 Validation Gap Analysis

---

## 1. Issue Summary

### Problem Statement

Story 6.2-P5 (EQC Data Persistence & Legacy Table Integration) 实际验证发现与 Legacy System (`legacy/annuity_hub/crawler/run.py`) 存在功能 Gap：

1. **API 覆盖不完整**
   - 当前: 只实现 `/api/search/?key=` (base_info 查询)
   - 缺失: `/api/search/findDepart?targetId=` (business_info)
   - 缺失: `/api/search/findLabels?targetId=` (biz_label)

2. **base_info 字段不完整**
   - 当前 `enterprise.base_info`: 6 列
   - Legacy `enterprise.archive_base_info`: 37 列
   - 缺失大量元数据字段

3. **原始数据追溯能力缺失**
   - 无法保存 `findDepart` 和 `findLabels` 的原始 API 响应
   - 无法追溯数据来源和获取时间

### Discovery Context

- **发现时间:** Story 6.2-P5 完成后进行 Legacy 功能对比验证
- **发现方式:** 对比 `legacy/annuity_hub/crawler/eqc_crawler.py` 与当前实现
- **影响范围:** Epic 6.2 数据完整性，Epic 7 Golden Dataset 测试准备

### Evidence

| 对比项 | 当前实现 | Legacy System | Gap |
|-------|---------|---------------|-----|
| API 端点 | 1 个 (search) | 3 个 (search + findDepart + findLabels) | 2 个缺失 |
| base_info 列数 | 6 列 | 37 列 (archive_base_info) | 31 列缺失 |
| 原始数据存储 | raw_data (search 响应) | MongoDB 完整存储 | 2 个 API 响应未存储 |

---

## 2. Impact Analysis

### Epic Impact

| Epic | 状态 | 影响 |
|------|------|------|
| Epic 6.2 | done | 需追加 3 个 Patch Story (P7/P8/P9) |
| Epic 6.2-P6 | in-progress | 无直接影响 (CLI 架构独立) |
| Epic 7 | backlog | 依赖完整数据结构进行 Golden Dataset 测试 |

### Artifact Conflicts

| Artifact | 变更类型 | 具体内容 |
|----------|---------|---------|
| Migration | 重构 | `20251206_000001_create_enterprise_schema.py` |
| EQCClient | 新增 | `get_business_info()`, `get_label_info()` 方法 |
| EqcProvider | 更新 | 集成新 API 调用和数据持久化 |
| Cleansing Rules | 更新 | `business_info` 规范化转换规则 |
| Story 文档 | 新建 | 3 个 Patch Story 文档 |
| Sprint Status | 更新 | 添加 P7/P8/P9 条目 |

### Technical Impact

- **数据库:** 重构 `base_info`/`business_info`/`biz_label` 表结构
- **代码:** EQCClient 和 EqcProvider 扩展
- **配置:** 清洗规则配置更新
- **测试:** 新增单元测试和集成测试

---

## 3. Recommended Approach

### Selected Path: Direct Adjustment

在 Epic 6.2 下新增 3 个 Patch Story，分阶段实现完整功能。

### Rationale

1. **项目尚未部署** - 可直接重构 migration 清理技术债务
2. **变更范围可控** - 不影响 MVP 时间线
3. **Legacy 对齐** - 完整对齐 Legacy 功能，为 Epic 7 测试做准备
4. **架构一致性** - 删除 `company_master` 减少冗余

### Trade-offs Considered

| 方案 | 优点 | 缺点 | 决策 |
|-----|------|------|------|
| 新增 migration 扩展字段 | 保持历史 | 产生冗余 migration | 不采用 |
| 重构现有 migration | 清洁架构 | 需重建表 | **采用** |
| 新增独立 Epic | 完整隔离 | 过度工程 | 不采用 |

---

## 4. Detailed Change Proposals

### Story 6.2-P7: Enterprise Schema Consolidation

**聚焦:** 数据库 Schema 重构

**Scope:**
- 重构 `20251206_000001_create_enterprise_schema.py`
- 删除 `company_master` 表 (已弃用)
- 新建完整 `base_info` 表 (对齐 `archive_base_info` 37 列 + 新增字段)
- 新建规范化 `business_info` 表 (重新设计字段格式)
- 新建 `biz_label` 表

**Schema Changes:**

```sql
-- base_info: 对齐 archive_base_info + 新增字段
CREATE TABLE enterprise.base_info (
    company_id VARCHAR(255) PRIMARY KEY,
    search_key_word VARCHAR(255),
    -- 对齐 archive_base_info 的 37 列
    name VARCHAR(255),
    name_display VARCHAR(255),
    symbol VARCHAR(255),
    rank_score DOUBLE PRECISION,
    country VARCHAR(255),
    company_en_name VARCHAR(255),
    smdb_code VARCHAR(255),
    is_hk INTEGER,
    coname VARCHAR(255),
    is_list INTEGER,
    company_nature VARCHAR(255),
    _score DOUBLE PRECISION,
    type VARCHAR(255),
    registeredStatus VARCHAR(255),
    organization_code VARCHAR(255),
    le_rep TEXT,
    reg_cap DOUBLE PRECISION,
    is_pa_relatedparty INTEGER,
    province VARCHAR(255),
    companyFullName VARCHAR(255),
    est_date VARCHAR(255),
    company_short_name VARCHAR(255),
    id VARCHAR(255),
    is_debt INTEGER,
    unite_code VARCHAR(255),
    registered_status VARCHAR(255),
    cocode VARCHAR(255),
    default_score DOUBLE PRECISION,
    company_former_name VARCHAR(255),
    is_rank_list INTEGER,
    trade_register_code VARCHAR(255),
    companyId VARCHAR(255),
    is_normal INTEGER,
    company_full_name VARCHAR(255),
    -- 新增字段
    raw_data JSONB,                    -- 原始 search 响应
    raw_business_info JSONB,           -- 原始 findDepart 响应
    raw_biz_label JSONB,               -- 原始 findLabels 响应
    api_fetched_at TIMESTAMP WITH TIME ZONE,  -- API 获取时间
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- business_info: 规范化字段格式
CREATE TABLE enterprise.business_info (
    company_id VARCHAR(255) PRIMARY KEY REFERENCES enterprise.base_info(company_id),
    registered_date DATE,              -- 规范化为 DATE 类型
    registered_capital NUMERIC(20,2),  -- 规范化为 NUMERIC (单位: 元)
    registered_status VARCHAR(100),
    legal_person_name VARCHAR(255),
    address TEXT,
    company_name VARCHAR(255),
    credit_code VARCHAR(50),
    company_type VARCHAR(100),
    industry_name VARCHAR(255),
    business_scope TEXT,
    _cleansing_status JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- biz_label: 标签表
CREATE TABLE enterprise.biz_label (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(255) NOT NULL REFERENCES enterprise.base_info(company_id),
    type VARCHAR(100),
    lv1_name VARCHAR(255),
    lv2_name VARCHAR(255),
    lv3_name VARCHAR(255),
    lv4_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_biz_label_company_id ON enterprise.biz_label(company_id);
```

**Dependencies:** None
**Effort:** Medium

---

### Story 6.2-P8: EQC Full Data Acquisition

**聚焦:** API 客户端扩展

**Scope:**
- `EQCClient` 新增 `get_business_info(company_id)` 方法
- `EQCClient` 新增 `get_label_info(company_id)` 方法
- 新增 `*_with_raw()` 变体返回原始 JSON
- `EqcProvider` 一次性调用 3 个 API
- 原始响应存入 `base_info` 的 JSONB 字段

**API Endpoints:**

| API | URL | 响应字段 | 存储位置 |
|-----|-----|---------|---------|
| search | `/api/search/?key={keyword}` | `list[0]` | `base_info.*` + `raw_data` |
| findDepart | `/api/search/findDepart?targetId={company_id}` | `businessInfodto` | `base_info.raw_business_info` |
| findLabels | `/api/search/findLabels?targetId={company_id}` | `labels` | `base_info.raw_biz_label` |

**Code Changes:**

```python
# EQCClient 新增方法
class EQCClient:
    def get_business_info(self, company_id: str) -> Optional[BusinessInfoResult]:
        """调用 findDepart API 获取业务信息"""
        ...

    def get_business_info_with_raw(self, company_id: str) -> Tuple[Optional[BusinessInfoResult], dict]:
        """调用 findDepart API，返回解析结果和原始 JSON"""
        ...

    def get_label_info(self, company_id: str) -> List[LabelInfo]:
        """调用 findLabels API 获取标签信息"""
        ...

    def get_label_info_with_raw(self, company_id: str) -> Tuple[List[LabelInfo], dict]:
        """调用 findLabels API，返回解析结果和原始 JSON"""
        ...
```

**Dependencies:** Story 6.2-P7 (Schema)
**Effort:** Low-Medium

---

### Story 6.2-P9: Raw Data Cleansing & Transformation

**聚焦:** 数据清洗和派生表填充

**Scope:**
- 从 `base_info.raw_business_info` 清洗转换到 `business_info` 表
- 从 `base_info.raw_biz_label` 解析到 `biz_label` 表
- 清洗规则配置
- CLI 支持批量清洗

**Data Flow:**

```
base_info.raw_business_info (JSONB)
    │
    ▼ 清洗转换 (CleansingRuleEngine)
business_info (规范化表)
    - "80000.00万元" → 800000000 (NUMERIC)
    - "2015-01-15" → 2015-01-15 (DATE)

base_info.raw_biz_label (JSONB)
    │
    ▼ 解析展开
biz_label (标签表)
    - 每个标签一行记录
```

**Cleansing Rules (cleansing_rules.yml):**

```yaml
eqc_business_info:
  registered_capital:
    - rule: extract_chinese_currency
      description: "80000.00万元" → 800000000
  registered_date:
    - rule: parse_date
      formats: ["%Y-%m-%d", "%Y年%m月%d日", "%Y/%m/%d"]
  # ... 其他字段规则
```

**CLI Commands:**

```bash
# 批量清洗 business_info
PYTHONPATH=src uv run python -m work_data_hub.cli.cleanse_data \
  --table business_info --domain eqc_business_info --batch-size 1000

# 批量解析 biz_label
PYTHONPATH=src uv run python -m work_data_hub.cli.cleanse_data \
  --table biz_label --source-field raw_biz_label --batch-size 1000
```

**Dependencies:** Story 6.2-P7, Story 6.2-P8
**Effort:** Medium

---

## 5. Implementation Handoff

### Change Scope Classification: Minor

可由开发团队直接实施，无需 PM/Architect 介入。

### Handoff Plan

| 角色 | 职责 |
|-----|------|
| **SM Agent** | 创建 Story 文档 (P7/P8/P9)，更新 Sprint Status |
| **Dev Agent** | 实施所有技术任务 |
| **Code Review** | 审查 migration 重构和 API 集成代码 |

### Implementation Sequence

```
6.2-P7 (Schema) ──> 6.2-P8 (API) ──> 6.2-P9 (Cleansing)
     │                   │                  │
     ▼                   ▼                  ▼
  Migration          EQCClient          CleansingRules
  重构               扩展               配置
```

### Success Criteria

- [ ] `base_info` 表对齐 `archive_base_info` 完整字段
- [ ] `company_master` 表已删除
- [ ] `findDepart` 和 `findLabels` API 调用正常
- [ ] 原始响应存入 `raw_business_info` 和 `raw_biz_label`
- [ ] `business_info` 数据规范化转换正确
- [ ] `biz_label` 标签解析正确
- [ ] 单元测试和集成测试通过

---

## Test Plan

- [ ] 验证 migration 重构后表结构正确
- [ ] 验证 EQCClient 新 API 方法返回正确数据
- [ ] 验证 EqcProvider 一次性获取并存储所有数据
- [ ] 验证清洗规则正确转换数据格式
- [ ] 验证 CLI 批量清洗功能
- [ ] 运行现有测试确保无回归

---

## References

- Story 6.2-P5: `docs/sprint-artifacts/stories/6.2-p5-eqc-data-persistence-legacy-integration.md`
- Legacy Crawler: `legacy/annuity_hub/crawler/eqc_crawler.py`
- Archive Schema: `enterprise.archive_base_info` (PostgreSQL)
- Epic 6: `docs/epics/epic-6-company-enrichment-service.md`

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
