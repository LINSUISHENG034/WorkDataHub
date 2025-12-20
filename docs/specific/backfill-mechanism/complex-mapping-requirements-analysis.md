# 回填机制复杂映射需求分析

## 问题描述

在 `annuity_performance` 域的数据处理中，存在一对多关系的复杂映射需求，当前的回填机制(具体介绍详见`docs/guides/infrastructure/backfill-mechanism-guide.md`)无法支持以下场景：

1. **主拓信息映射**：需要将 `期末资产规模` 最大值对应的 `机构代码` 和 `机构名称` 作为 `年金计划` 表的 `主拓代码` 和 `主拓机构`
2. **管理资格映射**：需要将 `业务类型` 进行去重组合（用 `+` 分隔）作为 `年金计划` 表的 `管理资格`

## 当前回填机制的局限性

### 1. 简单字段映射限制

当前回填机制 (`GenericBackfillService`) 只支持简单的 1:1 字段映射：

```python
# 当前实现 - groupby.first 取每个分组的第一个非空值
grouped_first = source_df.groupby(config.source_column, sort=False).first()
```

**问题**：
- 无法处理聚合需求（如最大值、求和等）
- 无法处理多个值的组合（如业务类型的拼接）
- 无法根据条件选择特定值

### 2. 配置结构限制

当前的 `foreign_keys.yml` 配置结构：

```yaml
backfill_columns:
  - source: "源字段名"
    target: "目标字段名"
    optional: true/false
```

**问题**：
- 无法指定聚合函数（MAX, SUM, GROUP_CONCAT等）
- 无法指定复杂的转换逻辑
- 无法引用多个源字段进行组合

## 具体需求分析

### 需求1：主拓代码和主拓机构映射

**目标**：将 `期末资产规模` 最大值对应的 `机构代码` 和 `机构名称` 作为 `年金计划` 表的 `主拓代码` 和 `主拓机构`

**数据关系**：
- 一个 `计划代码` 可能对应多个记录（不同业务类型、不同月份、不同机构）
- 每个记录都有 `期末资产规模`、`机构代码`、`机构名称` 字段
- 需要找到 `期末资产规模` 最大的记录，提取其 `机构代码` 和 `机构名称`

**当前SQL逻辑**（推测）：
```sql
UPDATE mapping.年金计划 Renewal INNER JOIN (
    SELECT
        A.年金计划号,
        MaxScale.机构代码,
        MaxScale.机构名称
    FROM
        mapping.年金计划 A
    INNER JOIN (
        SELECT
            计划代码,
            机构代码,
            机构名称
        FROM business.规模明细
        WHERE (计划代码, 期末资产规模) IN (
            SELECT
                计划代码,
                MAX(期末资产规模)
            FROM business.规模明细
            GROUP BY 计划代码
        )
    ) MaxScale
    ON A.年金计划号 = MaxScale.计划代码
    WHERE ISNULL(A.主拓代码) OR ISNULL(A.主拓机构)
    GROUP BY
        A.年金计划号,
        MaxScale.机构代码,
        MaxScale.机构名称
) Result
ON Renewal.年金计划号 = Result.年金计划号
SET
    Renewal.主拓代码 = Result.机构代码,
    Renewal.主拓机构 = Result.机构名称
WHERE ISNULL(Renewal.主拓代码) OR ISNULL(Renewal.主拓机构);
```

### 需求2：管理资格映射

**目标**：将年金计划涉及的所有业务类型用 `+` 连接

**数据关系**：
- 一个 `计划代码` 对应多个 `业务类型`
- 需要去重并按字母顺序排序

**当前SQL逻辑**：
```sql
UPDATE mapping.年金计划 Renewal INNER JOIN (
    SELECT
        A.年金计划号,
        GROUP_CONCAT(DISTINCT B.业务类型 ORDER BY B.业务类型 SEPARATOR '+') AS 管理资格
    FROM
        mapping.年金计划 A
    INNER JOIN
        business.规模明细 B
    ON
        A.年金计划号 = B.计划代码
    WHERE
        ISNULL(A.管理资格)
    GROUP BY
        A.年金计划号
) Result
ON Renewal.年金计划号 = Result.年金计划号
SET Renewal.管理资格 = Result.管理资格
WHERE ISNULL(Renewal.管理资格);
```