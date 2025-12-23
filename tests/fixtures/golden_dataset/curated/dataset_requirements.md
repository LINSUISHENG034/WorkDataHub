# Annuity Performance Golden Dataset Requirements & Plan (Epic 4/5/6)

## 1. Project Goal
Create a curated, small-scale "Golden Dataset" to validate the **Annuity Performance Domain Migration (Epic 4)** and **Infrastructure Layer (Epic 5/6)**. This dataset serves as the ground truth for:
1.  **New Pipeline Validation**: Verifying Bronze (Schema), Silver (Transform), and Gold (Projection) layers.
2.  **Parity Testing (Epic 6)**: Ensuring 100% output alignment with the Legacy System.
3.  **Complex Logic Verification**: Covering all data cleansing, enrichment, and business logic edge cases.
4.  **End-to-End Workflow Validation**: Testing file discovery, version detection, reference sync, and observability.
5.  **Company ID Resolution**: Validating the complete 5-step hierarchical resolution strategy with YAML overrides, DB cache, EQC lookup, and temp ID generation.

## 1.1 Data Source Principle (Critical)

> ⚠️ **CRITICAL REQUIREMENT**: Golden Dataset 必须从真实生产数据中筛选，**禁止使用模拟数据**。

### 1.1.1 为什么必须使用真实数据？

| 原因 | 说明 |
|------|------|
| **Parity 验证** | 只有真实数据才能与 Legacy System 的真实处理结果进行对齐分析 |
| **边界条件覆盖** | 真实数据包含实际业务中的边界情况和异常值 |
| **数据分布真实性** | 模拟数据无法准确反映真实的数据分布和关联关系 |
| **Company ID 映射** | 真实的 company_id 映射关系只存在于生产数据中 |

### 1.1.2 真实数据来源

**Source File (Authoritative)**:
```
tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集/V{n}/
└── 【for年金机构经营分析】{YY}年{MM}月年金规模收入数据*.xlsx
```

**当前可用数据**:
- `tests/fixtures/real_data/202510/收集数据/数据采集/V2/【for年金机构经营分析】25年10月年金规模收入数据 1111.xlsx`
- `tests/fixtures/real_data/202411/收集数据/数据采集/V1/24年11月年金终稿数据.xlsx`

### 1.1.3 数据筛选方法

Golden Dataset 的创建流程：

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: 从真实数据文件中识别符合测试场景的行                      │
│  ↓                                                              │
│  Step 2: 记录行号和原始数据（保持数据完整性）                      │
│  ↓                                                              │
│  Step 3: 同时通过 Legacy System 处理相同数据                      │
│  ↓                                                              │
│  Step 4: 记录 Legacy 输出作为 expected output                    │
│  ↓                                                              │
│  Step 5: 将筛选的行复制到 Golden Dataset Excel 文件               │
└─────────────────────────────────────────────────────────────────┘
```

**筛选脚本**:
```bash
# 从真实数据中筛选符合场景的行
PYTHONPATH=src uv run python scripts/tools/curate_golden_dataset.py \
  --source tests/fixtures/real_data/202510/收集数据/数据采集/V2/*.xlsx \
  --scenarios BZ-001,BZ-002,SV-ENR-01,... \
  --output tests/fixtures/golden_dataset/curated/
```

### 1.1.4 数据筛选标准

| 场景类型 | 筛选标准 | 示例 |
|----------|----------|------|
| BZ-002 (货币格式) | 查找 `期末资产规模` 列包含 "¥" 或 "," 的行 | 原始行 #15 |
| SV-ENR-01 (YAML Override) | 查找 `计划代码` = "FP0001" 的行 | 原始行 #42 |
| SV-NAME-01 (名称清洗) | 查找 `客户名称` 包含 "已转出" 的行 | 原始行 #78 |
| BIZ-03 (职年业务) | 查找 `业务类型` = "职年受托" 的行 | 原始行 #156 |

### 1.1.5 Manifest 文件格式 (Enhanced)

`dataset_manifest.csv` 必须记录原始数据来源：

| ID | Source File | Original Row | Golden Row | Scenario Tag | Legacy Output | Notes |
|----|-------------|--------------|------------|--------------|---------------|-------|
| 1 | 202510/V2/*.xlsx | 15 | 2 | BZ-002 | 1234.56 | 货币格式转换 |
| 2 | 202510/V2/*.xlsx | 42 | 11 | SV-ENR-01 | 614810477 | YAML override |

**Required Columns**:
- `Source File`: 原始数据文件路径
- `Original Row`: 在原始文件中的行号
- `Golden Row`: 在 Golden Dataset 中的行号
- `Legacy Output`: Legacy System 对该行的处理结果

## 2. Directory Structure Strategy
The dataset must mirror the **Epic 3 File Discovery** directory structure to validate version detection and folder scanning.

*   **Fixture Root**: `tests/fixtures/golden_dataset/`
*   **Structure Pattern**: `real_data/{YYYYMM}/收集数据/数据采集/V{n}/`
*   **Configuration Reference**: `config/data_sources.yml` (domain: `annuity_performance`)

**Action**: Place curated Excel files in the following hierarchy to test versioning strategies:
```text
tests/fixtures/golden_dataset/
├── real_data/
│   └── 202510/
│       └── 收集数据/
│           └── 数据采集/
│               ├── V1/ (Ignored - Lower Version)
│               │   └── 25年10月年金终稿数据.xlsx
│               └── V2/ (Selected - Highest Version)
│                   └── 25年10月年金终稿数据.xlsx
├── reference_data/           # Reference tables for enrichment testing
│   ├── enrichment_index.csv  # Pre-populated company mappings
│   ├── yaml_overrides.yml    # YAML priority overrides for testing
│   └── legacy_snapshot.json  # Legacy system output for parity
└── expected_outputs/         # Expected pipeline outputs
    ├── bronze_output.csv
    ├── silver_output.csv
    └── gold_output.csv
```

### 2.1 File Discovery Validation Scenarios (Epic 3)

| ID | Scenario | Test Configuration | Expected Behavior |
|----|----------|-------------------|-------------------|
| FD-001 | Version Selection | V1, V2 folders present | Select V2 (highest_number strategy) |
| FD-002 | Pattern Matching | `*年金终稿*.xlsx` | Match exactly 1 file per version |
| FD-003 | Exclude Patterns | `~$*.xlsx`, `*回复*` | Exclude temp and reply files |
| FD-004 | Sheet Selection | Multiple sheets | Load only `规模明细` sheet |
| FD-005 | Fallback Behavior | Ambiguous versions | Error (fallback: "error") |

### 2.2 Reference Data File Schemas

#### 2.2.1 enrichment_index.csv
Pre-populated company mappings for DB cache testing (SV-ENR-03/04/05).

```csv
lookup_type,lookup_key,company_id,company_name,priority,source,created_at
P1,P0290,123456789,测试公司A,1,migration,2025-10-01
P1,P0291,234567890,测试公司B,1,migration,2025-10-01
P4,中国石油天然气集团公司,987654321,中国石油天然气集团公司,4,migration,2025-10-01
P5,某公司年金账户,456789012,某公司,5,migration,2025-10-01
```

**Required Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `lookup_type` | string | P1 (plan_code), P2 (account_name), P3 (account_number), P4 (customer_name), P5 (plan_customer) |
| `lookup_key` | string | The key used for lookup (normalized for P4) |
| `company_id` | string | Resolved company ID |
| `company_name` | string | Company name for reference |
| `priority` | int | Priority level (1-5) |
| `source` | string | Data source identifier |

#### 2.2.2 yaml_overrides.yml
YAML priority overrides for testing (SV-ENR-01/02).

```yaml
# Priority 1: Plan code overrides
plan:
  FP0001: "614810477"
  FP0002: "614810477"

# Priority 2: Account number overrides
account: {}

# Priority 3: Hardcode overrides (special cases)
hardcode:
  P0809: "608349737"
  P0810: "608349738"

# Priority 4: Customer name overrides
name: {}

# Priority 5: Account name overrides
account_name: {}
```

#### 2.2.3 legacy_snapshot.json
Legacy system output for parity testing.

```json
{
  "metadata": {
    "source_table": "business.规模明细",
    "reporting_month": "202510",
    "exported_at": "2025-10-15T10:00:00Z",
    "row_count": 23
  },
  "rows": [
    {
      "月度": "2025-10-01",
      "计划代码": "P0290",
      "客户名称": "测试公司A",
      "company_id": "123456789",
      "期末资产规模": 1000000.00,
      "..."
    }
  ]
}
```

### 2.3 Dataset Versioning

**Naming Convention**: `golden_dataset_v{MAJOR}.{MINOR}/`
- **MAJOR**: Breaking changes (schema changes, removed scenarios)
- **MINOR**: Additive changes (new scenarios, bug fixes)

**Version History**: `tests/fixtures/golden_dataset/CHANGELOG.md`

```markdown
## [2.0.0] - 2025-01-15
### Added
- Company ID resolution scenarios (SV-ENR-01 to SV-ENR-09)
- Reference data backfill scenarios (REF-001 to REF-005)

## [1.0.0] - 2025-01-01
### Initial Release
- Bronze/Silver/Gold layer scenarios
- Basic cleansing rule coverage
```

**Backward Compatibility**: Tests must pass on both v1.x and v2.x datasets when applicable.

## 3. Data Selection Criteria (Layer-Based Scenarios)

The dataset must include specific rows to exercise each layer of the new architecture. **Every scenario below represents a specific requirement from the data cleansing specifications.**

### 3.1 Bronze Layer Scenarios (Story 4.2)
*Goal: Validate raw data ingestion and schema enforcement (Pandera).*

*   **[BZ-001] Happy Path**: Row with all required columns valid and correctly typed.
*   **[BZ-002] Numeric Coercion**:
    *   Currency format: `"¥1,234.56"` -> `1234.56`.
    *   Percentage: `"5.5%"` -> `0.055`.
*   **[BZ-003] Date Parsing (Loose)**:
    *   String format: `"202510"`.
    *   Excel serial date.
*   **[BZ-004] Missing Optional Fields**: Row with null `客户名称` (should pass Bronze, might fail later).
*   **[BZ-ERR-01] Missing Required Column**: (Negative Test) File missing `期末资产规模`.
*   **[BZ-ERR-02] Unparseable Types**: Row where `期末资产规模` is "Unknown".

### 3.2 Silver Layer Scenarios (Story 4.3)
*Goal: Validate transformation, cleansing, and enrichment logic. Based on 'tests/fixtures/golden_dataset/sample/样本数据集需求文档.md'.*

#### 3.2.1 Data Cleansing (Standardization)
*   **[SV-DATE] Date Standardization (Story 2.4)**:
    *   `DATE-001`: `"202510"` -> `2025-10-01`.
    *   `DATE-004`: `"2025年10月"` -> `2025-10-01`.
*   **[SV-PLAN] Plan Code Cleansing**:
    *   `PC-001`: Prefix removal ("1P0290" -> "P0290").
    *   `PC-002`: Null plan code + "集合计划" -> "AN001".
    *   `PC-003`: Null plan code + "单一计划" -> "AN002".
    *   `PC-005`: Trim whitespace (" P0290 " -> "P0290").
*   **[SV-ORG] Organization Code Cleansing**:
    *   `ORG-001/002`: Null/Empty -> "G00".
    *   `ORG-007`: Mapping verification ("北京" -> "G01").
*   **[SV-PORT] Portfolio Code Cleansing**:
    *   `PORT-001`: Prefix removal ("F123456" -> "123456").
    *   `PORT-002/003`: Null + "职年" business type -> "QTAN003".
*   **[SV-GCN] Group Customer Number Cleansing**:
    *   `GCN-001`: Prefix removal ("C123456" -> "123456").
    *   `GCN-005`: Length validation/cleanup.

#### 3.2.2 Company Name Normalization (Critical)
*   **[SV-NAME-01] Invalid String Removal**:
    *   Keywords: "已转出", "待转出", "终止", "保留", "存量" (e.g., "Company(已转出)" -> "Company").
*   **[SV-NAME-02] Bracket Normalization**:
    *   Full/Half width: "Company(Group)" -> "Company（Group）".
    *   Suffix handling: "Company（集团）" -> "Company".
*   **[SV-NAME-03] Suffix Removal**:
    *   "-养老", "-福利", "及下属子企业" -> Removed.

#### 3.2.3 Company ID Enrichment (Epic 5/6 Integration)
*Goal: Validate the complete 5-step hierarchical resolution strategy.*

**Resolution Priority Order** (per `CompanyIdResolver`):

| Step | Source | Lookup Key | Notes |
|------|--------|------------|-------|
| 1 | YAML Overrides | 5 priority levels: plan → account → hardcode → name → account_name | Static config-based |
| 2 | Database Cache | `enterprise.enrichment_index` (P1-P5 lookup types) | Batch-optimized SQL |
| 3 | Existing Column | Passthrough + backflow to DB | Preserves pre-resolved IDs |
| 4 | EQC Sync Lookup | External API (budgeted) | Cached to DB after lookup |
| 5 | Temp ID Generation | HMAC-SHA1 based | Format: `IN<16-char-Base32>` |

**Test Scenarios:**

*   **[SV-ENR-01] YAML Override - Plan Code**:
    *   Input: `计划代码` = "FP0001"
    *   Expected: `company_id` = "614810477" (from YAML plan priority)
*   **[SV-ENR-02] YAML Override - Hardcode**:
    *   Input: `计划代码` = "P0809"
    *   Expected: `company_id` = "608349737" (from YAML hardcode priority)
*   **[SV-ENR-03] DB Cache - Plan Code (P1)**:
    *   Input: `计划代码` = "P0290" (exists in enrichment_index)
    *   Expected: Resolved via DB-P1 path
*   **[SV-ENR-04] DB Cache - Customer Name (P4)**:
    *   Input: `客户名称` = "中国石油天然气集团公司" (normalized lookup)
    *   Expected: Resolved via DB-P4 path with normalization
*   **[SV-ENR-05] DB Cache - Account Name (P5)**:
    *   Input: `年金账户名` = "某公司年金账户" (RAW lookup)
    *   Expected: Resolved via DB-P5 path
*   **[SV-ENR-06] Existing Column Passthrough**:
    *   Input: Row with pre-populated `company_id` column
    *   Expected: Passthrough preserved, backflow to DB triggered
*   **[SV-ENR-07] EQC Sync Lookup**:
    *   Input: Unknown company name within budget
    *   Expected: EQC API called, result cached to DB
*   **[SV-ENR-08] Temp ID Generation**:
    *   Input: Completely unknown company name, budget exhausted
    *   Expected: `company_id` = "INXXXXXXXXXXXXXXXX" (deterministic HMAC-SHA1)
*   **[SV-ENR-09] Temp ID Determinism**:
    *   Input: Same company name processed twice
    *   Expected: Identical temp ID generated (same salt)

#### 3.2.3.1 EQC Lookup Testing Strategy

Since SV-ENR-07 depends on external EQC API, use the following testing strategies:

| Test Type | Strategy | Configuration |
|-----------|----------|---------------|
| **Unit Test** | Mock `EqcProvider.lookup()` | Return predefined `company_id` for specific names |
| **Integration Test** | Use test EQC endpoint | Set `EQC_BASE_URL` to sandbox environment |
| **E2E Test** | Conditional execution | Skip if `ENABLE_EQC_INTEGRATION=false`, use temp ID fallback |

**Mock Example (pytest):**
```python
@pytest.fixture
def mock_eqc_provider(mocker):
    mock = mocker.patch('work_data_hub.infrastructure.enrichment.eqc_provider.EqcProvider')
    mock.return_value.lookup.return_value = EqcResult(company_id="999888777", company_name="Mock公司")
    mock.return_value.is_available = True
    return mock
```

**Environment Variables:**
- `ENABLE_EQC_INTEGRATION`: Set to `true` for real API calls
- `EQC_BASE_URL`: Override for sandbox/test environment
- `WDH_ALIAS_SALT`: Salt for temp ID generation (use consistent value in tests)

### 3.3 Gold Layer Scenarios (Story 4.4)
*Goal: Validate database projection and integrity constraints.*

**Composite Key Definition** (per `GoldAnnuitySchema`):
```python
GOLD_COMPOSITE_KEY = ("月度", "计划代码", "组合代码", "company_id")
```

*   **[GD-001] Composite Key Uniqueness**:
    *   Ensure no duplicate `(月度, 计划代码, 组合代码, company_id)` tuples exist in output.
    *   Note: `组合代码` was added to handle multiple portfolios per plan (MVP Validation).
*   **[GD-002] Non-Negative Constraints**:
    *   `期初资产规模` >= 0 (starting_assets)
    *   `期末资产规模` >= 0 (ending_assets)
    *   `供款` >= 0 (contributions)
    *   `流失_含待遇支付` >= 0 (outflows)
*   **[GD-003] Schema Projection**:
    *   Verify extra columns (e.g., intermediate calculations) are dropped.
    *   Verify field names match `GoldAnnuitySchema` exactly (strict=True).
*   **[GD-004] Duplicate Aggregation**:
    *   When `aggregate_duplicates=True`: Sum numeric fields, take first for non-numeric.
    *   When `aggregate_duplicates=False`: Retain all detail rows (no error).
*   **[GD-005] Required Fields Validation**:
    *   `月度`: NOT NULL, valid date
    *   `计划代码`: NOT NULL, min_length=1
    *   `company_id`: NOT NULL, min_length=1
    *   `客户名称`: NOT NULL
    *   `期初资产规模`, `期末资产规模`, `投资收益`: NOT NULL

### 3.4 Business Type Coverage
*Goal: Ensure logic holds across different business lines.*

*   **[BIZ-01] Enterprise Annuity (Trustee)**: `企年受托`.
*   **[BIZ-02] Enterprise Annuity (Investment)**: `企年投资`.
*   **[BIZ-03] Occupational Annuity**: `职年受托` / `职年投资` (Triggers specific defaults like `QTAN003`).

### 3.5 Reference Data Sync Scenarios (Epic 6.2)
*Goal: Validate foreign key backfill and reference table synchronization.*

**Configuration Reference**: `config/data_sources.yml` → `foreign_keys` section

| ID | Scenario | Source Column | Target Table | Expected Behavior |
|----|----------|---------------|--------------|-------------------|
| REF-001 | Plan Backfill | `计划代码` | `年金计划` | Insert missing plans with derived fields |
| REF-002 | Portfolio Backfill | `组合代码` | `组合计划` | Insert missing portfolios (depends on fk_plan) |
| REF-003 | Organization Backfill | `组织代码` | `组织架构` | Insert missing org codes |
| REF-004 | Product Line Backfill | `产品线代码` | `产品线` | Insert from config file |
| REF-005 | Dependency Order | fk_portfolio depends on fk_plan | - | Portfolio backfill waits for plan |

**Plan Candidate Derivation Rules** (per `reference_backfill/service.py`):
*   `客户名称`: Most frequent value, tie-break by max `期末资产规模`
*   `主拓代码/主拓机构`: From row with max `期末资产规模`
*   `备注`: Format as `YYMM_新建` from `月度` field
*   `资格`: Filtered business types in order: `企年受托+企年投资+职年受托+年+职年投资`

### 3.6 Cleansing Registry Scenarios (Story 2.3)
*Goal: Validate domain-specific cleansing rule chains.*

**Configuration Reference**: `infrastructure/cleansing/settings/cleansing_rules.yml`

| ID | Field | Rule Chain | Test Input | Expected Output |
|----|-------|------------|------------|-----------------|
| CR-001 | `客户名称` | trim_whitespace → normalize_company_name | " 公司A（已转出） " | "公司A" |
| CR-002 | `期末资产规模` | remove_currency_symbols → clean_comma_separated_number | "¥1,234,567.89" | 1234567.89 |
| CR-003 | `当期收益率` | remove_currency_symbols → clean_comma_separated_number → handle_percentage_conversion | "5.5%" | 0.055 |
| CR-004 | `计划代码` | trim_whitespace | " P0290 " | "P0290" |

### 3.7 Error Handling Scenarios
*Goal: Validate graceful degradation and error reporting.*

| ID | Scenario | Input Condition | Expected Behavior |
|----|----------|-----------------|-------------------|
| ERR-001 | Bronze Threshold Exceeded | >10% unparseable dates | Raise validation error |
| ERR-002 | Bronze Threshold Exceeded | >10% non-numeric assets | Raise validation error |
| ERR-003 | Missing Required Column | File without `期末资产规模` | Raise schema error |
| ERR-004 | Empty DataFrame | 0 rows after filtering | Raise "DataFrame is empty" error |
| ERR-005 | EQC Budget Exhausted | Budget=0, unknown company | Generate temp ID (no error) |
| ERR-006 | DB Connection Failure | Database unavailable | Graceful fallback to temp ID |

#### 3.7.1 Error Scenario Implementation Strategy

| Scenario | Implementation Approach | Test File Location |
|----------|------------------------|-------------------|
| ERR-001/002 | Create separate malformed Excel files | `tests/fixtures/golden_dataset/error_cases/threshold_exceeded.xlsx` |
| ERR-003 | Create Excel file missing required column | `tests/fixtures/golden_dataset/error_cases/missing_column.xlsx` |
| ERR-004 | Use empty sheet in test file | `tests/fixtures/golden_dataset/error_cases/empty_sheet.xlsx` |
| ERR-005/006 | Mock external dependencies in unit tests | No fixture needed (use pytest mocks) |

**Directory Structure for Error Cases:**
```text
tests/fixtures/golden_dataset/error_cases/
├── threshold_exceeded_dates.xlsx    # >10% unparseable dates (ERR-001)
├── threshold_exceeded_numeric.xlsx  # >10% non-numeric assets (ERR-002)
├── missing_required_column.xlsx     # Missing 期末资产规模 (ERR-003)
└── empty_sheet.xlsx                 # Empty 规模明细 sheet (ERR-004)
```

**Test Implementation Pattern:**
```python
def test_err_001_date_threshold_exceeded():
    """ERR-001: Should raise when >10% dates are unparseable."""
    with pytest.raises(ValidationError, match="unparseable dates exceed threshold"):
        validate_bronze_dataframe(df_with_bad_dates, failure_threshold=0.10)
```

## 4. Dataset Manifest & Metadata

A **Manifest File** (`dataset_manifest.csv`) maps specific rows to their test purpose.

### 4.1 Core Pipeline Scenarios

| ID | File / Sheet | Row Index | Layer | Scenario Tag | Expected Outcome | Description |
|----|--------------|-----------|-------|--------------|------------------|-------------|
| 1  | V2/File.xlsx | 2         | Bronze| BZ-001       | Pass             | Happy path - all fields valid |
| 2  | V2/File.xlsx | 3         | Bronze| BZ-002       | 1234.56          | Numeric coercion (¥1,234.56) |
| 3  | V2/File.xlsx | 4         | Bronze| BZ-003       | 2025-10-01       | Date parsing (202510 string) |
| 4  | V2/File.xlsx | 5         | Silver| SV-NAME-01   | "XX公司"         | Name normalization (removal of '已转出') |
| 5  | V2/File.xlsx | 6         | Silver| PC-001       | "P0290"          | Plan code prefix strip (1P0290 → P0290) |
| 6  | V2/File.xlsx | 7         | Silver| PC-002       | "AN001"          | Null plan code + 集合计划 → AN001 |
| 7  | V2/File.xlsx | 8         | Silver| PORT-002     | "QTAN003"        | Null portfolio code default for 职年 |
| 8  | V2/File.xlsx | 9         | Silver| ORG-001      | "G00"            | Null org code → G00 default |
| 9  | V2/File.xlsx | 10        | Gold  | GD-001       | Unique           | Composite PK uniqueness check |
| 10 | V2/File.xlsx | 99        | Bronze| BZ-ERR-02    | Reject/Log       | 'N/A' in asset column |

### 4.2 Company ID Resolution Scenarios

| ID | File / Sheet | Row Index | Layer | Scenario Tag | Expected Outcome | Description |
|----|--------------|-----------|-------|--------------|------------------|-------------|
| 11 | V2/File.xlsx | 11        | Silver| SV-ENR-01    | "614810477"      | YAML override - plan code (FP0001) |
| 12 | V2/File.xlsx | 12        | Silver| SV-ENR-02    | "608349737"      | YAML override - hardcode (P0809) |
| 13 | V2/File.xlsx | 13        | Silver| SV-ENR-03    | DB-P1 resolved   | DB cache - plan code lookup |
| 14 | V2/File.xlsx | 14        | Silver| SV-ENR-04    | DB-P4 resolved   | DB cache - normalized customer name |
| 15 | V2/File.xlsx | 15        | Silver| SV-ENR-06    | Passthrough      | Existing company_id column preserved |
| 16 | V2/File.xlsx | 16        | Silver| SV-ENR-08    | "INXXXX..."     | Temp ID generation (unknown company) |
| 17 | V2/File.xlsx | 17        | Silver| SV-ENR-09    | Same as row 16   | Temp ID determinism (same name) |

### 4.3 Reference Data Backfill Scenarios

| ID | File / Sheet | Row Index | Layer | Scenario Tag | Expected Outcome | Description |
|----|--------------|-----------|-------|--------------|------------------|-------------|
| 18 | V2/File.xlsx | 18        | Ref   | REF-001      | Plan inserted    | New plan code triggers backfill |
| 19 | V2/File.xlsx | 19        | Ref   | REF-002      | Portfolio inserted | New portfolio triggers backfill |
| 20 | V2/File.xlsx | 20        | Ref   | REF-005      | Ordered insert   | Portfolio waits for plan dependency |

### 4.4 Business Type Coverage

| ID | File / Sheet | Row Index | Layer | Scenario Tag | Expected Outcome | Description |
|----|--------------|-----------|-------|--------------|------------------|-------------|
| 21 | V2/File.xlsx | 21        | Silver| BIZ-01       | 企年受托 logic   | Enterprise Annuity Trustee |
| 22 | V2/File.xlsx | 22        | Silver| BIZ-02       | 企年投资 logic   | Enterprise Annuity Investment |
| 23 | V2/File.xlsx | 23        | Silver| BIZ-03       | QTAN003 default  | Occupational Annuity (职年受托) |

### 4.5 Sample Row Construction Guide

This section provides concrete data examples for constructing test rows. Each row should satisfy its scenario requirements while maintaining realistic data patterns.

#### 4.5.1 Bronze Layer Sample Rows

| Row | 月度 | 计划代码 | 客户名称 | 期末资产规模 | 业务类型 | Scenario |
|-----|------|----------|----------|--------------|----------|----------|
| 2 | 202510 | P0290 | 测试公司A | 1000000.00 | 企年受托 | BZ-001 (Happy Path) |
| 3 | 202510 | P0291 | 测试公司B | ¥1,234.56 | 企年投资 | BZ-002 (Currency) |
| 4 | "202510" | P0292 | 测试公司C | 500000 | 职年受托 | BZ-003 (Date String) |
| 99 | 202510 | P0299 | 测试公司X | Unknown | 企年受托 | BZ-ERR-02 (Invalid) |

#### 4.5.2 Silver Layer Sample Rows (Cleansing)

| Row | 计划代码 (Input) | 客户名称 (Input) | 组合代码 (Input) | Expected Output | Scenario |
|-----|------------------|------------------|------------------|-----------------|----------|
| 5 | " 测试公司（已转出） " | - | - | "测试公司" | SV-NAME-01 |
| 6 | 1P0290 | 测试公司 | - | P0290 | PC-001 |
| 7 | NULL | 测试公司 (计划类型=集合计划) | - | AN001 | PC-002 |
| 8 | P0293 | 测试公司 (业务类型=职年受托) | NULL | QTAN003 | PORT-002 |

#### 4.5.3 Company ID Resolution Sample Rows

| Row | 计划代码 | 客户名称 | 年金账户名 | company_id (Input) | Expected company_id | Scenario |
|-----|----------|----------|------------|-------------------|---------------------|----------|
| 11 | FP0001 | 任意公司 | - | - | 614810477 | SV-ENR-01 (YAML) |
| 12 | P0809 | 任意公司 | - | - | 608349737 | SV-ENR-02 (YAML) |
| 13 | P0290 | 测试公司A | - | - | 123456789 | SV-ENR-03 (DB-P1) |
| 14 | P9999 | 中国石油天然气集团公司 | - | - | 987654321 | SV-ENR-04 (DB-P4) |
| 15 | P9998 | 已知公司 | - | 888777666 | 888777666 | SV-ENR-06 (Passthrough) |
| 16 | P9997 | 完全未知的公司名称XYZ | - | - | INXXXX... | SV-ENR-08 (Temp ID) |

#### 4.5.4 Multi-Scenario Row Construction

Some rows may need to satisfy multiple scenarios. Use this pattern:

```
Row 13 (SV-ENR-03 + BZ-001):
- 月度: 202510 (valid date for BZ-001)
- 计划代码: P0290 (exists in enrichment_index for SV-ENR-03)
- 客户名称: 测试公司A
- 期末资产规模: 1000000.00 (valid numeric for BZ-001)
- 业务类型: 企年受托
```

## 5. Legacy Reference (Parity Verification)

For **Epic 6 Parity Validation**, we verify the New Pipeline output against the Legacy System's Postgres data.

*   **Source Table**: `business.规模明细` (Legacy)
*   **Target Table**: `annuity_performance_NEW` (New Pipeline)
*   **Parity Criteria**:
    1.  **Row Count**: Exact match for the same reporting month.
    2.  **Field Value**: 100% equality for mapped fields (allowing for float precision ±1e-6).
    3.  **Enrichment**: `company_id` generation must match legacy logic (or be explicitly mapped).

**Snapshot Strategy**:
The `legacy_reference_snapshot.json` contains the `SELECT * FROM business.规模明细 WHERE monthly='202510'` result for the rows present in the Golden Dataset, enabling offline parity unit tests.

### 5.1 Parity Validation Script

```bash
# Run parity validation
PYTHONPATH=src uv run python scripts/tools/parity/validate_annuity_performance_parity.py

# Check latest results
ls -la tests/fixtures/validation_results/annuity_performance/
```

### 5.1.1 Legacy Snapshot Generation

**Option 1: Export from Production** (requires VPN + DB access)
```bash
# Export legacy data for specific month
PYTHONPATH=src uv run python scripts/tools/export_legacy_snapshot.py \
  --month 202510 \
  --output tests/fixtures/golden_dataset/reference_data/legacy_snapshot.json

# Verify export
cat tests/fixtures/golden_dataset/reference_data/legacy_snapshot.json | jq '.metadata'
```

**Option 2: Use Pre-generated Snapshot** (for CI/CD without DB access)
```bash
# Copy versioned snapshot
cp tests/fixtures/golden_dataset/reference_data/legacy_snapshot_202510_v1.json \
   tests/fixtures/golden_dataset/reference_data/legacy_snapshot.json
```

**Option 3: Manual Construction** (for isolated unit tests)
```python
# Create minimal snapshot for specific scenarios
legacy_snapshot = {
    "metadata": {"source_table": "business.规模明细", "reporting_month": "202510"},
    "rows": [
        {"月度": "2025-10-01", "计划代码": "P0290", "company_id": "123456789", ...}
    ]
}
```

**Snapshot Refresh Policy:**
- Refresh when legacy cleansing logic changes
- Version snapshots with date suffix: `legacy_snapshot_YYYYMM_vN.json`
- Document changes in `CHANGELOG.md`

### 5.2 Known Parity Differences

| Category | Description | Resolution |
|----------|-------------|------------|
| Float Precision | Minor differences in decimal places | Allow ±1e-6 tolerance |
| Column Rename | `流失（含待遇支付）` → `流失(含待遇支付)` | Handled in schema |
| Missing Tables | `eqc_search_result`, `annuity_account_mapping` | Fallback to temp ID |

## 6. End-to-End Workflow Validation

### 6.1 Pipeline Execution Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  File Discovery │───▶│  Bronze Layer   │───▶│  Silver Layer   │
│  (Epic 3)       │    │  (Pandera)      │    │  (Pydantic)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                       ┌─────────────────┐            │
                       │  Gold Layer     │◀───────────┘
                       │  (Projection)   │
                       └────────┬────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ DB Load       │    │ Reference       │    │ Observability   │
│ (Warehouse)   │    │ Backfill        │    │ (Audit Log)     │
└───────────────┘    └─────────────────┘    └─────────────────┘
```

### 6.2 Integration Test Checklist

| Test Category | Test File | Coverage |
|---------------|-----------|----------|
| E2E Pipeline | `tests/e2e/test_annuity_pipeline_e2e.py` | Full pipeline execution |
| Schema Validation | `tests/unit/domain/annuity_performance/test_schemas.py` | Bronze/Gold schemas |
| Model Validation | `tests/domain/annuity_performance/test_models.py` | Pydantic models |
| Cleansing Rules | `tests/unit/domain/annuity_performance/test_cleansing_integration.py` | Rule chains |
| Company ID | `tests/unit/infrastructure/enrichment/test_mapping_repository_enrichment_index.py` | Resolution logic |
| File Discovery | `tests/integration/io/test_file_discovery_integration.py` | Version detection |
| Config Loading | `tests/integration/test_annuity_config.py` | data_sources.yml |

## 7. Implementation Checklist

### 7.1 Dataset Creation Tasks (Priority Order)

**Phase 1 - Foundation (Blocking)** ⚠️ Must complete first
- [ ] **P0**: Set up V1/V2 directory structure for version testing
- [ ] **P0**: Populate `enrichment_index.csv` with test company mappings (for SV-ENR-03/04/05)
- [ ] **P0**: Create `yaml_overrides.yml` with test override entries (for SV-ENR-01/02)

**Phase 2 - Core Data (Depends on Phase 1)**
- [ ] **P1**: Create curated Excel file with all scenario rows (23+ rows)
- [ ] **P1**: Write `dataset_manifest.csv` with row-to-scenario mapping
- [ ] **P1**: Create error case Excel files (for ERR-001 to ERR-004)

**Phase 3 - Validation (Depends on Phase 2)**
- [ ] **P2**: Generate expected output files (bronze/silver/gold CSVs)
- [ ] **P2**: Generate `legacy_snapshot.json` from production data
- [ ] **P2**: Run dataset validation script to verify coverage

**Parallel Tasks** (Can run alongside any phase)
- [ ] Set up CI/CD integration for golden dataset tests
- [ ] Document any deviations from expected behavior

### 7.2 Test Implementation Tasks (Priority Order)

**Phase 1 - Core Pipeline Tests**
- [ ] **P0**: Unit tests for Bronze scenarios (BZ-001 to BZ-ERR-02)
- [ ] **P0**: Unit tests for Gold scenarios (GD-001 to GD-005)

**Phase 2 - Transformation Tests**
- [ ] **P1**: Unit tests for Silver cleansing scenarios (SV-DATE, SV-PLAN, SV-ORG, SV-PORT)
- [ ] **P1**: Unit tests for Company Name normalization (SV-NAME-01 to SV-NAME-03)

**Phase 3 - Enrichment Tests**
- [ ] **P2**: Unit tests for Company ID resolution (SV-ENR-01 to SV-ENR-09)
- [ ] **P2**: Integration tests for reference backfill (REF-001 to REF-005)

**Phase 4 - End-to-End**
- [ ] **P3**: E2E test using golden dataset
- [ ] **P3**: Parity validation against legacy snapshot

### 7.3 Dataset Validation Script

Run this script to verify dataset completeness before committing:

```bash
# Validate golden dataset coverage
PYTHONPATH=src uv run python scripts/tools/validate_golden_dataset.py \
  --dataset-path tests/fixtures/golden_dataset/curated \
  --manifest dataset_manifest.csv

# Expected output:
# ✅ All 23 scenarios covered
# ✅ Reference data files present (enrichment_index.csv, yaml_overrides.yml)
# ✅ Expected outputs match actual pipeline outputs
# ⚠️ Missing: SV-ENR-07 (EQC lookup - requires mock)
```

**Validation Checks:**
| Check | Description | Pass Criteria |
|-------|-------------|---------------|
| Scenario Coverage | All manifest scenarios have corresponding rows | 100% |
| Reference Data | Required CSV/YAML files exist and are valid | All present |
| Output Parity | Expected outputs match pipeline outputs | ±1e-6 tolerance |
| Schema Compliance | All rows pass Bronze/Gold schema validation | 100% |

### 7.4 Validation Criteria

| Metric | Target | Current | Notes |
|--------|--------|---------|-------|
| Row Count Parity | 100% | 99.7% | Investigating 0.3% difference |
| Field Value Parity | 100% | TBD | Pending legacy snapshot |
| Company ID Match | 100% | TBD | Depends on enrichment_index |
| Test Coverage | >90% | TBD | Measured by pytest-cov |
| Scenario Coverage | 23/23 | TBD | Per manifest |

---

## 8. FAQ & Troubleshooting

### Q1: How do I verify my dataset is correct?
Run the validation script (Section 7.3). It checks scenario coverage, reference data presence, and output parity.

### Q2: What if EQC lookup (SV-ENR-07) fails in CI/CD?
Use the mock strategy in Section 3.2.3.1. Set `ENABLE_EQC_INTEGRATION=false` to skip real API calls.

### Q3: How do I update the dataset for new scenarios?
1. Add new row to Excel file
2. Update `dataset_manifest.csv` with scenario tag
3. Update expected output files
4. Run validation script
5. Update `CHANGELOG.md`

### Q4: What if legacy snapshot is outdated?
Re-generate using Option 1 in Section 5.1.1, or document the difference in Section 5.2.

---

**Document Version**: 3.0
**Last Updated**: 2025-12-13
**Status**: Complete - Ready for implementation
**Changelog**:
- v3.0: Added team feedback (reference data schemas, sample rows, error strategies, priority checklist)
- v2.0: Enhanced for Epic 4/5/6 full workflow validation
- v1.0: Initial requirements document
