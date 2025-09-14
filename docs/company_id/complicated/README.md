# Company ID 文档索引（问题定义 → 蓝图 → 子任务）

本目录汇总“company_id”全流程的业务与技术文档。推荐阅读顺序：

1) 问题与方案（主文）

- PROBLEM.CI-000_问题定义与解决方案.md

2) 蓝图与分解

- CI-002_企业信息查询集成与客户ID富化闭环_蓝图.md（总体导航与动机）

3) 子任务（执行单元）

- CI-002A_Provider与Gateway最小闭环.md
- CI-002B_缓存与名称索引与请求队列.md
- CI-002D_异步回填作业与队列消费者.md
- CI-002E_可观测性与运营指标.md
- CI-002F_真实Provider(EQC)实现与密钥管理.md
- CI-002G_Legacy爬虫适配与去副作用.md
- CI-002H_存量数据迁移与兼容导入(Mongo-MySQL到Postgres缓存).md
- CI-002C_同步小预算富化集成.md（可选，默认关闭）

4) 配置与参数

- CONFIG.CI-ENV.md（环境变量与默认值）

5) 历史/废弃

- superseded/ 下的文档（仅供参考）

说明：

- 遵循 KISS/YAGNI：先跑通异步闭环（A/B/D/E），真实 Provider 与 legacy 适配（F/G）按需推进；同步小预算（C）为可选项。
- 统一口径：下游建议使用视图/Join 方式统一规范 company_id，必要时再做批量硬化。
