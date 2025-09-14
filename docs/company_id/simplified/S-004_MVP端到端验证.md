# S-004 — MVP端到端验证

集成S-001到S-003所有组件，在annuity_performance域中进行完整的端到端验证，确保新方案与legacy功能对等。

## FEATURE

在现有的annuity_performance处理流程中集成company_id enrichment服务，验证新方案的正确性、性能和稳定性。

## SCOPE

### In-scope
- 集成CompanyEnrichmentService到annuity_performance.service.py
- 在process_annuity_performance_op中集成enrichment步骤
- 提供enrichment统计报告和CSV导出
- 与legacy结果对比验证（至少95%一致性）
- 性能基准测试和瓶颈识别
- 完整的错误场景覆盖测试
- 异步队列处理CLI命令验证

### Non-goals
- 不修改其他域的处理逻辑
- 不进行历史数据批量回填
- 不实现Web界面或复杂报告
- 不涉及生产环境部署

## CONTEXT SNAPSHOT

```bash
src/work_data_hub/
  domain/
    annuity_performance/
      service.py                 # 集成enrichment调用
    company_enrichment/          # S-001到S-003的所有组件
      service.py
      models.py
      lookup_queue.py
  orchestration/
    ops.py                       # 更新process_annuity_performance_op
    jobs.py                      # 新增队列处理job
tests/
  e2e/
    test_company_enrichment_e2e.py  # 端到端测试
  fixtures/
    company_enrichment/             # 测试数据
```

## EXAMPLES

- Path: `src/work_data_hub/domain/annuity_performance/service.py` — 现有服务集成点
- Path: `src/work_data_hub/orchestration/ops.py` — process_annuity_performance_op修改
- Path: `tests/e2e/test_annuity_performance_e2e.py` — 端到端测试参考
- Path: `legacy/annuity_hub/data_handler/data_cleaner.py` — legacy对比基准

```python
# 在现有service中集成enrichment
def process_annuity_performance_rows(
    rows: List[Dict],
    enrichment_service: Optional[CompanyEnrichmentService] = None,
    sync_lookup_budget: int = 0
) -> ProcessingResult:
    """扩展现有处理逻辑，增加company_id enrichment"""

    enrichment_stats = EnrichmentStats()

    for row in rows:
        if enrichment_service:
            result = enrichment_service.resolve_company_id(
                plan_code=row.get("计划代码"),
                customer_name=row.get("客户名称"),
                account_name=row.get("年金账户名"),
                sync_lookup_budget=sync_lookup_budget
            )
            row["company_id"] = result.company_id
            enrichment_stats.record(result.status, result.source)

        # 继续现有处理逻辑...
```

## DOCUMENTATION

- File: `src/work_data_hub/domain/annuity_performance/service.py` — 集成点
- File: `docs/company_id/simplified/S-001_Legacy映射迁移.md` — 映射组件
- File: `docs/company_id/simplified/S-002_EQC客户端集成.md` — EQC组件
- File: `docs/company_id/simplified/S-003_基础缓存机制.md` — 核心服务
- File: `VALIDATION.md` — 现有验证流程参考

## INTEGRATION POINTS

### Data models
```python
class EnrichmentStats(BaseModel):
    """Enrichment过程统计"""
    total_records: int = 0
    success_internal: int = 0        # 内部映射命中
    success_external: int = 0        # EQC查询成功
    pending_lookup: int = 0          # 进入异步队列
    temp_assigned: int = 0           # 分配临时ID
    failed: int = 0                  # 失败
    sync_budget_used: int = 0        # 同步查询使用量
    processing_time_ms: int = 0      # 处理时间毫秒

class ProcessingResultWithEnrichment(ProcessingResult):
    """扩展现有ProcessingResult"""
    enrichment_stats: EnrichmentStats
    unknown_names_csv: Optional[str] = None  # 未解析名称CSV路径
```

### Config/ENV（集成现有配置）
```bash
# 在现有WDH_*配置基础上增加
WDH_COMPANY_ENRICHMENT_ENABLED=0     # 默认关闭，不影响现有流程
WDH_ENRICHMENT_SYNC_BUDGET=5         # 每次运行的同步查询预算
WDH_ENRICHMENT_EXPORT_UNKNOWNS=1     # 导出未解析样本CSV
```

### Jobs/Events（扩展现有CLI）
```bash
# 扩展现有命令，增加enrichment参数
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --execute \
  --enrichment-enabled \
  --enrichment-sync-budget 10

# 新增队列处理命令
uv run python -m src.work_data_hub.orchestration.jobs \
  --job process_company_lookup_queue \
  --execute
```

## DATA CONTRACTS

### Enrichment集成接口
```python
# 扩展现有AnnuityPerformanceConfig
class AnnuityPerformanceConfigWithEnrichment(AnnuityPerformanceConfig):
    enrichment_enabled: bool = False
    enrichment_sync_budget: int = 0
    export_unknown_names: bool = True

# ops层集成
@op(
    config_schema=AnnuityPerformanceConfigWithEnrichment,
    out={"processed_data": Out(), "enrichment_report": Out()}
)
def process_annuity_performance_op(context, config, excel_data):
    if config.enrichment_enabled:
        enrichment_service = get_enrichment_service()  # 依赖注入
    else:
        enrichment_service = None

    result = process_annuity_performance_rows(
        excel_data,
        enrichment_service=enrichment_service,
        sync_lookup_budget=config.enrichment_sync_budget
    )

    return result.processed_data, result.enrichment_stats
```

### 对比验证数据结构
```python
class ComparisonResult(BaseModel):
    """与legacy对比结果"""
    total_records: int
    matching_records: int           # company_id完全一致
    different_records: int          # company_id不同
    new_resolved_records: int       # 新方案解析出但legacy未解析
    consistency_rate: float         # 一致性比例
    differences: List[Dict]         # 具体差异记录（采样）

# 差异记录示例
{
    "plan_code": "AN001",
    "customer_name": "测试企业",
    "legacy_company_id": "614810477",
    "new_company_id": "608349737",
    "resolution_source": "external_eqc"
}
```

## GOTCHAS & LIBRARY QUIRKS

- enrichment过程不能影响现有字段处理逻辑的稳定性
- 同步查询budget耗尽后要优雅降级，不能中断处理
- CSV导出路径要与现有输出目录保持一致
- 对比验证要处理legacy中的None/空字符串差异
- 异步队列处理要支持中断和重启，保持幂等性
- 性能测试要在真实数据量下进行，不能只用小样本

## IMPLEMENTATION NOTES

- 保持现有service.py的函数签名兼容性
- enrichment逻辑作为可选参数，默认关闭
- 错误处理要区分enrichment错误和原有业务错误
- 日志格式要与现有保持一致，便于运维理解
- 使用现有的配置和数据库连接管理
- 遵循现有的测试文件组织结构

## VALIDATION GATES

```bash
# 标准验证
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v

# enrichment特定测试
uv run pytest -v -k "company_enrichment"
uv run pytest -v tests/e2e/test_company_enrichment_e2e.py

# 端到端验证（需要DB和测试数据）
export WDH_DATABASE__URI=postgresql://user:pass@host:5432/db
export WDH_DATA_BASE_DIR=tests/fixtures/sample_data/annuity_subsets
export WDH_COMPANY_ENRICHMENT_ENABLED=1
export WDH_ENRICHMENT_SYNC_BUDGET=5

# 不启用enrichment的baseline测试
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --execute --max-files 1 \
  --mode append --debug

# 启用enrichment的对比测试
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --execute --max-files 1 \
  --mode append --debug \
  --enrichment-enabled \
  --enrichment-sync-budget 5

# 队列处理验证
uv run python -m src.work_data_hub.orchestration.jobs \
  --job process_company_lookup_queue \
  --execute --debug
```

## ACCEPTANCE CRITERIA

### 功能验收
- [ ] enrichment功能可选启用，默认关闭不影响现有流程
- [ ] 内部映射命中率与legacy基本一致（>95%）
- [ ] EQC同步查询在budget内正常工作
- [ ] 异步队列正确处理未解析样本
- [ ] 统计报告包含各来源命中计数和处理时间
- [ ] 未解析样本正确导出CSV，格式清晰可读

### 性能验收
- [ ] enrichment开启后处理时间增长<50%
- [ ] 同步查询单次响应时间<5秒
- [ ] 批量处理性能>100条/分钟
- [ ] 内存使用无明显泄漏（长期运行稳定）

### 质量验收
- [ ] 与legacy对比一致性>95%（相同输入→相同company_id）
- [ ] 新增解析能力>legacy（原本未解析现在能解析的比例）
- [ ] 错误场景不影响主流程（降级到临时ID）
- [ ] 异常恢复能力（EQC不可用、DB连接中断等）

### 运维验收
- [ ] 完整的日志输出（来源分布、处理统计、错误详情）
- [ ] 支持plan-only模式预览enrichment效果
- [ ] CLI参数清晰，帮助信息完整
- [ ] 配置变更无需重启（通过环境变量控制）

## ROLLOUT & RISK

### Rollout计划
1. **Phase 1**: 在测试环境验证基础功能，关闭EQC查询
2. **Phase 2**: 小额度启用EQC同步查询（budget=5）
3. **Phase 3**: 验证异步队列处理，观察命中率提升
4. **Phase 4**: 根据效果决定是否推广到其他域

### Risk assessment
- **数据一致性风险**: 通过对比测试和渐进式启用降低
- **性能影响风险**: 通过budget控制和降级策略缓解
- **外部依赖风险**: EQC不可用时降级到现有逻辑
- **操作复杂性风险**: 保持CLI-first，避免增加运维负担

### Rollback策略
- 配置回滚：设置`WDH_COMPANY_ENRICHMENT_ENABLED=0`立即关闭
- 数据回滚：enrichment不修改原有字段，只新增company_id
- 功能回滚：新增字段可以通过视图隐藏，不影响下游

## APPENDICES

### 端到端测试示例
```python
@pytest.mark.e2e
def test_annuity_performance_with_enrichment_e2e():
    """完整的端到端测试，验证enrichment集成"""

    # 准备测试数据
    test_file = "tests/fixtures/sample_data/annuity_subsets/sample.xlsx"
    config = AnnuityPerformanceConfigWithEnrichment(
        enrichment_enabled=True,
        enrichment_sync_budget=3,
        export_unknown_names=True
    )

    # 执行处理
    result = execute_job_with_config("annuity_performance", config)

    # 验证结果
    assert result.enrichment_stats.total_records > 0
    assert result.enrichment_stats.success_internal > 0  # 至少有内部命中
    assert result.enrichment_stats.sync_budget_used <= 3  # 不超预算

    # 验证输出文件
    assert os.path.exists(result.unknown_names_csv)

    # 验证数据库记录
    with get_db_connection() as conn:
        records = conn.execute("SELECT * FROM annuity_performance ORDER BY 月度 DESC LIMIT 10").fetchall()
        assert all(record["company_id"] is not None for record in records)

def test_legacy_comparison():
    """与legacy结果对比测试"""

    # 运行legacy处理逻辑（模拟）
    legacy_results = run_legacy_processing("sample.xlsx")

    # 运行新逻辑
    new_results = run_new_processing_with_enrichment("sample.xlsx")

    # 对比分析
    comparison = compare_company_id_results(legacy_results, new_results)

    assert comparison.consistency_rate > 0.95  # 95%一致性
    assert comparison.new_resolved_records >= 0  # 新增解析能力

    # 输出详细差异报告
    print(f"一致性: {comparison.consistency_rate:.2%}")
    print(f"新增解析: {comparison.new_resolved_records}条")
    if comparison.different_records > 0:
        print("差异样本:")
        for diff in comparison.differences[:5]:  # 显示前5个差异
            print(f"  {diff}")
```

### 性能基准测试
```python
def test_performance_benchmark():
    """性能基准测试"""
    import time

    # 准备1000条测试记录
    test_data = generate_test_records(1000)

    # 测试不启用enrichment的基准时间
    start = time.time()
    result_baseline = process_annuity_performance_rows(test_data)
    baseline_time = time.time() - start

    # 测试启用enrichment的时间
    enrichment_service = get_test_enrichment_service()
    start = time.time()
    result_enriched = process_annuity_performance_rows(
        test_data,
        enrichment_service=enrichment_service,
        sync_lookup_budget=10
    )
    enriched_time = time.time() - start

    # 性能验证
    performance_overhead = (enriched_time - baseline_time) / baseline_time
    assert performance_overhead < 0.5  # 性能开销<50%

    print(f"Baseline: {baseline_time:.2f}s")
    print(f"With enrichment: {enriched_time:.2f}s")
    print(f"Overhead: {performance_overhead:.1%}")
```

### 有用的调试命令
```bash
# 查看enrichment相关代码
rg "enrichment" src/work_data_hub/
rg "company_id.*resolve" src/work_data_hub/

# 检查测试覆盖率
uv run pytest --cov=src/work_data_hub/domain/company_enrichment --cov-report=html

# 分析队列处理状态
psql -h host -d db -c "SELECT status, COUNT(*) FROM enterprise.lookup_requests GROUP BY status;"
```