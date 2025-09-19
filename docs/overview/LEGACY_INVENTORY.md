# Legacy System Inventory Report (R-015)

## Executive Summary

Complete inventory of legacy `annuity_hub` data cleaners revealing **21 domain-specific cleaners** handling various business data transformations. This report provides detailed analysis for migration planning.

## Cleaner Inventory & Analysis

### 1. Core Business Performance Domains (业务数据-系统)

#### 1.1 AnnuityPerformanceCleaner (规模明细)

- **Sheet**: 规模明细
- **Complexity**: HIGH ⭐⭐⭐⭐⭐
- **Key Features**:
  - 5-level company_id resolution hierarchy
  - Complex portfolio code assignment logic
  - Department code extraction via regex
  - Customer name normalization
  - Plan code corrections and defaults
- **Dependencies**: All 5 COMPANY_ID mappings, BUSINESS_TYPE_CODE_MAPPING, DEFAULT_PORTFOLIO_CODE_MAPPING
- **Migration Priority**: P1 - Core business metric

#### 1.2 AnnuityIncomeCleaner (收入明细)

- **Sheet**: 收入明细
- **Complexity**: HIGH ⭐⭐⭐⭐
- **Key Features**:
  - Inherits company_id update logic
  - Portfolio code conditional assignment
  - Product line code mapping
  - Date standardization
- **Dependencies**: COMPANY_ID mappings 1,3,4,5, BUSINESS_TYPE_CODE_MAPPING
- **Migration Priority**: P1 - Revenue tracking

#### 1.3 GroupRetirementCleaner (团养缴费)

- **Sheet**: 团养缴费
- **Complexity**: MEDIUM ⭐⭐⭐
- **Key Features**:
  - Multiple date field processing
  - Company branch mapping
  - Customer name cleaning
- **Dependencies**: COMPANY_ID4_MAPPING, COMPANY_BRANCH_MAPPING
- **Migration Priority**: P1 - Payment tracking

### 2. Health Coverage Domains (企康业务)

#### 2.1 HealthCoverageCleaner (企康缴费)

- **Sheet**: 企康缴费
- **Complexity**: MEDIUM ⭐⭐⭐
- **Key Features**:
  - Multiple date fields
  - Performance metrics calculation
  - Column renaming with Chinese/English
- **Dependencies**: COMPANY_ID4_MAPPING, COMPANY_BRANCH_MAPPING
- **Migration Priority**: P2

#### 2.2 YLHealthCoverageCleaner (养老险)

- **Sheet**: 养老险
- **Complexity**: MEDIUM ⭐⭐⭐
- **Key Features**: Similar to HealthCoverageCleaner
- **Migration Priority**: P2

#### 2.3 JKHealthCoverageCleaner (健康险)

- **Sheet**: 健康险
- **Complexity**: MEDIUM ⭐⭐⭐
- **Key Features**:
  - Regex-based column name cleaning
  - Conditional column dropping
- **Migration Priority**: P2

### 3. Manual Adjustments & Special Cases (台账)

#### 3.1 IFECCleaner (提费扩面)

- **Sheet**: 提费扩面
- **Complexity**: MEDIUM ⭐⭐⭐
- **Key Features**:
  - Percentage to decimal conversion
  - Numeric type coercion
- **Migration Priority**: P2

#### 3.2 APMACleaner (手工调整)

- **Sheet**: 灌入数据
- **Complexity**: MEDIUM ⭐⭐⭐
- **Key Features**:
  - Portfolio code processing
  - Business type mapping
- **Migration Priority**: P3

### 4. Award/Loss Tracking (中标/流失)

#### 4.1 TrusteeAwardCleaner (企年受托中标)

- **Sheet**: 企年受托中标(空白)
- **Complexity**: LOW ⭐⭐
- **Migration Priority**: P2

#### 4.2 TrusteeLossCleaner (企年受托流失)

- **Sheet**: 企年受托流失(解约)
- **Complexity**: LOW ⭐⭐
- **Filter Logic**: Excludes null 年金计划号
- **Migration Priority**: P2

#### 4.3 InvesteeAwardCleaner (企年投资中标)

- **Sheet**: 企年投资中标(空白)
- **Complexity**: LOW ⭐⭐
- **Migration Priority**: P2

#### 4.4 InvesteeLossCleaner (企年投资流失)

- **Sheet**: 企年投资流失(解约)
- **Complexity**: LOW ⭐⭐
- **Migration Priority**: P2

#### 4.5 GRAwardCleaner (团养中标)

- **Sheet**: 团养中标
- **Complexity**: LOW ⭐⭐
- **Migration Priority**: P3

### 5. Investment & Portfolio Management

#### 5.1 PInvesteeNIPCleaner (职年投资新增组合)

- **Sheet**: 职年投资新增组合
- **Complexity**: LOW ⭐⭐
- **Migration Priority**: P3

#### 5.2 InvestmentPortfolioCleaner (组合业绩)

- **Sheet**: 组合业绩
- **Complexity**: LOW ⭐⭐
- **Key Features**: Portfolio code normalization (remove 'F' prefix)
- **Migration Priority**: P3

### 6. Revenue & Financial Tracking

#### 6.1 RiskProvisionBalanceCleaner (风准金余额)

- **Sheet**: 风准金
- **Complexity**: MEDIUM ⭐⭐⭐
- **Key Features**:
  - Plan code derivation from portfolio
  - Complex column cleaning
- **Migration Priority**: P2

#### 6.2 HistoryFloatingFeesCleaner (历史浮费)

- **Sheet**: 历史浮费
- **Complexity**: MEDIUM ⭐⭐⭐
- **Key Features**:
  - Forward-fill logic for grouped data
  - Multi-column dependencies
- **Migration Priority**: P3

#### 6.3 AssetImpairmentCleaner (减值计提)

- **Sheet**: 减值计提
- **Complexity**: LOW ⭐⭐
- **Migration Priority**: P3

#### 6.4 RevenueDetailsCleaner (考核口径利润达成)

- **Sheet**: 公司利润数据
- **Complexity**: HIGH ⭐⭐⭐⭐
- **Key Features**:
  - Multi-sheet processing (实际_2023, 实际_2024)
  - Data unpivoting (melt operation)
  - Conditional value sign reversal
- **Migration Priority**: P1 - Financial reporting

#### 6.5 RevenueBudgetCleaner (考核口径利润预算)

- **Sheet**: 预算_2024
- **Complexity**: HIGH ⭐⭐⭐⭐
- **Key Features**: Similar to RevenueDetailsCleaner
- **Migration Priority**: P1 - Budget planning

### 7. Other Domains

#### 7.1 RenewalPendingCleaner (续签客户清单)

- **Sheet**: 续签客户清单
- **Complexity**: LOW ⭐
- **Migration Priority**: P3

#### 7.2 AnnuityRateStatisticsData (年金费率统计)

- **Status**: INCOMPLETE (class definition only, no implementation found)
- **Migration Priority**: P4 - Investigate completeness

## Mapping Dependencies Summary

### Critical Mappings (Used by Multiple Domains)

1. **COMPANY_ID1_MAPPING**: Plan code → Company ID (5 domains)
2. **COMPANY_ID2_MAPPING**: Group customer code → Company ID (1 domain)
3. **COMPANY_ID3_MAPPING**: Special case mapping (2 domains)
4. **COMPANY_ID4_MAPPING**: Customer name → Company ID (8 domains)
5. **COMPANY_ID5_MAPPING**: Account name → Company ID (2 domains)
6. **COMPANY_BRANCH_MAPPING**: Branch name → Branch code (15 domains)
7. **BUSINESS_TYPE_CODE_MAPPING**: Business type → Product line code (4 domains)
8. **DEFAULT_PORTFOLIO_CODE_MAPPING**: Plan type → Portfolio code (4 domains)
9. **DEFAULT_PLAN_CODE_MAPPING**: Portfolio → Plan code (2 domains)
10. **PRODUCT_ID_MAPPING**: Product detail → Product ID (2 domains)
11. **PROFIT_METRICS_MAPPING**: Metric name → Metric code (2 domains)

## Migration Complexity Assessment

### By Complexity Level

- **HIGH (⭐⭐⭐⭐⭐)**: 1 domain (AnnuityPerformanceCleaner)
- **HIGH (⭐⭐⭐⭐)**: 3 domains (AnnuityIncome, RevenueDetails, RevenueBudget)
- **MEDIUM (⭐⭐⭐)**: 8 domains
- **LOW (⭐⭐)**: 8 domains
- **LOW (⭐)**: 1 domain

### By Priority

- **P1 (Critical)**: 4 domains - Core business metrics and financial reporting
- **P2 (Important)**: 8 domains - Operational data and tracking
- **P3 (Standard)**: 8 domains - Supporting functions
- **P4 (Investigate)**: 1 domain - Incomplete implementation

## Migration Recommendations

### Phase 1: Foundation (Week 1)

1. **Migrate all mapping configurations to YAML**
2. **Create BaseDomainService framework**
3. **Implement common utility functions**:
   - Date parsing and standardization
   - Company name cleaning
   - Column safety operations

### Phase 2: Critical Domains (Week 2-3)

1. **AnnuityPerformanceCleaner** - Most complex, core metric
2. **AnnuityIncomeCleaner** - Revenue tracking
3. **RevenueDetailsCleaner** - Financial reporting
4. **RevenueBudgetCleaner** - Budget planning

### Phase 3: Operational Domains (Week 4-5)

1. **GroupRetirementCleaner** - Payment processing
2. **Health Coverage cleaners** (3 variants)
3. **Award/Loss trackers** (4 cleaners)
4. **RiskProvisionBalanceCleaner** - Financial reserves

### Phase 4: Supporting Domains (Week 6)

1. Remaining low-complexity cleaners
2. Manual adjustment processors
3. Portfolio management tools

## Risk Factors

1. **Complex Business Logic**: Company ID resolution has 5-level hierarchy
2. **Data Quality Dependencies**: Many cleaners depend on fill-forward, default values
3. **Multi-Sheet Processing**: Some cleaners process multiple sheets with year-specific logic
4. **Incomplete Documentation**: AnnuityRateStatisticsData lacks implementation
5. **Chinese Column Names**: Extensive use of Chinese characters in column operations

## Success Criteria

- ✅ All 21 cleaners migrated (excluding incomplete one)
- ✅ All 11 mapping configurations preserved
- ✅ Regression tests pass with <1% deviation
- ✅ Performance improvement >2x
- ✅ Configuration-driven architecture
- ✅ Type-safe with Pydantic models

## Next Steps

1. **Update ROADMAP.md** with complete domain list
2. **Create detailed PRP for each P1 domain**
3. **Design mapping configuration schema**
4. **Implement migration framework**
5. **Begin P1 domain migrations**

---
*Report Generated: 2025-01-09*
*Status: COMPLETED*
*Next Action: Update ROADMAP.md with findings*
