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

| Domain | Status | Document | Legacy Class |
|--------|--------|----------|--------------|
| annuity_performance | Migrated (Epic 4-5) | (implicit in code) | `AnnuityPerformanceCleaner` |
| annuity_income | Pending (Epic 5.5) | [annuity-income.md](./annuity-income.md) | `AnnuityIncomeCleaner` |

## Pending Domains (Epic 6+)

The following domains are candidates for future migration. Each should be documented using the template before implementation.

| Legacy Class | Chinese Name | Sheet Name | Priority |
|--------------|--------------|------------|----------|
| `GroupRetirementCleaner` | 团养缴费 | 团养缴费 | TBD |
| `HealthCoverageCleaner` | 企康缴费 | 企康缴费 | TBD |
| `YLHealthCoverageCleaner` | 养老险承保 | 养老险 | TBD |
| `JKHealthCoverageCleaner` | 健康险承保 | 健康险 | TBD |
| `IFECCleaner` | 提费扩面 | 提费扩面 | TBD |
| `APMACleaner` | 手工调整 | 灌入数据 | TBD |
| `TrusteeAwardCleaner` | 企年受托中标 | 企年受托中标(空白) | TBD |
| `TrusteeLossCleaner` | 企年受托流失 | 企年受托流失(解约) | TBD |
| `InvesteeAwardCleaner` | 企年投资中标 | 企年投资中标(空白) | TBD |
| `InvesteeLossCleaner` | 企年投资流失 | 企年投资流失(解约) | TBD |
| `PInvesteeNIPCleaner` | 职年投资新增组合 | 职年投资新增组合 | TBD |
| `InvestmentPortfolioCleaner` | 组合业绩 | 组合业绩 | TBD |
| `GRAwardCleaner` | 团养中标 | 团养中标 | TBD |
| `RenewalPendingCleaner` | 续签客户清单 | 续签客户清单 | TBD |
| `RiskProvisionBalanceCleaner` | 风准金余额 | 风准金 | TBD |
| `HistoryFloatingFeesCleaner` | 历史浮费 | 历史浮费 | TBD |
| `AssetImpairmentCleaner` | 减值计提 | 减值计提 | TBD |
| `RevenueDetailsCleaner` | 利润达成 | 公司利润数据 | TBD |
| `RevenueBudgetCleaner` | 利润预算 | 预算_2024 | TBD |
| `AnnuityRateStatisticsData` | 年金费率统计 | Sheet 0 | TBD |

## Documentation Workflow

1. **Before Migration:** Create cleansing rules document using template
2. **During Migration:** Reference document for Pipeline configuration
3. **After Migration:** Update document with any discovered edge cases
4. **Parity Validation:** Use document as checklist for validation

## References

- [Legacy Data Cleaner Source](../../legacy/annuity_hub/data_handler/data_cleaner.py)
- [Legacy Parity Validation Guide](../runbooks/legacy-parity-validation.md)
- [Epic 5.5: Pipeline Architecture Validation](../epics/epic-5.5-pipeline-architecture-validation.md)
