from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ACTIVE_DOMAINS = {
    "annuity_performance",
    "annuity_income",
    "annual_award",
    "annual_loss",
    "sandbox_trustee_performance",
}
SOURCE_PATTERNS = [
    "README.md",
    "docs/index.md",
    "docs/deployment_run_guide.md",
    "docs/deployment_run_guide_intranet.md",
    "docs/engineering/documentation-standards.md",
    "docs/guides/index.md",
    "docs/domains/**/*.md",
    "docs/runbooks/**/*.md",
    "docs/cleansing-rules/**/*.md",
    "docs/reference/**/*.md",
    "docs/business-background/**/*.md",
    "docs/guides/validation/**/*.md",
    "src/**/*.py",
    "tests/**/*.py",
    "tests/**/*.md",
    "scripts/**/*.py",
    "scripts/**/*.md",
    ".github/workflows/**/*.yml",
]
IGNORED_TARGET_PREFIXES = (
    "docs/PRD.md",
    "docs/architecture-boundaries.md",
    "docs/architecture/",
    "docs/bmm-index",
    "docs/brownfield-architecture",
    "docs/epic-",
    "docs/epics",
    "docs/implementation-readiness",
    "docs/pipeline-",
    "docs/prd/",
    "docs/research-deep-prompt",
    "docs/sprint-artifacts/",
    "docs/validation-report",
)
DOC_REF_RE = re.compile(r"docs/[^\s`)\]\"']+\.(?:md|yaml|yml|csv)")


def _iter_source_files() -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []
    for pattern in SOURCE_PATTERNS:
        for path in ROOT.glob(pattern):
            if path.is_file() and path not in seen:
                seen.add(path)
                files.append(path)
    return sorted(files)


def _load_active_domains() -> set[str]:
    config_data = yaml.safe_load(
        (ROOT / "config/data_sources.yml").read_text(encoding="utf-8")
    )
    config_domains = set(config_data["domains"])
    registry_text = (ROOT / "src/work_data_hub/domain/registry.py").read_text(
        encoding="utf-8"
    )
    registry_domains = set(re.findall(r'register_domain\("([^"]+)"', registry_text))
    return config_domains & registry_domains


def _should_ignore_target(ref: str) -> bool:
    if "*" in ref or "{" in ref:
        return True
    return ref.startswith(IGNORED_TARGET_PREFIXES)


def _collect_missing_refs() -> list[str]:
    missing: list[str] = []
    for source in _iter_source_files():
        text = source.read_text(encoding="utf-8", errors="ignore")
        for ref in sorted(set(DOC_REF_RE.findall(text))):
            if _should_ignore_target(ref):
                continue
            if not (ROOT / ref).exists():
                missing.append(f"{source.as_posix()}: {ref}")
    return missing


def main() -> int:
    errors: list[str] = []

    active_domains = _load_active_domains()
    if active_domains != EXPECTED_ACTIVE_DOMAINS:
        errors.append(
            "active domains drifted: "
            "config+registry="
            f"{sorted(active_domains)} expected={sorted(EXPECTED_ACTIVE_DOMAINS)}"
        )

    for domain in sorted(active_domains):
        for relative_path in (
            f"docs/domains/{domain}.md",
            f"docs/runbooks/{domain}.md",
        ):
            if not (ROOT / relative_path).exists():
                errors.append(f"missing required doc: {relative_path}")

    errors.extend(_collect_missing_refs())

    if errors:
        print("docs alignment check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("docs alignment check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
