"""Integration tests for active domain documentation coverage."""

from pathlib import Path

import pytest
import yaml


ACTIVE_DOMAINS = {
    "annuity_performance",
    "annuity_income",
    "annual_award",
    "annual_loss",
    "sandbox_trustee_performance",
}

DOMAIN_REQUIRED_SECTIONS = [
    "overview",
    "inputs",
    "file discovery and sheet selection",
    "transformation and validation",
    "output tables",
    "cli and operational entry points",
    "configuration",
    "verification",
    "related runbooks and rules",
]

RUNBOOK_REQUIRED_SECTIONS = [
    "preconditions",
    "manual execution",
    "common errors",
    "verification",
    "rollback or safe re-run",
]


def _active_domains_from_config() -> set[str]:
    with open("config/data_sources.yml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return set(config["domains"]).intersection(ACTIVE_DOMAINS)


class TestActiveDomainDocsComplete:
    """Verify docs coverage for active ETL domains."""

    @pytest.fixture(scope="class")
    def active_domains(self) -> set[str]:
        return _active_domains_from_config()

    def test_domain_doc_exists_for_every_active_domain(
        self, active_domains: set[str]
    ) -> None:
        for domain in active_domains:
            doc_path = Path(f"docs/domains/{domain}.md")
            assert doc_path.exists(), f"Missing domain doc: {doc_path}"

    def test_runbook_exists_for_every_active_domain(
        self, active_domains: set[str]
    ) -> None:
        for domain in active_domains:
            runbook_path = Path(f"docs/runbooks/{domain}.md")
            assert runbook_path.exists(), f"Missing runbook: {runbook_path}"

    def test_every_active_domain_doc_has_required_sections(
        self, active_domains: set[str]
    ) -> None:
        for domain in active_domains:
            content = Path(f"docs/domains/{domain}.md").read_text(encoding="utf-8").lower()
            for section in DOMAIN_REQUIRED_SECTIONS:
                assert section in content, (
                    f"{domain} domain doc missing required section: {section}"
                )

    def test_every_active_runbook_has_required_sections(
        self, active_domains: set[str]
    ) -> None:
        for domain in active_domains:
            content = Path(f"docs/runbooks/{domain}.md").read_text(encoding="utf-8").lower()
            for section in RUNBOOK_REQUIRED_SECTIONS:
                assert section in content, (
                    f"{domain} runbook missing required section: {section}"
                )
