# MySQL to PostgreSQL 迁移脚本优化实施计划

## 目标
将现有的基于正则表达式的 SQL 解析器 (`sql_parser.py`) 替换为基于 `sqlglot` 的解析器 (`sqlglot_parser.py`)，以提高 SQL 解析的准确性和对复杂语法的支持能力。

## 实施步骤

### 第一阶段：验证与修复 (已完成 ✅)
1.  **环境验证**：确认 `sqlglot` 库已安装且版本兼容（已确认版本 28.1.0）。
2.  **修复 `sqlglot_parser.py`**：
    -   [x] 修正 `stmt.kind` 判断逻辑，适配 `sqlglot` 新版本的字符串返回类型 (将 `isinstance(stmt.kind, exp.Table)` 改为 `str(stmt.kind).upper() == "TABLE"`).
    -   [x] 修复表名提取逻辑，正确处理 Schema 对象结构
    -   [x] 修复约束提取逻辑，从 Schema.expressions 中提取索引和外键
    -   [x] 修复 UniqueColumnConstraint 和 IndexColumnConstraint 的列名提取
    -   [x] 修复 ForeignKey 的引用表和列提取
    -   [x] 运行脚本验证修复后的解析功能。

### 第二阶段：重构 `sync_schema.py` (已完成 ✅)
1.  **替换引用**：
    -   [x] 修改 `sync_schema.py`，将引用从 `sql_parser` 切换到 `sqlglot_parser`。
    -   [x] 引入 `SQLGlotParser` 类替代 `MySQLSQLParser`。
2.  **适配接口**：
    -   [x] `sqlglot_parser.py` 中的 `MySQLTableDefinition`、`MySQLIndex`、`MySQLForeignKey` 类结构与原代码保持兼容。
    -   [x] 确保 `SchemaSynchronizer` 类初始化时正确实例化 `SQLGlotParser`。
    -   [x] 更新所有其他文件的引用：`ddl_generator.py`, `test_sync.py`, `__init__.py`

### 第三阶段：测试与验证 (已完成 ✅)
1.  **Dry Run 测试**：
    -   [x] 使用 `--dry-run` 模式运行 `sync_schema.py`，验证新解析器生成的 DDL 语句。
    -   [x] 命令示例：`PYTHONPATH=src uv run python scripts/migrations/mysql_to_postgres_sync/sync_schema.py --table business.规模明细 --dry-run`
    -   [x] 验证结果：成功解析 8 个索引和 4 个外键，DDL 生成正确
2.  **复杂用例测试**：
    -   [x] 测试包含复杂 `CREATE TABLE` 语法的 SQL 文件，验证 `sqlglot` 的解析优势。

### 第四阶段：清理与交付 (已完成 ✅)
1.  **清理历史文件**：
    -   [x] 确认新方案稳定后，删除旧的解析模块 `scripts/migrations/mysql_to_postgres_sync/sql_parser.py`。
    -   [x] 删除临时调试脚本（`debug_sqlglot.py`）。
    -   [x] 删除临时文档（`requirements_optimized.txt`, `SETUP_OPTIMIZATION.md`, `OPTIMIZATION_PLAN.md`）。
2.  **更新文档**：
    -   [x] 更新 `IMPLEMENTATION_PLAN.md` 标记所有阶段已完成。
    -   [x] 更新 `README.md` 说明当前使用的解析方案。

## 实施总结

### 完成情况
✅ **所有四个阶段已成功完成**

### 主要改进
1. **解析准确性提升**：使用 `sqlglot` 库替代正则表达式，能够准确解析复杂的 MySQL CREATE TABLE 语法
2. **代码可维护性提升**：基于 AST 的解析方式更加可靠和易于维护
3. **功能完整性**：成功提取所有索引（包括 UNIQUE 和普通索引）和外键约束

### 测试结果
- ✅ 成功解析 8 个索引（1 个 UNIQUE + 7 个普通索引）
- ✅ 成功解析 4 个外键约束
- ✅ 正确提取索引名称和列名
- ✅ 正确提取外键引用表和列
- ✅ 正确提取 ON DELETE 和 ON UPDATE 动作

### 技术要点
1. **Schema 对象处理**：sqlglot 将 CREATE TABLE 解析为 Schema 对象，需要从 `create_stmt.this.args['expressions']` 中提取列定义和约束
2. **约束类型**：
   - `UniqueColumnConstraint`：UNIQUE KEY 约束
   - `IndexColumnConstraint`：普通 KEY/INDEX 约束
   - `Constraint`：包含 ForeignKey 的约束
3. **列名提取**：需要从 Identifier 对象的 `this` 属性中提取实际列名字符串

## 预期结果
- 移除对脆弱正则表达式的依赖。
- 提升脚本的可维护性和对不同 MySQL SQL 语法的兼容性。
- 代码结构更加清晰。
