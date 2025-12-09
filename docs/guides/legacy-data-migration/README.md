# Legacy 数据迁移指南

本文档说明如何访问从 MySQL 迁移到 PostgreSQL 的 legacy 数据。

## 数据库配置

### PostgreSQL 连接信息

| 配置项 | 值 |
|--------|-----|
| **Host** | `localhost` |
| **Port** | `5432` |
| **Database** | `legacy`（建议专用库） |
| **User** | `postgres` |
| **Password** | 见 `.env` 文件 `WDH_DATABASE_PASSWORD` |

### 连接字符串

```
postgresql://postgres:<password>@localhost:5432/legacy
```

### 环境变量配置

```bash
# .env 文件中的相关配置（推荐将迁移数据写入 legacy 数据库）
WDH_DATABASE_HOST=localhost
WDH_DATABASE_PORT=5432
WDH_DATABASE_USER=postgres
WDH_DATABASE_PASSWORD=<your_password>
# 默认应用库（与迁移库分离）
WDH_DATABASE_DB=postgres
# 迁移目标库（新增）
LEGACY_DATABASE_DB=legacy

# 可选 URI（优先级高于上面的 host/port/user/password/db）
WDH_DATABASE__URI=postgres://postgres:<password>@localhost:5432/postgres
# 可选：迁移专用 URI（优先于 DATABASE_URL 和 WDH_DATABASE__URI）
# LEGACY_DATABASE__URI=postgres://postgres:<password>@localhost:5432/legacy
```

## 数据库映射关系

Legacy MySQL 数据库已迁移到 PostgreSQL，每个原数据库对应一个独立的 Schema：

| 原 MySQL 数据库 | PostgreSQL Schema | 表数量 | 预估行数 |
|-----------------|-------------------|--------|----------|
| `mapping` | `mapping` | 11 | ~13,753 |
| `business` | `business` | 9 | ~798,879 |
| `customer` | `customer` | 21 | ~32,763 |
| `finance` | `finance` | 7 | ~3,160 |
| **合计** | - | **48** | **~848,555** |

## 查询示例

### 基本查询

```sql
-- 查询 mapping schema 下的表
SELECT * FROM mapping."年金客户" LIMIT 10;
SELECT * FROM mapping."组织架构";

-- 查询 business schema 下的表
SELECT * FROM business."收入明细" LIMIT 10;
SELECT * FROM business."规模明细";

-- 查询 customer schema 下的表
SELECT * FROM customer."企年受托已客";
SELECT * FROM customer."年金已客名单2024";

-- 查询 finance schema 下的表
SELECT * FROM finance."减值计提";
SELECT * FROM finance."年金费率统计";
```

### 元数据查询

```sql
-- 列出某个 schema 下的所有表
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'mapping'
ORDER BY table_name;

-- 列出所有 legacy schema
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name IN ('mapping', 'business', 'customer', 'finance');

-- 查看表结构
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'mapping' AND table_name = '年金客户';

-- 统计各 schema 的表数量
SELECT table_schema, COUNT(*) as table_count
FROM information_schema.tables
WHERE table_schema IN ('mapping', 'business', 'customer', 'finance')
GROUP BY table_schema;
```

### 使用 psql 连接

```bash
# 连接数据库
PGPASSWORD="<password>" psql -h localhost -U postgres -d postgres

# 列出 schema
\dn

# 切换到指定 schema
SET search_path TO mapping;

# 列出当前 schema 的表
\dt

# 查看表结构
\d "年金客户"
```

## 表清单

### mapping (11 张表)

| 表名 | 说明 |
|------|------|
| 产品明细 | 产品详细信息 |
| 产品线 | 产品线定义 |
| 全量客户 | 全量客户列表 |
| 利润指标 | 利润指标数据 |
| 客户灌入 | 客户导入数据 |
| 年金客户 | 年金客户信息 |
| 年金计划 | 年金计划定义 |
| 管理架构 | 管理架构信息 |
| 组合计划 | 组合计划数据 |
| 组织架构 | 组织架构信息 |
| 计划层规模 | 计划层规模数据 |

### business (9 张表)

| 表名 | 说明 |
|------|------|
| 企康缴费 | 企业健康险缴费数据 |
| 团养缴费 | 团体养老险缴费数据 |
| 手工调整 | 手工调整记录 |
| 提费扩面 | 提费扩面数据 |
| 收入明细 | 收入明细记录 |
| 灌入数据 | 数据导入记录 |
| 组合业绩 | 组合业绩数据 |
| 规模明细 | 规模明细数据 |
| 账管数据 | 账户管理数据 |

### customer (21 张表)

| 表名 | 说明 |
|------|------|
| 企年受托中标 | 企业年金受托中标客户 |
| 企年受托已客 | 企业年金受托已有客户 |
| 企年受托战客 | 企业年金受托战略客户 |
| 企年受托流失 | 企业年金受托流失客户 |
| 企年投资中标 | 企业年金投资中标客户 |
| 企年投资估值流失 | 企业年金投资估值流失 |
| 企年投资已客 | 企业年金投资已有客户 |
| 企年投资战客 | 企业年金投资战略客户 |
| 企年投资新增组合 | 企业年金投资新增组合 |
| 企年投资流失 | 企业年金投资流失客户 |
| 团养中标 | 团体养老中标客户 |
| 外部受托客户 | 外部受托客户信息 |
| 年金已客名单2023 | 2023年年金已有客户名单 |
| 年金已客名单2024 | 2024年年金已有客户名单 |
| 战区客户名单 | 战区客户名单 |
| 投资客户分摊比例表 | 投资客户分摊比例 |
| 续签客户清单 | 续签客户清单 |
| 职年受托已客 | 职业年金受托已有客户 |
| 职年投资已客 | 职业年金投资已有客户 |
| 职年投资待遇支付 | 职业年金投资待遇支付 |
| 职年投资新增组合 | 职业年金投资新增组合 |

### finance (7 张表)

| 表名 | 说明 |
|------|------|
| 减值计提 | 减值计提数据 |
| 历史浮费 | 历史浮动费用 |
| 固费分摊比例 | 固定费用分摊比例 |
| 年金费率统计 | 年金费率统计数据 |
| 考核收入明细 | 考核收入明细 |
| 考核收入预算 | 考核收入预算 |
| 风准金余额表 | 风险准备金余额 |

## 迁移脚本

### 脚本位置

```
scripts/migrations/
├── mysql_dump_migrator/          # 迁移模块
│   ├── __init__.py
│   ├── parser.py                 # MySQL dump 解析器
│   ├── converter.py              # MySQL → PostgreSQL 转换器
│   ├── migrator.py               # 迁移执行器
│   └── cli.py                    # CLI 接口
└── migrate_mysql_dump_to_postgres.py  # 主入口脚本
```

### 使用方法

```bash
# 扫描 dump 文件，查看可用数据库
uv run --env-file .env python scripts/migrations/migrate_mysql_dump_to_postgres.py scan

# Dry-run 模式（不实际写入数据库）
uv run --env-file .env python scripts/migrations/migrate_mysql_dump_to_postgres.py --dry-run

# 执行正式迁移
uv run --env-file .env python scripts/migrations/migrate_mysql_dump_to_postgres.py

# 迁移指定数据库
uv run --env-file .env python scripts/migrations/migrate_mysql_dump_to_postgres.py \
    --databases mapping finance
```

## 注意事项

1. **中文表名**：PostgreSQL 中使用双引号引用中文表名，如 `mapping."年金客户"`
2. **Schema 隔离**：每个原 MySQL 数据库对应独立的 PostgreSQL Schema，避免表名冲突
3. **数据类型**：MySQL 数据类型已自动转换为 PostgreSQL 兼容类型
4. **编码**：所有数据使用 UTF-8 编码
5. **目标数据库**：迁移前请确认目标数据库（如 `legacy`）已创建。迁移脚本会自动创建所需 schema，但不会创建数据库本身。
6. **URI 规范化**：如使用 `postgres://` 形式，内部会自动转换为 `postgresql://` 供 SQLAlchemy 使用。

## 相关文档

- 源数据备份文件：`tests/fixtures/legacy_db/alldb_backup_20251208.sql`
- 环境配置：`.env`
