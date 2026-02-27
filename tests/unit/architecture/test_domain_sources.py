"""Domain Source Configuration Tests.

TDD Phase: RED
验证配置驱动的数据源加载机制。
"""

import pytest


class TestDomainSourceConfigExists:
    """验证配置模块存在."""

    def test_config_module_exists(self):
        """domain_sources 模块应该存在."""
        from work_data_hub.config.domain_sources import DOMAIN_SOURCE_REGISTRY

        assert DOMAIN_SOURCE_REGISTRY is not None

    def test_config_is_dict(self):
        """DOMAIN_SOURCE_REGISTRY 应该是字典."""
        from work_data_hub.config.domain_sources import DOMAIN_SOURCE_REGISTRY

        assert isinstance(DOMAIN_SOURCE_REGISTRY, dict)


class TestDomainSourceConfig:
    """验证各 domain 的配置."""

    EXPECTED_DOMAINS = [
        "annuity_performance",
        "annuity_income",
        "sandbox_trustee_performance",
        "annual_award",
    ]

    def test_all_domains_have_config(self):
        """所有 domain 应该有配置."""
        from work_data_hub.config.domain_sources import DOMAIN_SOURCE_REGISTRY

        for domain in self.EXPECTED_DOMAINS:
            assert domain in DOMAIN_SOURCE_REGISTRY, f"Missing: {domain}"

    @pytest.mark.parametrize("domain_name", EXPECTED_DOMAINS)
    def test_config_has_source_type(self, domain_name: str):
        """每个配置应该有 source_type."""
        from work_data_hub.config.domain_sources import DOMAIN_SOURCE_REGISTRY

        config = DOMAIN_SOURCE_REGISTRY[domain_name]
        assert hasattr(config, "source_type")
        assert config.source_type in ["single_file", "multi_table"]
