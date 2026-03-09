"""Unit tests for intranet deployment bundle service helpers."""

from pathlib import Path

import pytest

from work_data_hub.gui.intranet_deploy.service import (
    DEFAULT_SKIP_FILES,
    IntranetDeployService,
    PACKAGE_COMPONENTS,
    merge_bundle_into_target,
)


@pytest.mark.unit
def test_merge_bundle_overwrites_regular_files(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()

    (source_dir / "src").mkdir()
    (target_dir / "src").mkdir()
    (source_dir / "src" / "main.py").write_text("new", encoding="utf-8")
    (target_dir / "src" / "main.py").write_text("old", encoding="utf-8")

    result = merge_bundle_into_target(source_dir, target_dir)

    assert (target_dir / "src" / "main.py").read_text(encoding="utf-8") == "new"
    assert result.copied_files == 0
    assert result.overwritten_files == 1


@pytest.mark.unit
def test_merge_bundle_skips_existing_default_config_files(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    (source_dir / "config").mkdir(parents=True)
    (target_dir / "config").mkdir(parents=True)

    (source_dir / "config" / "data_sources.yml").write_text("remote", encoding="utf-8")
    (target_dir / "config" / "data_sources.yml").write_text("local", encoding="utf-8")

    result = merge_bundle_into_target(source_dir, target_dir)

    assert (target_dir / "config" / "data_sources.yml").read_text(
        encoding="utf-8"
    ) == "local"
    assert result.skipped_files == ("config/data_sources.yml",)


@pytest.mark.unit
def test_merge_bundle_copies_skip_file_when_destination_missing(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()

    (source_dir / ".wdh_env").write_text("PYTHONPATH=src", encoding="utf-8")

    result = merge_bundle_into_target(source_dir, target_dir)

    assert (target_dir / ".wdh_env").read_text(encoding="utf-8") == "PYTHONPATH=src"
    assert result.copied_files == 1
    assert result.skipped_files == ()


@pytest.mark.unit
def test_build_archive_name_contains_repo_and_commit() -> None:
    service = IntranetDeployService.__new__(IntranetDeployService)
    service.repo_name = "WorkDataHub"

    archive_name = IntranetDeployService._build_archive_name(
        service,
        "vendor",
        "1234567890abcdef",
    )

    assert archive_name.startswith("WorkDataHub-intranet-vendor-")
    assert archive_name.endswith("-12345678.7z")
    assert DEFAULT_SKIP_FILES == (".wdh_env", "config/data_sources.yml")


@pytest.mark.unit
def test_discover_component_archives_returns_available_components(tmp_path: Path) -> None:
    service = IntranetDeployService.__new__(IntranetDeployService)
    service.repo_name = "WorkDataHub"

    for component in PACKAGE_COMPONENTS[:2]:
        archive_path = (
            tmp_path
            / f"WorkDataHub-intranet-{component.name}-20260309-120000-12345678.7z"
        )
        archive_path.write_text("", encoding="utf-8")

    result = IntranetDeployService._discover_component_archives(service, tmp_path)

    assert [component.name for component, _ in result] == ["repo-root", "vendor"]


@pytest.mark.unit
def test_resolve_components_requires_non_empty_selection() -> None:
    service = IntranetDeployService.__new__(IntranetDeployService)

    with pytest.raises(RuntimeError, match="至少选择一个"):
        IntranetDeployService._resolve_components(service, [])
