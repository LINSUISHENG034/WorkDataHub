# Cleansing Rules Documentation Index

This directory contains documented cleansing rules for each domain migrated from the legacy system.

## Purpose

- Provide reference for Pipeline configuration
- Enable parity validation against legacy behavior
- Capture tribal knowledge before it's lost
- Establish standard documentation process for domain migrations

## Template

Use [cleansing-rules-template.md](../templates/cleansing-rules-template.md) when documenting a new domain.

## Documented Domains

| Domain | Status | Document | Legacy Class | Dependencies Migrated |
|--------|--------|----------|--------------|----------------------|
| annuity_performance | Partial (85% - 2 tables missing) | [annuity-performance.md](./annuity-performance.md) | `AnnuityPerformanceCleaner` | Partial (5/7 tables migrated) |
| annuity_income | Pending (Epic 5.5) | [annuity-income.md](./annuity-income.md) | `AnnuityIncomeCleaner` | Yes (company_id_mapping, eqc_search_result) |

## Pending Domains (Epic 6+)

The following domains are candidates for future migration. Each should be documented using the template before implementation.

| Legacy Class | Chinese Name | Sheet Name | Priority | Dependencies Migrated |
|--------------|--------------|------------|----------|----------------------|
| `GroupRetirementCleaner` | 团养缴费 | 团养缴费 | TBD | No |
| `HealthCoverageCleaner` | 企康缴费 | 企康缴费 | TBD | No |
| `YLHealthCoverageCleaner` | 养老险承保 | 养老险 | TBD | No |
| `JKHealthCoverageCleaner` | 健康险承保 | 健康险 | TBD | No |
| `IFECCleaner` | 提费扩面 | 提费扩面 | TBD | No |
| `APMACleaner` | 手工调整 | 灌入数据 | TBD | No |
| `TrusteeAwardCleaner` | 企年受托中标 | 企年受托中标(空白) | TBD | No |
| `TrusteeLossCleaner` | 企年受托流失 | 企年受托流失(解约) | TBD | No |
| `InvesteeAwardCleaner` | 企年投资中标 | 企年投资中标(空白) | TBD | No |
| `InvesteeLossCleaner` | 企年投资流失 | 企年投资流失(解约) | TBD | No |
| `PInvesteeNIPCleaner` | 职年投资新增组合 | 职年投资新增组合 | TBD | No |
| `InvestmentPortfolioCleaner` | 组合业绩 | 组合业绩 | TBD | No |
| `GRAwardCleaner` | 团养中标 | 团养中标 | TBD | No |
| `RenewalPendingCleaner` | 续签客户清单 | 续签客户清单 | TBD | No |
| `RiskProvisionBalanceCleaner` | 风准金余额 | 风准金 | TBD | No |
| `HistoryFloatingFeesCleaner` | 历史浮费 | 历史浮费 | TBD | No |
| `AssetImpairmentCleaner` | 减值计提 | 减值计提 | TBD | No |
| `RevenueDetailsCleaner` | 利润达成 | 公司利润数据 | TBD | No |
| `RevenueBudgetCleaner` | 利润预算 | 预算_2024 | TBD | No |
| `AnnuityRateStatisticsData` | 年金费率统计 | Sheet 0 | TBD | No |

## Documentation Workflow

1. **Before Migration:** Create cleansing rules document using template
2. **During Migration:** Reference document for Pipeline configuration
3. **After Migration:** Update document with any discovered edge cases
4. **Parity Validation:** Use document as checklist for validation

## References

- [Legacy Data Cleaner Source](../../legacy/annuity_hub/data_handler/data_cleaner.py)
- [Legacy Parity Validation Guide](../runbooks/legacy-parity-validation.md)
- [Epic 5.5: Pipeline Architecture Validation](../epics/epic-5.5-pipeline-architecture-validation.md)
