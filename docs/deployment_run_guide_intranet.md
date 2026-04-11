# WorkDataHub 内网部署与运行指南

> Source of truth: `src/work_data_hub/cli/etl/main.py`, `config/data_sources.yml`
> Last verified: `2026-04-11`
> Scope: ETL execution and deployment operations

本文档面向无法直接访问外部 PyPI 的内网环境。核心原则只有两条：

- 依赖安装优先使用 `vendor/` 内的离线产物。
- 所有 `uv run` 命令都带 `--no-sync`，避免联网同步。

## 相关文档

- [文档总览](./index.md)
- [普通部署与运行指南](./deployment_run_guide.md)
- [参考资料](./reference/README.md)

## 离线依赖准备

项目内置以下离线依赖目录：

```text
vendor/
├── requirements.txt
└── wheels/
```

推荐命令：

```powershell
$env:UV_PYTHON_PREFERENCE='only-system'
Remove-Item .python-version -ErrorAction SilentlyContinue
uv venv --python 3.12
uv pip install --find-links vendor/wheels --no-index -r vendor/requirements.txt
```

## 环境变量

`.wdh_env` 至少需要：

```env
PYTHONPATH=src
DATABASE_URL=postgresql://user:password@localhost:5432/postgres
WDH_INTRANET=true
PA_UM_ACCOUNT=your_account
PA_UM_PASSWORD=your_password
```

如需浏览器相关命令，还应设置：

```env
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
```

## 数据库准备

```bash
uv run --no-sync --env-file .wdh_env alembic upgrade head
```

## 内网专用传输 GUI

```bash
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli intranet-deploy-gui
```

该命令用于打包或组装 `.7z` 部署产物，默认保留目标机上的 `config/data_sources.yml` 与 `.wdh_env`。

## 手动执行 ETL

内网环境的命令格式与普通环境一致，只是统一增加 `--no-sync`。

```bash
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl --help
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl --check-db
```

```bash
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl \
  --domains annuity_performance \
  --period 202411 \
  --plan-only
```

```bash
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl \
  --domains annual_award \
  --period 202411 \
  --no-enrichment \
  --execute
```

```bash
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl \
  --all-domains \
  --period 202411 \
  --file-selection newest \
  --execute
```

## 参数参考

| 参数 | 说明 |
|------|------|
| `--domains` | 单域或多域执行入口 |
| `--all-domains` | 执行所有已配置活动域 |
| `--period` | 账期，格式为 `YYYYMM` |
| `--plan-only` | 仅执行计划，不写库 |
| `--execute` | 真正写库 |
| `--file-selection` | 多文件匹配策略 |
| `--no-enrichment` | 关闭企业解析；内网常用 |
| `--no-post-hooks` | 禁用后置 Hook |
| `--check-db` | 数据库连通性检查 |

## 验证

```bash
uv run --no-sync --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --plan-only
uv run --no-sync --env-file .wdh_env python scripts/quality/check_docs_alignment.py
```

## 常见问题

| 问题 | 处理方式 |
|------|----------|
| `invalid peer certificate: UnknownIssuer` | 确认所有 `uv run` 命令都带 `--no-sync`。 |
| `Failed to parse environment file` | 检查 `.wdh_env` 中 Windows 路径是否加引号或改为正斜杠。 |
| `Executable doesn't exist` | 为 Playwright 指定系统浏览器路径。 |
| `Candidates found: 0` | 核对 `config/data_sources.yml` 的路径、账期目录和文件命名。 |
