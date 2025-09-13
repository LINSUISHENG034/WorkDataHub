# INITIAL.CI-002F — 真实 Provider（EQC）实现与密钥管理

目的：提供可用于生产的 EQC Provider 实现，纳入 `EnterpriseInfoProvider` 协议体系，统一密钥管理、速率/重试控制与响应规范化。

## FEATURE
- 实现 `EqcProvider`（`search_by_name` / `get_by_id`），返回标准 `CompanyCandidate/CompanyDetail`。
- 环境与密钥：`WDH_PROVIDER_EQC_TOKEN`（必需），`WDH_PROVIDER_EQC_BASE_URL`（可选，默认官方）。
- 健壮性：超时、重试（指数退避）、速率限制（每秒/每分钟），错误分类与可观测日志。
- 安全：不在日志打印明文 Token；遵循 `docs/security/SECRETS_POLICY.md`。

## SCOPE
- In-scope：HTTP 客户端、响应解析/映射、错误/限流处理、配置读取、单元测试（基于本地 fixtures 或假服务）。
- Non-goals：不引入新依赖（优先使用标准库/现有依赖）；不实现多 Provider 聚合（由 Gateway 完成）。

## CONTRACTS（接口约定）
- `search_by_name(name:str)->List[CompanyCandidate]`：按规范化名称查询，返回按 score 排序的候选。
- `get_by_id(id:str)->CompanyDetail|None`：按唯一 ID 获取详情（若 EQC 支持）。
- 约束：
  - score：0–1 浮点；官方名精确匹配得分最高；别名/相似度次之。
  - 字段映射：`unite_code`、`official_name`、`aliases` 从 EQC 字段派生；缺失字段置空。

## VALIDATION
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k eqc_provider
```

## ACCEPTANCE CRITERIA
- 具备限流与重试；离线测试使用 fixtures 稳定通过；返回结构稳定且与 Gateway 兼容；不泄露密钥到日志。

## RISKS
- EQC 接口变更：封装解析层，集中维护字段映射；必要时引入版本标识。

