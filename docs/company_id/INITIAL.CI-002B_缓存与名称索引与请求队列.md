# INITIAL.CI-002B — 缓存与名称索引与请求队列（DDL/DAO）

目的：建立最小可用的企业主数据缓存、名称索引与富化请求队列表及 DAO，支撑后续同步/异步富化闭环。

## FEATURE
- PostgreSQL 最小 DDL：`enterprise.company_master`、`enterprise.company_name_index`、`enterprise.enrichment_requests`。
- 只读/写 DAO：插入/更新 master 与 name_index；请求队列的入队、取出、标记完成/失败。

## SCOPE
- In-scope：DDL 脚本、轻量 DAO（基于 psycopg2，仿 ops 中连接获取模式）、基础索引与约束。
- Non-goals：不实现复杂事务/重试；不改动 pipeline；不接入外部 Provider。

## DDL（最小）
```sql
CREATE SCHEMA IF NOT EXISTS enterprise;
CREATE TABLE IF NOT EXISTS enterprise.company_master (
  company_id  VARCHAR(50) PRIMARY KEY,
  official_name TEXT NOT NULL,
  unite_code  TEXT,
  aliases     TEXT[],
  source      TEXT,
  updated_at  TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS enterprise.company_name_index (
  norm_name   TEXT PRIMARY KEY,
  company_id  VARCHAR(50) NOT NULL REFERENCES enterprise.company_master(company_id),
  match_type  TEXT,
  updated_at  TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS enterprise.enrichment_requests (
  id          BIGSERIAL PRIMARY KEY,
  raw_name    TEXT NOT NULL,
  norm_name   TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'pending',
  attempts    INT  NOT NULL DEFAULT 0,
  last_error  TEXT,
  requested_at TIMESTAMPTZ DEFAULT now(),
  updated_at   TIMESTAMPTZ DEFAULT now()
);
```

## VALIDATION
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k company_cache
```

## ACCEPTANCE CRITERIA
- DDL 可在本地测试库创建成功；DAO 可完成基本 upsert 与入队/取出/标记；类型检查与测试通过。

## RISKS
- search_path 差异：在 DAO 层明确 schema 限定（enterprise.前缀）。

