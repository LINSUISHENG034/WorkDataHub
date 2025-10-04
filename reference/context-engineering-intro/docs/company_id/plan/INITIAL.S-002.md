# INITIAL — S-002 EQC 客户端集成（KISS/YAGNI）

本 INITIAL 定义了 S-002 的最小实现范围、边界、样例、集成点、风险与验证步骤，用于驱动 Claude 生成并执行 PRP 与实现代码。目标是基于最少抽象，直接提供一个可用的 EQC 客户端，支持公司搜索与详情查询，并通过标准校验门（ruff/mypy/pytest）。

## 背景与目标

- 背景：参见 `docs/company_id/simplified/S-002_EQC客户端集成.md`。我们需要一个“无抽象层”的最小 EQC 客户端，避免过度设计，优先可用性与可测试性。
- 目标：提供 `EQCClient`，可用 `token` 直接调用 EQC 接口，完成“按名称搜索公司”和“获取公司详情”两条主路径。错误处理、限流、超时和重试为最小必要实现。

## 范围（Scope）

In-scope（必须实现）
- 新建 `EQCClient` 类，接口：
  - `search_company(name: str) -> List[CompanySearchResult]`
  - `get_company_detail(company_id: str) -> CompanyDetail`
- 数据模型：`CompanySearchResult`、`CompanyDetail`（Pydantic v2）。
- 基本错误处理：401（认证失败）、404（未找到）、429（限流）、5xx（服务器错误）、超时。
- 简单重试（指数退避 + 抖动）与速率限制（每分钟 N 次，可配置）。
- 凭据管理：默认从 `WDH_EQC_TOKEN` 环境变量读取；不在客户端内实现自动登录。
- 单元测试（使用 mock，不依赖真实网络/API）。

Out-of-scope（明确不做）
- Provider/Gateway 抽象层与多 Provider 聚合。
- 复杂评分/打分与领域标签解析。
- GUI 或浏览器自动过滑块增强逻辑（此为 S-002 之外主题）。

## 参考与样例

- Legacy 用法与请求头示例：`legacy/annuity_hub/crawler/eqc_crawler.py`
  - 关键点：token 置于请求头 `token`，而非 `Authorization`；`Referer` 需为 `https://eqc.pingan.com/`。
- 连接器风格参考：`src/work_data_hub/io/connectors/file_connector.py`
- 领域模型结构参考：`src/work_data_hub/domain/annuity_performance/service.py`
- 简化路线图：`docs/company_id/simplified/README.md`、`docs/company_id/simplified/S-002_EQC客户端集成.md`

API 端点（根据 S-002 文档与 legacy 约定）：
- 搜索：`GET https://eqc.pingan.com/kg-api-hfd/api/search/searchAll?keyword=<encoded>&currentPage=1&pageSize=10`
- 详情：`GET https://eqc.pingan.com/kg-api-hfd/api/search/findDepart?targetId=<company_id>`

Headers（最小必要）：
- `token: <WDH_EQC_TOKEN>`
- `Referer: https://eqc.pingan.com/`
- `User-Agent: Mozilla/5.0 ...`（通用）

## 变更清单（文件与位置）

新增
- `src/work_data_hub/io/connectors/eqc_client.py`
  - 定义 `EQCClient` 与异常类型（见下方异常规范）。
  - 使用 `requests.Session`，支持超时、重试、速率限制与日志化（脱敏）。
- 数据模型（两种等价方式，二选一）：
  1) `src/work_data_hub/domain/company_enrichment/eqc_models.py`
  2) 或在既有 `src/work_data_hub/domain/company_enrichment/models.py` 中新增 `CompanySearchResult`、`CompanyDetail`

修改
- `src/work_data_hub/config/settings.py`
  - 新增可选配置（带 `WDH_` 前缀）：
    - `eqc_enabled: bool = True`（env: `WDH_EQC_ENABLED`）
    - `eqc_timeout: int = 30`（env: `WDH_EQC_TIMEOUT`）
    - `eqc_rate_limit: int = 10`（env: `WDH_EQC_RATE_LIMIT`，每分钟最大请求数）
    - `eqc_retry_max: int = 3`（env: `WDH_EQC_RETRY_MAX`）
    - `eqc_base_url: str = "https://eqc.pingan.com"`（env: `WDH_EQC_BASE_URL`）
  - 不强制新增 `WDH_EQC_TOKEN` 字段（由 `os.getenv("WDH_EQC_TOKEN")` 直接读取，以保持简化）。

测试
- `tests/io/connectors/test_eqc_client.py`
  - 使用 `requests` mock 覆盖：成功、空结果、401、404、429（含重试）、5xx、超时。
  - 集成测试（可选、跳过默认）：标记 `@pytest.mark.eqc_integration`，仅在设置了 `WDH_EQC_TOKEN` 时运行真实请求（可只断言 401/200 行为，不依赖具体数据）。

文档
- 在 `README.md` “EQC Token (Company ID MVP)” 小节补充最小用法（见“用法示例”）。

## 接口与数据模型（精确规范）

异常类型（放在 `eqc_client.py` 内即可）：
- `class EQCClientError(Exception)` — 基类
- `class EQCAuthenticationError(EQCClientError)` — 401
- `class EQCRateLimitError(EQCClientError)` — 429（重试达到上限后抛出）
- `class EQCNotFoundError(EQCClientError)` — 404

数据模型（Pydantic v2）：
```python
from pydantic import BaseModel, Field
from typing import List, Optional

class CompanySearchResult(BaseModel):
    company_id: str = Field(..., description="EQC公司ID，字符串化")
    official_name: str = Field(..., description="官方名称")
    unite_code: Optional[str] = Field(None, description="统一社会信用代码")
    match_score: float = Field(0.0, ge=0.0, le=1.0)

class CompanyDetail(BaseModel):
    company_id: str
    official_name: str
    unite_code: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    business_status: Optional[str] = None
```

`EQCClient` 签名：
```python
class EQCClient:
    def __init__(self, token: Optional[str] = None, *, timeout: int = 30, retry_max: int = 3, rate_limit: int = 10):
        ...

    def search_company(self, name: str) -> List[CompanySearchResult]:
        """名称搜索。对中文进行 URL 编码，返回结构化结果。401/429/5xx 含重试，超时与异常按规范抛出。"""

    def get_company_detail(self, company_id: str) -> CompanyDetail:
        """详情查询。将响应字段映射为 CompanyDetail。"""
```

实现要点
- `token` 优先顺序：构造参数 > `os.getenv("WDH_EQC_TOKEN")`；为空时报错 `EQCAuthenticationError`。
- 统一 headers：包含 `token`、`Referer`、`User-Agent`。
- 速率限制：最简单实现（每次请求前 `sleep` 基于窗口节流，或令牌桶均可，保持可读性）。
- 重试：对 `429` 与 `>=500` 使用指数退避（建议 `base=0.5~1s`，`factor=2`，随机抖动±20%）。到达上限后：
  - 429 抛 `EQCRateLimitError`；
  - 5xx 抛 `EQCClientError`。
- 日志：仅记录请求摘要（方法/路径/状态码/耗时），禁止输出完整 token 与敏感 URL 查询串（可截断）。
- 响应解析：将 EQC 字段名（如 `companyId/companyName/uniteCode/aliases/businessStatus`）映射为模型字段。非必需字段缺失时安全降级为 `None`/空列表。

## 用法示例（README 可复用）

```python
from src.work_data_hub.io.connectors.eqc_client import EQCClient

# export WDH_EQC_TOKEN=....  # 30分钟有效
client = EQCClient(timeout=30, retry_max=3, rate_limit=10)

results = client.search_company("中国平安")
if results:
    detail = client.get_company_detail(results[0].company_id)
    print(detail.official_name, detail.unite_code)
```

## 校验步骤（Validation Gates）

命令（全部需通过）：
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k "test_eqc_client"

# 可选：集成测试（需要真实 token）
export WDH_EQC_TOKEN=your_token_here
uv run pytest -v tests/io/connectors/test_eqc_client.py::test_integration -m eqc_integration
```

## 验收标准（Acceptance Criteria）
- [ ] `EQCClient.search_company` 返回结构化结果（空结果可返回空列表）
- [ ] `EQCClient.get_company_detail` 返回结构化详情
- [ ] 覆盖错误处理：401/404/429/5xx/超时，并按规范抛出异常
- [ ] 含基本的重试与超时保护，速率限制生效
- [ ] 单元测试使用 mock，不依赖真实 API；集成测试可选
- [ ] 日志脱敏与最小必要记录
- [ ] ruff、mypy、pytest 均为绿色

## 风险与注意事项（Gotchas）
- Token 30 分钟有效，非本任务负责自动刷新；失败返回 401 时应给出明确错误。
- EQC 响应字段可能为数字或字符串（如 companyId），一律转换为 `str` 存储于模型。
- 429：需重试并在上限后抛出 `EQCRateLimitError`，避免无限重试。
- 中文编码：查询参数需 URL 编码；注意 `requests` 正确传参（如 `params`）。
- 不泄露敏感信息：日志严格脱敏，不打印 token。

## 与 ROADMAP 对齐
- 任务：Milestone 1.5 — Company ID Enrichment，S-002（无抽象层的 EQC 客户端）。
- 后续阶段：S-003 基础缓存机制、S-004 MVP 端到端验证；仅在本任务通过所有验证门后推进。

