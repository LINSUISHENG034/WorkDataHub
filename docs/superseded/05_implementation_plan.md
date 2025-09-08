# Annuity Hub 重构项目实施计划 (修订版)

> Note: This document is superseded by `docs/overview/01_system_overview.md` (2025-09-08). It is preserved for historical context. For current plan/status see `ROADMAP.md`.

## 1. 最终技术栈选型

*技术栈选型保持不变，确保了技术方向的稳定性。*

| 分类 | 技术选型 | 理由 |
| :--- | :--- | :--- |
| **语言** | Python 3.10+ | 利用其强大的类型提示系统，提升代码健壮性。 |
| **核心处理库** | Polars | 相比 Pandas，Polars 在大规模数据集上的性能更优，且其表达式API更符合现代数据处理范式。 |
| **数据校验** | Pydantic V2 | 强制的数据契约，确保数据质量，是构建健壮ETL管道的基石。 |
| **工作流编排器** | Dagster | 提供强大的数据资产目录、本地开发体验和清晰的声明式API，完美契合我们的架构愿景。 |
| **数据仓库** | PostgreSQL | 作为一个成熟、健壮的开源关系型数据库，是项目初期的最佳选择，未来可平滑迁移至云原生方案。 |
| **测试框架** | Pytest | 社区标准，功能强大，插件丰富，能够很好地支持我们的TDD策略。 |
| **CI/CD** | GitHub Actions | 与代码仓库紧密集成，配置简单，能够满足我们自动化的代码质量检查、测试和部署需求。 |
| **依赖管理** | UV | 遵循 `CLAUDE.md` 指导，使用 `uv` 进行高性能的依赖和虚拟环境管理。 |

## 2. 项目初始化与基线建立 (里程碑零)

**目标:** 消除关键风险，为后续开发奠定坚实基础。

| 任务 | 描述 | 验收标准 |
| :--- | :--- | :--- |
| ✅ **1. 初始化代码仓库** | 创建新的代码仓库 (`git init`)，并按照 `CLAUDE.md` 指导建立分层架构目录结构 (`src/annuity_hub`, `tests`, etc.)。 | 代码仓库已创建，包含清晰的、符合规范的初始目录结构。 |
| ✅ **2. 搭建开发环境** | 编写 `pyproject.toml`，使用 `uv` 初始化虚拟环境并安装核心依赖 (Polars, Pydantic, Pytest)。 | 开发者可以通过 `uv sync` 命令一键搭建起标准化的本地开发环境。 |
| **3. 建立CI/CD基础** | 配置 GitHub Actions，建立一个基础的CI流水线，包含代码风格检查 (Ruff)、类型检查 (Mypy) 和依赖安全扫描。 | 每次代码提交都会自动触发CI流水线，并报告代码质量问题。 |
| **4. 凭据外部化** | 将遗留系统中的所有硬编码凭据（数据库密码等）迁移至环境变量，并通过 Pydantic 的 `BaseSettings` 进行管理。 | 代码库中无可寻的明文凭据，所有敏感信息均通过环境变量加载。 |
| **5. 建立端到端测试基线** | 针对遗留系统最核心的一条数据处理路径，编写一个端到端的集成测试。该测试将调用 `legacy/annuity_hub/main.py`，验证“给定输入文件，得到预期的数据库输出”。 | 核心流程的端到端测试在CI环境中稳定通过，为后续重构提供安全网。 |

## 3. 核心基础设施部署 (生产环境优先)

**目标:** 搭建与生产环境一致的核心平台基础设施。

| 任务 | 描述 | 验收标准 |
| :--- | :--- | :--- |
| **1. 部署 PostgreSQL** | **(非Docker)** 根据生产环境的操作系统，使用官方包管理器直接安装和配置 PostgreSQL 服务。**如果已有可用的PostgreSQL实例，则直接配置连接信息。** | PostgreSQL 服务稳定运行，已为项目创建专用的数据库和用户，并且应用进程可以成功连接。 |
| **2. 部署 Dagster** | **(非Docker)** 创建独立的Python虚拟环境，安装所有依赖。配置 `dagster.yaml` 以连接到PostgreSQL。使用 `systemd` 或类似工具将 `dagster-webserver` 和 `dagster-daemon` 注册为系统服务。 | Dagster 的 Web UI 和守护进程作为系统服务稳定运行，可远程访问，并成功连接到PostgreSQL实例。 |

## 4. 领域服务重构 (里程碑一 & 二)

**目标:** 将所有业务逻辑重构为独立的、高质量的领域服务。

| 任务 | 描述 | 验收标准 |
| :--- | :--- | :--- |
| **1. 定义核心数据契约** | 使用 Pydantic 为每个核心业务领域（如年金业绩、健康险等）定义输入和输出的数据模型。 | 每个领域都有清晰、版本化的Pydantic模型，作为服务间通信的契约。 |
| **2. 重构领域服务** | 将 `data_cleaner.py` 中的逻辑，逐一重构为独立的、可测试的Python函数（领域服务）。每个服务都遵循“输入 -> 处理 -> 输出”的纯函数模式，并使用Pydantic模型进行输入输出校验。 | 所有业务逻辑均已迁移到独立的领域服务中，每个服务都有单元测试覆盖，代码覆盖率 > 90%。 |
| **3. 开发数据源连接器** | 开发一个可配置的 `DataSourceConnector`，能够根据YAML配置（正则表达式、版本发现策略）智能地发现和加载源文件。 | 连接器能够成功处理 `03_specified_data_source_problems_analysis.md` 中描述的所有复杂场景。 |
| **4. 开发数据仓库加载器** | 开发一个通用的 `DataWarehouseLoader`，负责将领域服务处理后的数据（Polars DataFrame）原子化地加载到PostgreSQL。 | 加载器支持 “先删后插” (基于主键) 和 “追加” 两种模式，并包含在事务中。 |

## 5. 端到端管道集成与验证 (里程碑三)

**目标:** 将所有组件集成为一个完整、可靠的数据处理管道。

| 任务 | 描述 | 验收标准 |
| :--- | :--- | :--- |
| **1. 编排ETL工作流** | 使用 Dagster 将 `DataSourceConnector`、各个领域服务和 `DataWarehouseLoader` 编排成一个完整的ETL工作流 (DAG)。 | 完整的ETL工作流可以在 Dagster 中被可视化和手动触发。 |
| **2. 数据比对验证** | 使用全量历史输入文件，并行运行新旧两个系统，并将新系统在PostgreSQL中生成的输出与旧系统在MySQL中的输出进行数据比对。 | 新旧系统输出的数据100%一致。任何不一致都需要被记录、分析和修复。 |
| **3. 建立监控与告警** | 在 Dagster 中为关键数据质量指标（如记录数、关键字段空值率、处理时长）添加传感器 (Sensors) 和告警。 | 当数据质量出现问题或管道运行失败时，能自动发送告警通知。 |

## 6. 项目交付与归档 (里程碑四)

**目标:** 完成项目交接，确保新平台可维护。

| 任务 | 描述 | 验收标准 |
| :--- | :--- | :--- |
| **1. 部署到生产环境** | 按照第3节中的非Docker部署方案，将新系统部署到最终的目标环境。 | 新系统在目标环境中成功运行，并处理生产数据。 |
| **2. 撰写技术文档** | 交付最终的架构图、服务接口说明 (基于Pydantic模型自动生成)、部署运维手册和开发者指南。 | 技术文档完整、清晰，能够指导新成员快速上手。 |
| **3. 归档遗留系统** | 将 `legacy/annuity_hub` 代码库设置为只读，并正式归档。 | 遗留代码库已归档，所有开发活动均在新代码库中进行。 |

---

## 附录：可选的本地开发环境 (Docker Compose)

为方便开发者快速搭建隔离的本地开发环境，项目将提供一个 `docker-compose.yml` 文件。

```yaml
# docker-compose.yml (示例)
version: '3.8'
services:
  postgres:
    image: postgres:13
    environment:
      POSTGRES_USER: dagster_user
      POSTGRES_PASSWORD: dagster_password
      POSTGRES_DB: dagster_db
    ports:
      - "5432:5432"

  dagster-webserver:
    build:
      context: .
      dockerfile: ./Dockerfile
    entrypoint:
      - "dagster-webserver"
      - "-h"
      - "0.0.0.0"
      - "-p"
      - "3000"
    ports:
      - "3000:3000"
    environment:
      DAGSTER_POSTGRES_USER: dagster_user
      DAGSTER_POSTGRES_PASSWORD: dagster_password
      DAGSTER_POSTGRES_DB: dagster_db
      DAGSTER_POSTGRES_HOST: postgres
    volumes:
      - .:/app
    depends_on:
      - postgres

# ... (dagster-daemon 服务类似)
```
**使用方法:** 开发者在本地只需运行 `docker-compose up` 即可启动包含PostgreSQL和Dagster的完整开发环境。
