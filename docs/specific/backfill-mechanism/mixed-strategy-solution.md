  ? 专业意见：混合策略是最佳选择

  核心观点

  单一方案都有明显短板，混合策略可以取长补短：

  | 场景         | 选项 B 单独       | 选项 D 单独  | 混合策略    |
  |--------------|-------------------|--------------|-------------|
  | 已知引用数据 | ?? 只创建最小记录 | ? 完整数据  | ? 完整数据 |
  | 新增FK 值    | ? 自动创建       | ? 失败/阻塞 | ? 自动创建 |
  | 数据质量追踪 | ? 无法区分来源   | ? 清晰      | ? 清晰     |
  | 运维复杂度   | 低                | 中           | 中          |

  ---
  ? 混合策略设计建议

  分层数据质量模型

  ┌─────────────────────────────────────────────────────────────────┐
  │  Layer 1: Authoritative Data (权威数据)                         │
  │  来源: Legacy MySQL, MDM, 配置文件                │
  │  特点: 完整字段、已验证、有审计追踪│
  │  标记: source ='authoritative'                                 │
  └─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  Layer 2: Auto-Derived Data (自动派生数据)                      │
  │  来源: 事实数据中的新 FK 值                                     │
  │  特点: 最小字段、待补充、需审核                                  │
  │  标记: source = 'auto_derived', needs_review = true│
  └─────────────────────────────────────────────────────────────────┘

  执行流程

  ┌─────────────────────────────────────────────────────────────────┐
  │  Phase 1: Pre-Load (每日凌晨 1:00)                              │
  │  ├── 从Legacy MySQL 同步 年金计划、组合计划、组织架构           │
  │  ├── 从配置文件加载 产品线                │
  │  └── 验证引用表完整性                                           │
  └─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  Phase 2: Fact Processing (每日凌晨 3:00)                       │
  │  ├── 读取并处理事实数据                                         │
  │  ├── 验证 FK 预条件                                             │
  │  │   ├── 已存在 → 继续                                          │
  │  │   └── 不存在 → 进入 Phase 3                                  │
  │  └── 加载事实数据                                               │
  └─────────────────────────────────────────────────────────────────┘
                                │
                                ▼ (仅当有未知 FK 值时)
  ┌─────────────────────────────────────────────────────────────────┐
  │  Phase 3: Auto-Derive (按需触发)                                │
  │  ├── 从事实数据派生最小引用记录                                  │
  │  ├── 标记为 source='auto_derived', needs_review=true            │
  │  ├── 插入引用表                                                 │
  │  └── 生成审核报告                                               │
  └─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  Phase 4: Data Governance (人工/定期)                           │
  │  ├── 审核 auto_derived 记录                                     │
  │  ├── 补充缺失字段                                               │
  │  ├── 更新 source='authoritative' 或删除错误记录                 │
  │  └── 反馈到源系统（如需要）                                     │
  └─────────────────────────────────────────────────────────────────┘

  ---
  ? 技术实现要点

  1. 引用表Schema 扩展

  -- 为所有引用表添加数据来源追踪字段
  ALTER TABLE "business"."年金计划" ADD COLUMN IF NOT EXISTS
      _source VARCHAR(20) DEFAULT 'authoritative';

  ALTER TABLE "business"."年金计划" ADD COLUMN IF NOT EXISTS
      _needs_review BOOLEAN DEFAULT FALSE;

  ALTER TABLE "business"."年金计划" ADD COLUMN IF NOT EXISTS
      _derived_from_domain VARCHAR(50);

  ALTER TABLE "business"."年金计划" ADD COLUMN IF NOT EXISTS
      _derived_at TIMESTAMP;

  2. 配置层设计

  # config/reference_management.yml

  strategy: "hybrid"  # hybrid | preload_only | backfill_only

  preload:enabled: true
    schedule: "0 1 * * *"
    sources:
      年金计划:
        type: "legacy_mysql"
        database: "annuity_hub"
        table: "年金计划"组合计划:
        type: "legacy_mysql"
        database: "annuity_hub"
        table: "组合计划"
      产品线:
        type: "config_file"
        path: "config/reference_data/product_lines.yml"
      组织架构:
        type: "legacy_mysql"
        database: "enterprise"
        table: "组织架构"

  backfill:
    enabled: true
    mode: "fallback"  # fallback (仅当预加载未覆盖时) | always
    mark_for_review: true
    notify_on_new_records: true
    notification_channel: "data-quality-alerts"

  3. 混合服务实现

  class HybridReferenceService:
      """
      混合引用数据管理服务

      结合预加载和按需 Backfill 的优势
      """

      def __init__(self, config: HybridConfig):
          self.preload_service = ReferenceSyncService()
          self.backfill_service = GenericBackfillService()
          self.config = config
      def ensure_references(
          self,
          df: pd.DataFrame,
          domain: str,
          fk_configs: list[ForeignKeyConfig],
          conn: Connection
      ) -> EnsureReferencesResult:
          """
          确保所有 FK 引用存在

          1. 检查预加载数据是否覆盖
          2. 对于未覆盖的值，使用 Backfill 创建
          3. 标记 Backfill 创建的记录
          """
          results = []

          for config in fk_configs:
              # 获取事实数据中的 FK 值
              fk_values = df[config.source_column].dropna().unique()

              # 检查哪些已存在（预加载覆盖）
              existing = self._get_existing_keys(
                  conn, config.target_table, config.target_key
              )

              # 识别未覆盖的值
              missing = set(fk_values) - set(existing)

              if missing:
                  # 使用 Backfill 创建，并标记来源
                  backfill_result = self._backfill_with_tracking(
                      df=df,
                      config=config,
                      missing_keys=missing,
                      domain=domain,
                      conn=conn
                  )
                  results.append(backfill_result)
                  # 发送通知（如配置）
                  if self.config.notify_on_new_records:
                      self._send_notification(config, missing, domain)

          return EnsureReferencesResult(results)

      def _backfill_with_tracking(
          self,
          df: pd.DataFrame,
          config: ForeignKeyConfig,
          missing_keys: set,
          domain: str,
          conn: Connection
      ) -> BackfillTableResult:
          """
          Backfill 并添加追踪字段
          """
          # 派生候选记录
          candidates = self.backfill_service.derive_candidates(df, config)

          # 只保留缺失的键
          candidates = candidates[
              candidates[config.target_key].isin(missing_keys)
          ]

          # 添加追踪字段
          candidates['_source'] = 'auto_derived'
          candidates['_needs_review'] = True
          candidates['_derived_from_domain'] = domain
          candidates['_derived_at'] = datetime.now()

          # 插入
          return self.backfill_service._backfill_table(
              candidates, config, conn
          )

  ---
  ? 混合策略的优势总结

  1. 数据质量分层管理

  | 数据层 | 来源     | 质量               | 处理方式        |
  |--------|----------|--------------------|-----------------|
  | 权威层 | 预加载   | 高（完整、已验证） | 直接使用        |
  | 派生层 | Backfill | 中（最小记录）     | 使用 + 标记审核 |

  2. 故障容错

  场景: 预加载作业失败
      ↓
  传统预加载方案: 事实处理全部失败 ?
  混合方案: Backfill 兜底，事实处理继续 ? (但会标记更多待审核记录)

  3. 渐进式数据治理

  Day 1: 大量 auto_derived 记录
      ↓
  Day 30: 数据团队补充完善
      ↓
  Day 60: 大部分记录已是 authoritative
      ↓
  持续: 只有真正的新值才会触发 auto_derive

  4. 可观测性

  # 数据质量仪表板查询
  SELECT
      _source,
      COUNT(*) as record_count,
      SUM(CASE WHEN _needs_review THEN 1 ELSE 0 END) as pending_review
  FROM "business"."年金计划"
  GROUP BY _source;

  # 结果示例:
  # _source        | record_count | pending_review
  # authoritative  | 1,234| 0
  # auto_derived   | 56| 23

  ---
  ?? 需要注意的风险

  1. 数据一致性窗口

  问题：预加载和事实处理之间可能有时间差

  缓解：
  - 预加载完成后立即触发事实处理（Sensor 机制）
  - 或在事实处理开始时做增量同步检查

  2. Auto-Derived 数据堆积

  问题：如果审核不及时，auto_derived 记录可能越来越多

  缓解：
  - 设置告警阈值（如 auto_derived 占比 > 10%）
  - 定期生成审核报告
  - 将审核任务纳入数据治理流程

  3. 循环依赖

  问题：如果引用表之间有FK 关系（如 组合计划 → 年金计划）

  缓解：
  - 预加载时按依赖顺序同步
  - Backfill 时也按依赖顺序处理
  - 配置中明确声明 depends_on

  ---
  ? 最终建议

  我强烈推荐采用混合策略，理由如下：

  1. 业务现实：在复杂业务中，新 FK 值是常态，纯预加载无法应对
  2. 数据质量：纯 Backfill 会导致引用数据质量下降，混合策略保留了预加载的质量优势
  3. 运维友好：即使预加载失败，系统仍能继续运行（降级模式）
  4. 可演进：随着数据治理成熟，auto_derived 比例会自然下降

  实施优先级建议：

  Phase 1: 实现通用 Backfill 框架（选项 B）
      ↓ 快速解决当前问题
  Phase 2: 添加数据来源追踪字段
      ↓ 为混合策略做准备
  Phase 3: 实现预加载服务（选项 D）
      ↓ 提升数据质量
  Phase 4: 整合为混合策略
      ↓ 最终形态

  ---