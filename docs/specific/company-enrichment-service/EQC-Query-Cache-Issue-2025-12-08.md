# EQC 查询结果缓存问题

**日期**: 2025-12-08
**问题类型**: 数据持久化问题
**影响范围**: EQC API 查询结果的自动缓存机制
**严重程度**: 中等（影响查询效率，但不影响查询功能本身）

---

## 问题描述

EQC API 查询功能正常工作，能够成功查询到企业的 Company ID，但查询结果没有自动写入 `enrichment_index` 表，导致无法实现查询结果的持久化和复用。

## 验证过程

### 1. EQC 查询功能验证
使用项目自带的 `EqcProvider` 组件直接查询 EQC API：

```python
provider = EqcProvider(token=eqc_token, budget=10)
result = provider.lookup("华为技术有限公司")
```

**查询结果**：
- ✅ 华为技术有限公司 -> 601562992
- ✅ 小米科技有限责任公司 -> 602800435
- ✅ OPPO广东移动通信有限公司 -> 603150146
- ✅ vivo移动通信有限公司 -> 603624173
- ✅ 海尔集团公司 -> 602080065
- ✅ 美的集团股份有限公司 -> 602201135

所有查询都返回了正确的 9 位数字 Company ID 和完整的企业信息。

### 2. 数据持久化验证
检查 `enrichment_index` 表中的新增记录：

```sql
SELECT COUNT(*)
FROM enterprise.enrichment_index
WHERE source = 'eqc_api'
AND created_at >= NOW() - INTERVAL '5 minute';
```

**结果**: 0 条新记录

## 问题分析

### 根本原因

1. **EqcProvider 初始化问题**
   - `CompanyIdResolver` 创建 `EqcProvider` 时没有传入 `mapping_repository` 参数
   - 导致即使查询成功，也无法触发缓存写入

   ```python
   # src/work_data_hub/infrastructure/enrichment/company_id_resolver.py:112
   self.eqc_provider = eqc_provider  # mapping_repository 未传入
   ```

2. **缓存写入目标错误**
   - `EqcProvider._cache_result()` 方法试图写入 `company_name_index` 表
   - 但该表在 Epic 6.1 中不存在
   - Epic 6.1 使用的是 `enrichment_index` 表

   ```python
   # src/work_data_hub/infrastructure/enrichment/eqc_provider.py:355
   # Write to enterprise.company_name_index with match_type=eqc
   self.mapping_repository.insert_company_name_index_batch([...])
   ```

3. **数据库表结构**
   当前 `enterprise` schema 中的表：
   - `company_mapping` ✓
   - `company_master` ✓
   - `enrichment_index` ✓
   - `enrichment_requests` ✓
   - `company_name_index` ❌（不存在）

### 影响范围

1. **功能影响**
   - EQC 查询结果无法持久化
   - 相同企业的重复查询会再次调用 EQC API
   - 无法利用缓存提升查询效率

2. **性能影响**
   - 增加 EQC API 调用次数
   - 降低整体查询性能
   - 增加 API 配额消耗

3. **数据影响**
   - 查询历史丢失
   - 无法分析 EQC 查询模式

## 解决方案

### 方案 1：修改 EqcProvider 缓存机制（推荐）

1. **更新 `_cache_result` 方法**
   ```python
   def _cache_result(self, company_name: str, result: CompanyInfo) -> None:
       try:
           from work_data_hub.infrastructure.enrichment.normalizer import normalize_for_temp_id

           normalized = normalize_for_temp_id(company_name) or company_name.strip()

           # 写入 enrichment_index 表而不是 company_name_index
           record = EnrichmentIndexRecord(
               lookup_key=normalized,
               lookup_type=LookupType.CUSTOMER_NAME,
               company_id=result.company_id,
               confidence=result.confidence,
               source=SourceType.EQC_API,
               source_domain="eqc_sync_lookup"
           )

           self.mapping_repository.insert_enrichment_index_batch([record])

       except Exception:
           logger.warning("eqc_provider.cache_failed")
   ```

2. **修改 CompanyIdResolver 初始化**
   ```python
   # 在创建 EqcProvider 时传入 mapping_repository
   self.eqc_provider = EqcProvider(
       token=settings.eqc_token,
       budget=settings.company_sync_lookup_limit,
       mapping_repository=self.mapping_repository  # 关键：传入 repository
   )
   ```

### 方案 2：创建 company_name_index 表（备选）

```sql
CREATE TABLE enterprise.company_name_index (
    id SERIAL PRIMARY KEY,
    normalized_name VARCHAR(255) NOT NULL,
    company_id VARCHAR(100) NOT NULL,
    match_type VARCHAR(50),
    confidence FLOAT,
    priority INTEGER,
    source VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_company_name_index_unique
ON enterprise.company_name_index (normalized_name, match_type);
```

### 方案 3：优化 CompanyIdResolver 缓存逻辑（临时方案）

在 `_resolve_via_eqc_provider` 方法中手动处理缓存：

```python
if result:
    resolved.loc[idx] = result.company_id
    eqc_hits += 1

    # 手动缓存到 enrichment_index
    try:
        normalized = normalize_for_temp_id(str(customer_name))
        record = EnrichmentIndexRecord(
            lookup_key=normalized,
            lookup_type=LookupType.CUSTOMER_NAME,
            company_id=result.company_id,
            confidence=result.confidence,
            source=SourceType.EQC_API,
            source_domain="eqc_sync_lookup"
        )
        self.mapping_repository.insert_enrichment_index_batch([record])
    except Exception:
        logger.warning("Failed to cache EQC result")
```

## 建议的实施步骤

1. **第一步**：采用方案 1，修改 `EqcProvider._cache_result()` 方法
2. **第二步**：更新 `CompanyIdResolver` 初始化逻辑
3. **第三步**：编写单元测试验证缓存功能
4. **第四步**：集成测试验证完整流程

## 验证用例

### 1. 验证 EQC 查询缓存写入

```python
def test_eqc_cache_write():
    # 1. 清除现有缓存
    # 2. 执行 EQC 查询
    # 3. 验证 enrichment_index 中有新记录
    # 4. 重复查询相同企业，验证命中缓存
    pass
```

### 2. 验证查询性能提升

```python
def test_eqc_performance():
    # 1. 记录查询次数
    # 2. 多次查询相同企业
    # 3. 验证 API 调用次数减少
    pass
```

## 相关文件

1. **源代码文件**：
   - `src/work_data_hub/infrastructure/enrichment/eqc_provider.py`
   - `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py`

2. **测试文件**：
   - `tests/unit/infrastructure/enrichment/test_eqc_provider.py`
   - `tests/unit/infrastructure/enrichment/test_company_id_resolver_eqc_integration.py`

3. **配置文件**：
   - `config/data_sources.yml`

## 备注

- 此问题不影响 EQC 查询功能本身
- 仅影响查询结果的持久化和复用
- 优先采用方案 1，保持与 Epic 6.1 架构一致
- 建议在实施时做好充分的测试验证

---

**报告人**: Dev Agent
**审核人**: 待定
**创建日期**: 2025-12-08