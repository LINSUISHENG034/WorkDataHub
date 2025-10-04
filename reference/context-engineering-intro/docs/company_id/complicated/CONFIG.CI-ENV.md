# Company ID 相关环境变量与默认值

- `WDH_ALIAS_SALT`：生成临时别名ID（IN_ 前缀）所用盐；建议必配，确保可重复且不可逆。
- `WDH_ENRICH_COMPANY_ID`：是否启用 company_id 富化（0/1），默认 0（关闭）。
- `WDH_ENRICH_SYNC_BUDGET`：同步在线查询额度（每次运行允许的最大条数），默认 0（禁用）。
- `WDH_ENTERPRISE_PROVIDER`：外部企业信息 Provider 选择（`stub`/`eqc`/...），默认 `stub`。
- `WDH_PROVIDER_EQC_TOKEN`：EQC 访问 Token（仅当 `WDH_ENTERPRISE_PROVIDER=eqc` 时需要）。

建议：
- 生产环境通过 .env/密钥管理系统配置；日志与错误信息不得泄露 Token。
- 无网络或无凭据时使用 `stub` Provider + 固定 fixtures 完成本地与 CI 验证。
