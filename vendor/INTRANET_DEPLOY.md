# 内网离线部署指南

本文档面向无法直接访问外部 PyPI（如公司内网隔离环境）的部署场景。依赖包已预先下载至 `vendor/wheels/` 目录，可完全离线完成安装。

---

## 前置条件

| 依赖 | 要求 | 说明 |
|------|------|------|
| Python | ≥ 3.10（已安装到系统） | 内网机器需提前安装 |
| uv | latest（推荐） | 如未安装也可用 pip 替代（见方式二） |

## 目录结构

```
vendor/
├── INTRANET_DEPLOY.md      ← 本文档
├── requirements.txt        ← 完整依赖清单（由 uv pip compile 生成）
└── wheels/                 ← 预下载的 wheel 包（约 170 MB）
```

---

## 方式一：使用 uv 离线部署（推荐）

> `uv.lock` 锁定了生成时的精确 Python 版本（如 3.12.10）。若内网系统安装的是不同 patch 版本（如 3.12.9），只需删除 `.python-version` 文件，并配合 `--no-sync` 参数即可完全离线运行。

```cmd
REM 1. 强制 uv 使用系统 Python（整个部署流程只需设置一次）
set UV_PYTHON_PREFERENCE=only-system

REM 2. 移除精确的 Python 版本锁定（切勿执行 uv lock）
del .python-version

REM 3. 创建虚拟环境
uv venv --python 3.12

REM 4. 从本地 wheel 包离线安装所有依赖（已含 psycopg v3，解决中文 Windows 的 UnicodeDecodeError）
uv pip install --find-links vendor/wheels --no-index -r vendor/requirements.txt

REM 5. (可选) 安装 pre-commit 钩子
REM 若提示 program not found，是因为之前导出包时未开启 --all-groups，纯部署可直接跳过此步！
uv run --no-sync pre-commit install

REM 6. 配置环境变量（编辑 .wdh_env，填写数据库连接等，详见主部署指南）
REM ⚠️ 重要提示：在 .wdh_env 中填写 Windows 目录路径（如 WDH_DATA_BASE_DIR）时，
REM 请务必使用单引号包裹：'D:\Share\Data'，或者使用正斜杠：D:/Share/Data
REM 否则会报 Failed to parse environment file 错误！

REM 7. 执行数据库迁移（必须加 --no-sync 防止自动联网）
uv run --no-sync --env-file .wdh_env alembic upgrade head
```

> **提示**：如需永久免去每次 `set UV_PYTHON_PREFERENCE`，可在项目根目录创建 `uv.toml`，写入 `python-preference = "only-system"`。

---

## 方式二：使用 pip 离线部署（无需 uv）

```cmd
REM 1. 创建并激活虚拟环境
python -m venv .venv
.venv\Scripts\activate

REM 2. 从本地 wheel 包离线安装所有依赖（已含 psycopg v3，解决中文 Windows 的 UnicodeDecodeError）
pip install --find-links vendor/wheels --no-index -r vendor/requirements.txt

REM 3. (可选) 安装 pre-commit 钩子（若提示找不到命令，纯部署可跳过）
pre-commit install

REM 4. 配置环境变量（编辑 .wdh_env）

REM 5. 执行数据库迁移
set PYTHONPATH=src
alembic upgrade head
```

---

## 如何更新 vendor 包

当项目依赖发生变更时，需在**有外网的机器**上重新导出：

```cmd
REM 1. 重新生成依赖清单（加 --all-groups 包含 pre-commit 等开发依赖）
uv export --all-groups --no-hashes --format requirements-txt -o vendor/requirements.txt

REM 2. 安装 pip 到虚拟环境（如尚未安装）
uv pip install pip

REM 3. 重新下载所有 wheel 包
uv run python -m pip download -r vendor/requirements.txt -d vendor/wheels

REM 4. 额外下载 psycopg v3 wheel（中文 Windows 必需）
uv run python -m pip download psycopg psycopg-binary -d vendor/wheels --only-binary=:all: --python-version 3.12 --platform win_amd64
```

然后将更新后的 `vendor/` 目录同步到内网环境。

---

## 注意事项

- `vendor/wheels/` 中的包针对 **Windows x86_64 + Python 3.12** 平台下载，如目标环境的操作系统或 Python 版本不同，需重新导出。
- 建议在 `.gitignore` 中添加 `vendor/wheels/` 避免将大量二进制文件提交到 Git。
- 后续操作（ETL 运行、Dagster UI 等）请参阅 [部署与运行指南](../docs/deployment_run_guide.md)。

## 常见问题

| 问题现象 | 原因 | 解决方案 |
|----------|------|----------|
| `alembic upgrade head` 报 `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd6` | 中文 Windows 系统区域为 GBK（代码页 936），psycopg2 的 C 扩展无法解码 libpq 返回的 GBK 编码信息 | 安装 `psycopg`（v3）：`uv pip install psycopg`。项目已在 `env.py` 中自动切换到 psycopg v3 驱动 |
