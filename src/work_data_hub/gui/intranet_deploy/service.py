"""
Backend services for intranet deployment packaging and assembly.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence
from zipfile import ZipFile

from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_SKIP_FILES = (".wdh_env", "config/data_sources.yml")
MANIFEST_NAME = ".wdh_intranet_bundle.json"
SEVEN_ZIP_CANDIDATES = (
    "7z",
    "7za",
    r"C:\Program Files\7-Zip\7z.exe",
    r"C:\Program Files\7-Zip\7za.exe",
    r"C:\Program Files (x86)\7-Zip\7z.exe",
    r"C:\Program Files (x86)\7-Zip\7za.exe",
)

ProgressCallback = Callable[[str], None]


class DeploymentBundleError(RuntimeError):
    """Raised when the deployment bundle workflow fails."""


@dataclass(frozen=True)
class PackageManifest:
    """Metadata embedded in each deployment bundle."""

    repo_name: str
    component_name: str
    git_ref: str
    git_commit: str
    generated_at: str
    default_skip_files: tuple[str, ...]


@dataclass(frozen=True)
class PackageComponent:
    """Definition of one independently transferable bundle component."""

    name: str
    source_relative_path: str | None
    excluded_paths: tuple[str, ...] = ()


PACKAGE_COMPONENTS = (
    PackageComponent(
        name="repo-root",
        source_relative_path=None,
        excluded_paths=("vendor", "config/seeds", "data/backups"),
    ),
    PackageComponent(name="vendor", source_relative_path="vendor"),
    PackageComponent(name="config-seeds", source_relative_path="config/seeds"),
    PackageComponent(name="data-backups", source_relative_path="data/backups"),
)
PACKAGE_COMPONENTS_BY_NAME = {
    component.name: component for component in PACKAGE_COMPONENTS
}


@dataclass(frozen=True)
class PackageArchive:
    """One generated archive file."""

    component_name: str
    archive_path: Path


@dataclass(frozen=True)
class PackageResult:
    """Summary returned after bundle creation."""

    git_ref: str
    git_commit: str
    archives: tuple[PackageArchive, ...]


@dataclass(frozen=True)
class AssembleResult:
    """Summary returned after bundle assembly."""

    project_dir: Path
    copied_files: int
    overwritten_files: int
    skipped_files: tuple[str, ...]
    processed_components: tuple[str, ...]


def discover_project_root(start_path: Path | None = None) -> Path:
    """Discover the repository root by walking upwards for ``pyproject.toml``."""

    current = (start_path or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists():
            return candidate

    raise DeploymentBundleError("无法定位项目根目录: 未找到 pyproject.toml")


def discover_7zip_executable() -> str:
    """Locate a 7-Zip executable on PATH or in standard install locations."""

    for candidate in SEVEN_ZIP_CANDIDATES:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
        path_candidate = Path(candidate)
        if path_candidate.exists():
            return str(path_candidate)

    raise DeploymentBundleError(
        "未找到 7-Zip 可执行文件。请先安装 7-Zip，并确保 `7z` 可在 PATH 中使用。"
    )


def merge_bundle_into_target(
    source_dir: Path,
    target_dir: Path,
    skip_files: Sequence[str] = DEFAULT_SKIP_FILES,
) -> AssembleResult:
    """
    Merge an extracted bundle into the target project directory.

    Existing files are overwritten except for skip-listed files that already
    exist in the destination.
    """

    normalized_skip = {Path(item).as_posix() for item in skip_files}
    skipped_files: list[str] = []
    copied_files = 0
    overwritten_files = 0

    for source_path in sorted(source_dir.rglob("*")):
        if source_path.is_dir():
            continue

        relative_path = source_path.relative_to(source_dir)
        relative_posix = relative_path.as_posix()
        if relative_posix == MANIFEST_NAME:
            continue
        destination_path = target_dir / relative_path

        if relative_posix in normalized_skip and destination_path.exists():
            skipped_files.append(relative_posix)
            continue

        destination_path.parent.mkdir(parents=True, exist_ok=True)

        if destination_path.exists():
            if destination_path.is_dir():
                shutil.rmtree(destination_path)
            else:
                destination_path.unlink()
            overwritten_files += 1
        else:
            copied_files += 1

        shutil.copy2(source_path, destination_path)

    return AssembleResult(
        project_dir=target_dir,
        copied_files=copied_files,
        overwritten_files=overwritten_files,
        skipped_files=tuple(skipped_files),
        processed_components=(),
    )


class IntranetDeployService:
    """Service object for bundle packaging and assembly workflows."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = discover_project_root(project_root)
        self.repo_name = self.project_root.name
        self._seven_zip = discover_7zip_executable()

    @property
    def seven_zip_executable(self) -> str:
        """Return the resolved 7-Zip executable path."""

        return self._seven_zip

    def create_package(
        self,
        output_dir: Path,
        component_names: Sequence[str] | None = None,
        progress: ProgressCallback | None = None,
    ) -> PackageResult:
        """Build multiple ``.7z`` deployment bundles from the upstream revision."""

        output_dir.mkdir(parents=True, exist_ok=True)
        selected_components = self._resolve_components(component_names)
        upstream_ref = self._resolve_upstream_ref()
        git_commit = self._fetch_remote_ref(upstream_ref)

        self._emit(
            progress,
            f"已同步远端引用 {upstream_ref}，提交 {git_commit[:8]}。",
        )
        archives: list[PackageArchive] = []

        with tempfile.TemporaryDirectory(prefix="wdh_bundle_") as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            for component in selected_components:
                archive = self._create_component_archive(
                    component=component,
                    temp_dir=temp_dir,
                    output_dir=output_dir,
                    upstream_ref=upstream_ref,
                    git_commit=git_commit,
                    progress=progress,
                )
                archives.append(archive)

        self._emit(progress, f"打包完成，共生成 {len(archives)} 个压缩包。")
        return PackageResult(
            git_ref=upstream_ref,
            git_commit=git_commit,
            archives=tuple(archives),
        )

    def assemble_packages(
        self,
        package_dir: Path,
        target_base_dir: Path,
        skip_files: Sequence[str] = DEFAULT_SKIP_FILES,
        progress: ProgressCallback | None = None,
    ) -> AssembleResult:
        """Extract multiple bundles and reassemble them into one project tree."""

        if not package_dir.exists():
            raise DeploymentBundleError(f"找不到压缩包目录: {package_dir}")
        if not package_dir.is_dir():
            raise DeploymentBundleError(f"压缩包来源不是目录: {package_dir}")

        target_base_dir.mkdir(parents=True, exist_ok=True)
        component_archives = self._discover_component_archives(package_dir)
        copied_files = 0
        overwritten_files = 0
        skipped_files: set[str] = set()
        processed_components: list[str] = []
        project_dir: Path | None = None

        with tempfile.TemporaryDirectory(prefix="wdh_assemble_") as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            for component, archive_path in component_archives:
                extraction_dir = temp_dir / component.name
                extraction_dir.mkdir(parents=True, exist_ok=True)

                self._emit(progress, f"正在解压 {archive_path.name} ...")
                self._run_command(
                    [
                        self._seven_zip,
                        "x",
                        str(archive_path),
                        f"-o{extraction_dir}",
                        "-y",
                    ],
                    cwd=extraction_dir,
                )

                bundle_root = self._locate_bundle_root(extraction_dir)
                manifest = self._read_manifest(bundle_root)
                current_project_dir = target_base_dir / manifest.repo_name
                if project_dir is None:
                    project_dir = current_project_dir
                elif project_dir != current_project_dir:
                    raise DeploymentBundleError(
                        "压缩包目录中存在多个仓库名称，无法组装。"
                    )

                self._emit(progress, f"正在合并组件 {component.name} ...")
                merge_result = merge_bundle_into_target(
                    source_dir=bundle_root,
                    target_dir=project_dir,
                    skip_files=skip_files,
                )
                copied_files += merge_result.copied_files
                overwritten_files += merge_result.overwritten_files
                skipped_files.update(merge_result.skipped_files)
                processed_components.append(component.name)

        if project_dir is None:
            raise DeploymentBundleError("未发现可组装的压缩包。")

        self._emit(progress, f"组装完成: {project_dir}")
        return AssembleResult(
            project_dir=project_dir,
            copied_files=copied_files,
            overwritten_files=overwritten_files,
            skipped_files=tuple(sorted(skipped_files)),
            processed_components=tuple(processed_components),
        )

    def _resolve_upstream_ref(self) -> str:
        """Resolve the remote ref that should be packaged."""

        try:
            result = self._run_command(
                [
                    "git",
                    "rev-parse",
                    "--abbrev-ref",
                    "--symbolic-full-name",
                    "@{u}",
                ]
            )
            upstream_ref = result.stdout.strip()
            if upstream_ref:
                return upstream_ref
        except DeploymentBundleError:
            logger.warning("intranet_bundle.upstream_missing")

        branch_result = self._run_command(["git", "branch", "--show-current"])
        branch_name = branch_result.stdout.strip() or "main"
        return f"origin/{branch_name}"

    def _fetch_remote_ref(self, upstream_ref: str) -> str:
        """Fetch the latest remote ref and return its commit SHA."""

        remote_name = upstream_ref.split("/", maxsplit=1)[0]
        self._run_command(["git", "fetch", "--prune", remote_name])
        commit_result = self._run_command(["git", "rev-parse", upstream_ref])
        return commit_result.stdout.strip()

    def _create_component_archive(
        self,
        component: PackageComponent,
        temp_dir: Path,
        output_dir: Path,
        upstream_ref: str,
        git_commit: str,
        progress: ProgressCallback | None,
    ) -> PackageArchive:
        """Create one component archive in the output directory."""

        stage_dir = temp_dir / component.name
        bundle_root = stage_dir / self.repo_name
        bundle_root.mkdir(parents=True, exist_ok=True)

        if component.source_relative_path is None:
            self._emit(progress, "正在导出远端仓库主体代码...")
            self._export_remote_tree(upstream_ref, stage_dir, bundle_root)
            for excluded_path in component.excluded_paths:
                self._remove_path(bundle_root / excluded_path)
        else:
            self._emit(progress, f"正在打包目录 {component.source_relative_path} ...")
            self._copy_extra_item(component.source_relative_path, bundle_root)

        self._write_manifest(bundle_root, upstream_ref, git_commit, component)

        archive_path = output_dir / self._build_archive_name(
            component.name,
            git_commit,
        )
        if archive_path.exists():
            archive_path.unlink()

        self._run_command(
            [
                self._seven_zip,
                "a",
                "-t7z",
                str(archive_path),
                self.repo_name,
            ],
            cwd=stage_dir,
        )
        return PackageArchive(component_name=component.name, archive_path=archive_path)

    def _export_remote_tree(
        self,
        upstream_ref: str,
        temp_dir: Path,
        bundle_root: Path,
    ) -> None:
        """Export a clean tracked-tree snapshot from the upstream ref."""

        archive_path = temp_dir / "repo.zip"
        self._run_command(
            [
                "git",
                "archive",
                "--format=zip",
                f"--output={archive_path}",
                upstream_ref,
            ]
        )
        with ZipFile(archive_path, "r") as archive:
            archive.extractall(bundle_root)

    def _copy_extra_item(self, relative_path: str, bundle_root: Path) -> None:
        """Copy required extra content from the current working tree."""

        source_path = self.project_root / relative_path
        if not source_path.exists():
            raise DeploymentBundleError(f"打包必需内容缺失: {source_path}")

        destination_path = bundle_root / relative_path
        if source_path.is_dir():
            if destination_path.exists():
                shutil.rmtree(destination_path)
            shutil.copytree(source_path, destination_path)
        else:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)

    def _write_manifest(
        self,
        bundle_root: Path,
        upstream_ref: str,
        git_commit: str,
        component: PackageComponent,
    ) -> None:
        """Write bundle metadata into the package."""

        manifest = PackageManifest(
            repo_name=self.repo_name,
            component_name=component.name,
            git_ref=upstream_ref,
            git_commit=git_commit,
            generated_at=datetime.now().isoformat(timespec="seconds"),
            default_skip_files=DEFAULT_SKIP_FILES,
        )
        manifest_path = bundle_root / MANIFEST_NAME
        manifest_path.write_text(
            json.dumps(asdict(manifest), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _read_manifest(self, bundle_root: Path) -> PackageManifest:
        """Load package metadata from the extracted bundle."""

        manifest_path = bundle_root / MANIFEST_NAME
        if not manifest_path.exists():
            raise DeploymentBundleError(f"压缩包缺少清单文件: {MANIFEST_NAME}")

        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return PackageManifest(
            repo_name=raw_manifest["repo_name"],
            component_name=raw_manifest["component_name"],
            git_ref=raw_manifest["git_ref"],
            git_commit=raw_manifest["git_commit"],
            generated_at=raw_manifest["generated_at"],
            default_skip_files=tuple(raw_manifest["default_skip_files"]),
        )

    def _locate_bundle_root(self, extraction_dir: Path) -> Path:
        """Locate the top-level extracted repository directory."""

        manifest_candidates = list(extraction_dir.rglob(MANIFEST_NAME))
        if not manifest_candidates:
            raise DeploymentBundleError("压缩包中未找到部署清单，无法确定项目根目录。")
        return manifest_candidates[0].parent

    def _discover_component_archives(
        self,
        package_dir: Path,
    ) -> list[tuple[PackageComponent, Path]]:
        """Discover and validate component archives in a directory."""

        archives_by_name: dict[str, Path] = {}
        found_components: list[PackageComponent] = []
        for component in PACKAGE_COMPONENTS:
            matches = sorted(
                package_dir.glob(f"{self.repo_name}-intranet-{component.name}-*.7z")
            )
            if len(matches) > 1:
                raise DeploymentBundleError(
                    f"压缩包目录中存在多个 {component.name} 组件包，请只保留一个。"
                )
            if not matches:
                continue
            archives_by_name[component.name] = matches[0]
            found_components.append(component)

        if not found_components:
            raise DeploymentBundleError("压缩包目录中未找到可识别的组件包。")

        return [
            (component, archives_by_name[component.name])
            for component in found_components
        ]

    def _resolve_components(
        self,
        component_names: Sequence[str] | None,
    ) -> tuple[PackageComponent, ...]:
        """Resolve selected component names to known package components."""

        if component_names is None:
            return PACKAGE_COMPONENTS
        if not component_names:
            raise DeploymentBundleError("请至少选择一个需要打包的内容。")

        selected_components: list[PackageComponent] = []
        seen_names: set[str] = set()
        for name in component_names:
            if name in seen_names:
                continue
            component = PACKAGE_COMPONENTS_BY_NAME.get(name)
            if component is None:
                raise DeploymentBundleError(f"未知打包组件: {name}")
            selected_components.append(component)
            seen_names.add(name)

        if not selected_components:
            raise DeploymentBundleError("请至少选择一个需要打包的内容。")
        return tuple(selected_components)

    def _build_archive_name(self, component_name: str, git_commit: str) -> str:
        """Build a timestamped archive filename."""

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        short_commit = git_commit[:8]
        return (
            f"{self.repo_name}-intranet-{component_name}-{timestamp}-{short_commit}.7z"
        )

    def _remove_path(self, path: Path) -> None:
        """Remove a file or directory from a staging area if it exists."""

        if not path.exists():
            return
        if path.is_dir():
            shutil.rmtree(path)
            return
        path.unlink()

    def _run_command(
        self,
        command: Sequence[str],
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a subprocess and surface stderr as a domain-specific error."""

        try:
            return subprocess.run(
                list(command),
                cwd=cwd or self.project_root,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        except FileNotFoundError as exc:
            raise DeploymentBundleError(f"命令不可用: {command[0]}") from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            details = stderr or stdout or "unknown error"
            raise DeploymentBundleError(details) from exc

    def _emit(
        self,
        progress: ProgressCallback | None,
        message: str,
    ) -> None:
        """Send a progress message to the caller and logger."""

        logger.info("intranet_bundle.progress", message=message)
        if progress is not None:
            progress(message)
