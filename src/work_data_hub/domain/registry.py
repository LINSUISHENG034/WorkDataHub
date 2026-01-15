"""Domain Service Registry - 统一的 domain 服务注册表.

Story: Orchestration Layer Refactor - Phase 0
Location: domain/registry.py

提供 DOMAIN_SERVICE_REGISTRY，存储实现 DomainServiceProtocol 的服务实例。
"""

from typing import Dict

from work_data_hub.domain.protocols import DomainServiceProtocol

# Domain Service Registry
# 存储所有实现 DomainServiceProtocol 的服务实例
DOMAIN_SERVICE_REGISTRY: Dict[str, DomainServiceProtocol] = {}


def register_domain(name: str, service: DomainServiceProtocol) -> None:
    """注册 domain 服务."""
    DOMAIN_SERVICE_REGISTRY[name] = service


def unregister_domain(name: str) -> None:
    """注销 domain 服务."""
    DOMAIN_SERVICE_REGISTRY.pop(name, None)


# 注册所有 domain adapters
def _register_all_domains() -> None:
    """注册所有内置 domain 服务."""
    from work_data_hub.domain.annual_award.adapter import AnnualAwardService
    from work_data_hub.domain.annual_loss.adapter import AnnualLossService
    from work_data_hub.domain.annuity_income.adapter import AnnuityIncomeService
    from work_data_hub.domain.annuity_performance.adapter import (
        AnnuityPerformanceService,
    )
    from work_data_hub.domain.sandbox_trustee_performance.adapter import (
        SandboxTrusteePerformanceService,
    )

    register_domain("annuity_performance", AnnuityPerformanceService())
    register_domain("annuity_income", AnnuityIncomeService())
    register_domain("sandbox_trustee_performance", SandboxTrusteePerformanceService())
    register_domain("annual_award", AnnualAwardService())
    register_domain("annual_loss", AnnualLossService())


_register_all_domains()
