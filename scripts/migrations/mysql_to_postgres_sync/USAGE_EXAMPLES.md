# MySQL到PostgreSQL Schema同步工具 - 使用示例

本文档提供了MySQL到PostgreSQL Schema同步工具的具体使用示例。

## 已完成的功能

✅ **核心功能**
- SQL文件解析：支持MySQL的CREATE TABLE语句解析
- 索引迁移：将MySQL索引转换为PostgreSQL索引
- 外键迁移：将MySQL外键转换为PostgreSQL外键
- 依赖检查：检查外键引用的表是否存在
- 错误处理：提供详细的错误报告和日志

✅ **已验证的表**
- `business.规模明细` - 成功同步了9个索引和4个外键

## 使用示例

### 1. 基本用法

```bash
# 同步指定表的索引和外键
source .env && python scripts/migrations/mysql_to_postgres_sync/sync_schema.py --table business.规模明细

# 使用详细日志模式
source .env && python scripts/migrations/mysql_to_postgres_sync/sync_schema.py --table business.规模明细 --verbose
```

### 2. Dry Run模式

```bash
# 只显示将要执行的SQL，不实际执行
source .env && python scripts/migrations/mysql_to_postgres_sync/sync_schema.py --table business.规模明细 --dry-run
```

### 3. 指定SQL文件目录

```bash
# 使用自定义的SQL文件目录
source .env && python scripts/migrations/mysql_to_postgres_sync/sync_schema.py \
    --table business.规模明细 \
    --sql-dir /path/to/sql/files
```

## 成功案例：business.规模明细表

### 迁移前状态
- 表存在，但没有索引和外键约束
- MySQL定义了9个索引和4个外键

### 迁移结果
✅ **成功创建的索引 (5个，因为过滤了重复)**
- `idx_规模明细_业务查询` - 复合索引 (月度, 机构代码)
- `idx_规模明细_公司id` - company_id索引
- `idx_规模明细_客户名称` - 客户名称索引
- `idx_规模明细_年金账户号` - 年金账户号索引
- `idx_规模明细_财务分析` - 复合索引 (月度, 产品线代码, 业务类型)

✅ **成功创建的外键 (4个)**
- `fk_规模明细_产品线` → `mapping.产品线`
- `fk_规模明细_年金计划` → `mapping.年金计划`
- `fk_规模明细_组合计划` → `mapping.组合计划`
- `fk_规模明细_组织架构` → `mapping.组织架构`

### 迁移日志摘要
```
MySQL到PostgreSQL Schema同步报告
============================================================

目标表: business.规模明细
SQL文件: tests\fixtures\legacy_db\schema\business\规模明细.sql
发现: 9 个索引, 4 个外键

✅ 成功创建: 13
  - 索引 INDEX (9个)
  - 外键 (4个)

============================================================
```

## 工作原理

1. **查找SQL文件**：在`tests/fixtures/legacy_db/schema/`目录下查找对应的SQL文件
2. **解析定义**：解析MySQL的CREATE TABLE语句，提取索引和外键定义
3. **检查依赖**：验证外键引用的表是否存在于PostgreSQL中
4. **生成DDL**：生成PostgreSQL兼容的CREATE INDEX和ALTER TABLE语句
5. **执行迁移**：按顺序执行DDL语句
6. **生成报告**：提供详细的执行报告

## 注意事项

1. **数据库名映射**：SQL文件中的数据库名映射到PostgreSQL的schema名
2. **外键引用表**：外键引用的表默认在`mapping` schema中查找
3. **索引名称**：自动处理索引名称冲突和转换
4. **错误处理**：遇到错误时会跳过并继续执行其他项目

## 下一步建议

1. **批量处理**：可以扩展脚本支持批量同步多个表
2. **配置文件**：添加配置文件支持，定义schema映射规则
3. **回滚功能**：添加回滚功能，在出错时恢复原始状态
4. **性能优化**：对于大型表，添加并行处理支持