# MySQL to PostgreSQL Schema Synchronization Script

## 概述

这是一个通用的脚本，用于根据MySQL SQL文件为PostgreSQL数据库表自动添加索引和外键约束。该脚本会扫描`tests/fixtures/legacy_db/schema/`目录下的SQL文件，解析MySQL的索引和外键定义，并将其转换为PostgreSQL兼容的DDL语句。

## 功能特性

- **自动文件匹配**：根据PostgreSQL表名自动查找对应的MySQL SQL文件
- **索引迁移**：将MySQL的KEY/INDEX定义转换为PostgreSQL的CREATE INDEX语句
- **外键迁移**：将MySQL的FOREIGN KEY约束转换为PostgreSQL的ALTER TABLE语句
- **依赖检查**：在添加外键前检查引用表是否存在，如果不存在则跳过并提示
- **错误处理**：处理各种边界情况和错误条件
- **详细日志**：提供详细的执行日志和进度报告

## 使用方法

```bash
# 基本用法
source .env && python scripts/migrations/mysql_to_postgres_sync/sync_schema.py --table schema.table_name

# 示例：为business.规模明细表同步索引和外键
source .env && python scripts/migrations/mysql_to_postgres_sync/sync_schema.py --table business.规模明细

# 带额外选项的用法
source .env && python scripts/migrations/mysql_to_postgres_sync/sync_schema.py \
    --table business.规模明细 \
    --dry-run \
    --verbose \
    --sql-dir tests/fixtures/legacy_db/schema
```

## 命令行参数

- `--table`: 目标PostgreSQL表名（格式：schema.table_name）
- `--sql-dir`: SQL文件目录路径（默认：tests/fixtures/legacy_db/schema）
- `--dry-run`: 只显示将要执行的SQL，不实际执行
- `--verbose`: 显示详细日志
- `--force`: 忽略某些错误继续执行

## 文件结构

```
scripts/migrations/mysql_to_postgres_sync/
├── README.md                 # 本文档
├── sync_schema.py            # 主脚本文件
├── sqlglot_parser.py         # SQL解析模块（基于sqlglot）
├── ddl_generator.py          # DDL生成模块
├── dependency_checker.py     # 依赖检查模块
├── pgloader_wrapper.py       # pgloader包装脚本
├── requirements.txt          # Python依赖
├── IMPLEMENTATION_PLAN.md    # 实施计划文档
└── USAGE_EXAMPLES.md         # 使用示例文档
```

## 工作流程

1. **输入验证**：验证PostgreSQL表名格式和数据库连接
2. **文件查找**：在指定目录下查找对应的MySQL SQL文件
3. **SQL解析**：解析MySQL的CREATE TABLE语句，提取索引和外键定义
4. **依赖检查**：检查外键引用的表是否存在于PostgreSQL中
5. **DDL生成**：生成PostgreSQL兼容的DDL语句
6. **执行迁移**：按顺序执行索引和外键的创建
7. **结果报告**：生成详细的执行报告

## 支持的MySQL特性

### 索引类型
- PRIMARY KEY
- UNIQUE KEY
- KEY (普通索引)
- INDEX
- FULLTEXT INDEX (转换为标准索引)

### 外键特性
- ON DELETE CASCADE
- ON DELETE RESTRICT
- ON DELETE SET NULL
- ON UPDATE CASCADE
- ON UPDATE RESTRICT
- ON UPDATE SET NULL

## 限制和注意事项

1. **表名映射**：MySQL表名直接映射到PostgreSQL，不进行名称转换
2. **数据类型**：假设表结构已经存在，只处理索引和外键
3. **字符集**：忽略MySQL的CHARACTER SET和COLLATE设置
4. **存储引擎**：忽略MySQL的ENGINE设置

## 错误处理

- **文件不存在**：如果找不到对应的SQL文件，给出提示并退出
- **表不存在**：如果目标PostgreSQL表不存在，给出错误提示
- **依赖缺失**：如果外键引用的表不存在，跳过该外键并记录警告
- **SQL错误**：捕获并记录PostgreSQL执行错误

## 示例输出

```
MySQL to PostgreSQL Schema Synchronization Tool
===============================================

Target table: business.规模明细
SQL file: tests/fixtures/legacy_db/schema/business/规模明细.sql

Found 4 indexes and 4 foreign keys in SQL file

[CHECK] Verifying target table exists... ✓
[CHECK] Verifying dependency tables... ✓

[INDEX] Creating idx_规模明细_客户名称... ✓
[INDEX] Creating idx_规模明细_年金账户号... ✓
[INDEX] Creating idx_规模明细_公司ID... ✓

[FOREIGN KEY] Adding fk_规模明细_产品线... ✓
[FOREIGN KEY] Adding fk_规模明细_年金计划... ✓
[FOREIGN KEY] Adding fk_规模明细_组合计划... ✓
[FOREIGN KEY] Adding fk_规模明细_组织架构... ✓

Migration completed successfully!
Total indexes created: 4
Total foreign keys added: 4
Skipped items: 0
```

## 技术实现

### SQL解析方案

本脚本使用 **SQLGlot** 库进行SQL解析，相比传统的正则表达式方案具有以下优势：

1. **准确性更高**：基于AST（抽象语法树）的解析方式，能够准确处理复杂的SQL语法
2. **可维护性更好**：代码结构清晰，易于理解和维护
3. **扩展性更强**：可以轻松支持更多的MySQL语法特性

### 解析流程

1. **读取SQL文件**：从指定路径读取MySQL的CREATE TABLE语句
2. **提取数据库名**：从SQL注释中提取数据库名（`-- 数据库: xxx`）
3. **解析表结构**：使用sqlglot解析CREATE TABLE语句，生成AST
4. **提取约束信息**：
   - 从Schema对象的expressions中提取列定义
   - 识别UniqueColumnConstraint（UNIQUE KEY）
   - 识别IndexColumnConstraint（普通KEY/INDEX）
   - 识别Constraint对象中的ForeignKey
5. **生成PostgreSQL DDL**：将MySQL约束转换为PostgreSQL兼容的DDL语句

### 约束类型映射

| MySQL约束类型 | SQLGlot表达式类型 | PostgreSQL DDL |
|--------------|------------------|----------------|
| PRIMARY KEY | PrimaryKey | 在CREATE TABLE中定义 |
| UNIQUE KEY | UniqueColumnConstraint | CREATE UNIQUE INDEX |
| KEY/INDEX | IndexColumnConstraint | CREATE INDEX |
| FOREIGN KEY | Constraint + ForeignKey | ALTER TABLE ADD CONSTRAINT |

## 开发说明

该脚本使用Python编写，依赖以下库：
- `sqlglot`: SQL解析和转换（核心依赖）
- `psycopg2-binary`: PostgreSQL数据库连接
- `argparse`: 命令行参数解析
- `logging`: 日志记录

扩展开发时，可以添加对更多MySQL特性的支持，如触发器、存储过程等。

## 版本历史

### v2.0 (当前版本)
- ✅ 使用SQLGlot替代正则表达式进行SQL解析
- ✅ 提升解析准确性和可维护性
- ✅ 支持更复杂的MySQL语法
- ✅ 完整的测试覆盖

### v1.0
- 基于正则表达式的SQL解析
- 基本的索引和外键迁移功能