# S-002 — EQC客户端集成（无抽象层）

直接实现EQC企业查查客户端，提供简单的公司信息查询功能，避免过度抽象。

## FEATURE

基于legacy/annuity_hub/crawler/eqc_crawler.py实现简化的EQCClient类，提供公司搜索和详情查询功能。

## SCOPE

### In-scope
- 实现EQCClient类，支持按公司名称搜索
- 支持获取公司详细信息（官方名、统一社会信用代码、别名）
- 基本的错误处理和重试机制
- 认证凭据管理（环境变量）
- 简单的速率限制保护
- 单元测试和集成测试

### Non-goals
- 不实现Provider抽象接口
- 不实现复杂的评分算法
- 不实现多Provider聚合功能
- 不实现GUI界面
- 不处理复杂的业务标签解析

## CONTEXT SNAPSHOT

```bash
src/work_data_hub/
  io/
    connectors/
      eqc_client.py              # 新增EQC客户端
  domain/
    company_enrichment/
      models.py                  # 响应数据模型
      service.py                 # 使用EQC客户端的服务
tests/
  io/
    connectors/
      test_eqc_client.py         # 客户端测试
  fixtures/
    eqc_responses/               # 模拟响应数据
```

## EXAMPLES

- Path: `legacy/annuity_hub/crawler/eqc_crawler.py` — 原始EQC爬虫逻辑
- Path: `src/work_data_hub/io/connectors/file_connector.py` — 连接器模式参考
- Path: `src/work_data_hub/domain/annuity_performance/service.py` — 错误处理参考

```python
# 参考现有连接器模式
class EQCClient:
    def __init__(self, token: str, timeout: int = 30):
        self.token = token
        self.timeout = timeout

    def search_company(self, name: str) -> List[CompanySearchResult]:
        """搜索公司，返回候选列表"""

    def get_company_detail(self, company_id: str) -> CompanyDetail:
        """获取公司详细信息"""
```

## DOCUMENTATION

- File: `legacy/annuity_hub/crawler/eqc_crawler.py` — 原始实现参考
- URL: EQC API文档（如有提供）
- File: `docs/security/SECRETS_POLICY.md` — 凭据管理标准
- File: `CLAUDE.md` — 错误处理和日志约定

## INTEGRATION POINTS

### Data models
```python
from pydantic import BaseModel, Field
from typing import List, Optional

class CompanySearchResult(BaseModel):
    """公司搜索结果"""
    company_id: str = Field(..., description="EQC公司ID")
    official_name: str = Field(..., description="官方名称")
    unite_code: Optional[str] = Field(None, description="统一社会信用代码")
    match_score: float = Field(0.0, description="匹配度分数0-1")

class CompanyDetail(BaseModel):
    """公司详细信息"""
    company_id: str
    official_name: str
    unite_code: Optional[str] = None
    aliases: List[str] = Field(default_factory=list, description="曾用名/别名")
    business_status: Optional[str] = None
```

### Config/ENV
```bash
# 必需配置（在.env文件中设置）
WDH_EQC_TOKEN=your_32_char_token  # EQC访问令牌（30分钟过期，需定期更新）

# 可选配置
WDH_EQC_ENABLED=1              # 启用EQC查询开关（默认启用）
WDH_EQC_TIMEOUT=30             # 请求超时秒数
WDH_EQC_RATE_LIMIT=10          # 每分钟最大请求数
WDH_EQC_RETRY_MAX=3            # 最大重试次数
```

**Token获取方式**：
参见 `docs/company_id/simplified/TOKEN_CONFIG_GUIDE.md`

### Error handling
```python
class EQCClientError(Exception):
    """EQC客户端异常基类"""

class EQCAuthenticationError(EQCClientError):
    """认证失败异常"""

class EQCRateLimitError(EQCClientError):
    """速率限制异常"""

class EQCNotFoundError(EQCClientError):
    """公司未找到异常"""
```

## DATA CONTRACTS

### API请求示例（基于legacy实现）
```python
# 搜索请求
search_url = "https://eqc.pingan.com/kg-api-hfd/api/search/searchAll"
search_params = {
    "keyword": "测试公司名称",
    "currentPage": 1,
    "pageSize": 10
}

# 详情请求
detail_url = f"https://eqc.pingan.com/kg-api-hfd/api/search/findDepart?targetId={company_id}"
```

### 响应数据示例
```json
{
  "code": 200,
  "data": [
    {
      "companyId": "614810477",
      "companyName": "测试企业有限公司",
      "uniteCode": "91110000123456789X",
      "aliases": ["测试企业", "测试公司"],
      "businessStatus": "存续"
    }
  ]
}
```

## GOTCHAS & LIBRARY QUIRKS

- EQC API可能返回429状态码，需要指数退避重试
- 公司名称需要URL编码处理中文字符
- Token可能有过期机制，需要处理401错误
- API响应中的`companyId`字段可能为数字或字符串，需要统一转换
- 网络超时设置要合理，避免阻塞主流程
- 空搜索结果和错误响应的区别处理

## IMPLEMENTATION NOTES

- 使用`requests`库，配置session复用连接
- 遵循项目日志约定，使用结构化日志
- 错误信息不能包含敏感的Token信息
- 实现简单的内存缓存，避免重复查询同一公司
- 保持函数简短，单一职责
- 使用dataclass或Pydantic进行数据验证

## VALIDATION GATES

```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k "test_eqc"

# 集成测试（需要真实token）
export WDH_EQC_TOKEN=your_token_here
uv run pytest -v tests/io/connectors/test_eqc_client.py::test_integration
```

## ACCEPTANCE CRITERIA

- [ ] EQCClient可以成功搜索公司并返回结构化结果
- [ ] 支持获取公司详细信息（ID、官方名、统一代码、别名）
- [ ] 错误处理覆盖：网络错误、认证失败、未找到、速率限制
- [ ] 具备基本的重试和超时保护
- [ ] 单元测试使用mock数据，不依赖真实API
- [ ] 集成测试可选择性运行（需要真实凭据）
- [ ] 日志记录请求/响应摘要，不泄露敏感信息
- [ ] 性能：单次查询响应时间<5秒

## ROLLOUT & RISK

### Feature flags
- `WDH_EQC_ENABLED=0` 默认关闭，避免意外调用
- 支持降级：EQC不可用时返回空结果，不阻塞主流程

### Risk mitigation
- 速率限制：客户端侧限制每分钟请求次数
- 超时保护：设置合理的连接和读取超时
- 重试策略：指数退避，避免雪崩效应
- 监控告警：记录成功率、响应时间等指标

### Security considerations
- Token通过环境变量管理，不硬编码
- 请求日志脱敏，不记录完整URL中的敏感参数
- 支持HTTPS，验证SSL证书

## APPENDICES

### 测试fixture示例
```python
@pytest.fixture
def mock_eqc_responses():
    return {
        "search_success": {
            "code": 200,
            "data": [
                {
                    "companyId": "614810477",
                    "companyName": "测试企业有限公司",
                    "uniteCode": "91110000123456789X"
                }
            ]
        },
        "search_empty": {"code": 200, "data": []},
        "auth_error": {"code": 401, "message": "Unauthorized"}
    }

@pytest.fixture
def eqc_client():
    return EQCClient(token="test_token", timeout=10)
```

### 集成测试示例
```python
@pytest.mark.integration
def test_eqc_real_search():
    """需要真实token的集成测试"""
    token = os.environ.get("WDH_EQC_TOKEN")
    if not token:
        pytest.skip("No EQC token provided")

    client = EQCClient(token)
    results = client.search_company("中国平安")
    assert len(results) > 0
    assert results[0].company_id
```

### 有用的搜索命令
```bash
rg "eqc.*crawler" legacy/annuity_hub/
rg "requests\." src/work_data_hub/
rg "timeout" src/work_data_hub/
```