"""
Controller for the intranet deployment packaging GUI.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from work_data_hub.gui.intranet_deploy.service import (
    DEFAULT_SKIP_FILES,
    PACKAGE_COMPONENTS,
    AssembleResult,
    IntranetDeployService,
    PackageResult,
)


class IntranetDeployController:
    """Thin GUI-facing wrapper around :class:`IntranetDeployService`."""

    def __init__(self) -> None:
        self._service = IntranetDeployService()

    @property
    def project_root(self) -> Path:
        """Return the resolved project root."""

        return self._service.project_root

    @property
    def default_skip_files(self) -> tuple[str, ...]:
        """Return the default skip file list shown in the GUI."""

        return DEFAULT_SKIP_FILES

    @property
    def seven_zip_executable(self) -> str:
        """Return the resolved 7-Zip executable path."""

        return self._service.seven_zip_executable

    @property
    def package_components(self) -> tuple[str, ...]:
        """Return the available packaging component names."""

        return tuple(component.name for component in PACKAGE_COMPONENTS)

    def create_package(
        self,
        output_dir: Path,
        component_names: Sequence[str] | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> PackageResult:
        """Create a new deployment bundle."""

        return self._service.create_package(
            output_dir=output_dir,
            component_names=component_names,
            progress=progress,
        )

    def assemble_package(
        self,
        package_dir: Path,
        target_base_dir: Path,
        skip_files: Sequence[str],
        progress: Callable[[str], None] | None = None,
    ) -> AssembleResult:
        """Assemble deployment bundles from a directory into a target directory."""

        return self._service.assemble_packages(
            package_dir=package_dir,
            target_base_dir=target_base_dir,
            skip_files=skip_files,
            progress=progress,
        )
