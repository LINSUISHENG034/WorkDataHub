"""
Unit tests for Story 1.1: Project Structure and Development Environment Setup

Tests verify all acceptance criteria:
- AC-1: Project initialized with uv package manager
- AC-2: Directory structure follows Clean Architecture pattern
- AC-3: Core dependencies installed
- AC-4: Environment configuration template provided
"""

import os
from pathlib import Path

import pytest

# tomllib is only available in Python 3.11+, use tomli for 3.10
try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]

# Project root is 3 levels up from this test file
PROJECT_ROOT = Path(__file__).parent.parent.parent


@pytest.mark.unit
class TestAC1_UvProjectInitialization:
    """AC-1: Project initialized with uv package manager"""

    def test_pyproject_toml_exists(self) -> None:
        """Verify pyproject.toml exists with [project] metadata"""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml must exist"

        # Verify it contains valid TOML with [project] section
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)

        assert "project" in config, "[project] section must exist in pyproject.toml"
        assert "name" in config["project"], "[project] must have 'name' field"
        assert "version" in config["project"], "[project] must have 'version' field"
        assert (
            "requires-python" in config["project"]
        ), "[project] must have 'requires-python' field"

    def test_python_version_file_exists(self):
        """Verify .python-version file specifies Python 3.10+"""
        python_version_path = PROJECT_ROOT / ".python-version"
        assert python_version_path.exists(), ".python-version file must exist"

        # Verify it specifies Python 3.10+
        with open(python_version_path) as f:
            version = f.read().strip()

        # Parse major.minor version
        major, minor = map(int, version.split(".")[:2])
        assert (
            major == 3 and minor >= 10
        ), f".python-version must specify Python 3.10+, got {version}"

    def test_uv_lock_exists(self):
        """Verify uv.lock file committed to git (reproducible builds)"""
        uv_lock_path = PROJECT_ROOT / "uv.lock"
        assert uv_lock_path.exists(), "uv.lock file must exist for reproducible builds"


@pytest.mark.unit
class TestAC2_CleanArchitectureStructure:
    """AC-2: Directory structure follows Clean Architecture pattern"""

    REQUIRED_DIRECTORIES = [
        "src/work_data_hub/domain",
        "src/work_data_hub/io",
        "src/work_data_hub/orchestration",
        "src/work_data_hub/config",
        "src/work_data_hub/utils",
        "tests",
    ]

    def test_required_directories_exist(self):
        """Verify all required directories exist"""
        for dir_path in self.REQUIRED_DIRECTORIES:
            full_path = PROJECT_ROOT / dir_path
            assert (
                full_path.exists() and full_path.is_dir()
            ), f"Required directory must exist: {dir_path}"

    def test_all_directories_have_init_py(self):
        """Verify each directory has __init__.py for Python package recognition"""
        src_directories = [
            d for d in self.REQUIRED_DIRECTORIES if d.startswith("src/work_data_hub")
        ]

        for dir_path in src_directories:
            init_py = PROJECT_ROOT / dir_path / "__init__.py"
            assert init_py.exists(), f"{dir_path} must have __init__.py file"

    def test_readme_documents_structure(self):
        """Verify README.md documents directory structure and purpose"""
        readme_path = PROJECT_ROOT / "README.md"
        assert readme_path.exists(), "README.md must exist"

        with open(readme_path) as f:
            content = f.read()

        # Verify README contains documentation of key concepts
        assert "domain" in content.lower(), "README must document domain/ layer"
        assert "io" in content.lower(), "README must document io/ layer"
        assert (
            "orchestration" in content.lower()
        ), "README must document orchestration/ layer"
        assert (
            "clean architecture" in content.lower()
        ), "README must explain Clean Architecture"


@pytest.mark.unit
class TestAC3_CoreDependencies:
    """AC-3: Core dependencies installed"""

    REQUIRED_PRODUCTION_DEPS = [
        "pandas",
        "pydantic",
        "structlog",
        "psycopg2-binary",
        "alembic",
        "dagster",
    ]

    REQUIRED_DEV_DEPS = ["mypy", "ruff", "pytest", "pytest-cov", "pytest-postgresql"]

    MIN_VERSIONS = {
        "pydantic": "2.11.7",
        "mypy": "1.17.1",
        "ruff": "0.12.12",
    }

    def test_production_dependencies_in_pyproject(self):
        """Verify production dependencies are declared in pyproject.toml"""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"

        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)

        deps = config["project"]["dependencies"]
        deps_str = " ".join(deps)  # Join all deps for substring matching

        for dep in self.REQUIRED_PRODUCTION_DEPS:
            assert dep in deps_str, f"Required production dependency missing: {dep}"

    def test_dev_dependencies_in_pyproject(self):
        """Verify dev dependencies are declared in pyproject.toml"""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"

        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)

        # Check both [project.optional-dependencies] and [dependency-groups]
        dev_deps = []
        if "project" in config and "optional-dependencies" in config["project"]:
            dev_deps.extend(config["project"]["optional-dependencies"].get("dev", []))
        if "dependency-groups" in config:
            dev_deps.extend(config["dependency-groups"].get("dev", []))

        deps_str = " ".join(dev_deps)

        for dep in self.REQUIRED_DEV_DEPS:
            assert dep in deps_str, f"Required dev dependency missing: {dep}"

    def test_minimum_versions_enforced(self):
        """Verify specific minimum versions for critical dependencies"""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"

        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)

        # Collect all dependency declarations
        all_deps = config["project"]["dependencies"].copy()
        if "project" in config and "optional-dependencies" in config["project"]:
            all_deps.extend(config["project"]["optional-dependencies"].get("dev", []))
        if "dependency-groups" in config:
            all_deps.extend(config["dependency-groups"].get("dev", []))

        for dep_name, min_version in self.MIN_VERSIONS.items():
            # Find dependency declaration
            dep_decl = [d for d in all_deps if dep_name in d]
            assert (
                dep_decl
            ), f"{dep_name} must be declared in dependencies with minimum version"

            # Verify version constraint
            dep_str = dep_decl[0]
            assert ">=" in dep_str, f"{dep_name} must specify minimum version with >="
            assert (
                min_version in dep_str
            ), f"{dep_name} must have minimum version {min_version}"

    def test_uv_lock_pins_all_dependencies(self):
        """Verify uv.lock exists and pins all dependencies"""
        uv_lock_path = PROJECT_ROOT / "uv.lock"
        assert uv_lock_path.exists(), "uv.lock must exist to pin all dependencies"

        # Verify it's not empty
        assert (
            uv_lock_path.stat().st_size > 0
        ), "uv.lock must not be empty (should contain locked dependencies)"


@pytest.mark.unit
class TestAC4_EnvironmentConfiguration:
    """AC-4: Environment configuration template provided"""

    REQUIRED_ENV_VARS = ["WDH_DATABASE", "WDH_LOG_LEVEL"]

    REQUIRED_GITIGNORE_PATTERNS = [
        ".env",
        "__pycache__",
        "*.py[cod]",  # Covers *.pyc, *.pyo, *.pyd
        ".pytest_cache",
        ".mypy_cache",
    ]

    def test_env_example_exists(self):
        """Verify .env.example file exists with placeholder values"""
        env_example_path = PROJECT_ROOT / ".env.example"
        assert env_example_path.exists(), ".env.example template must exist"

    def test_env_example_has_required_placeholders(self):
        """Verify .env.example contains required environment variables"""
        env_example_path = PROJECT_ROOT / ".env.example"

        with open(env_example_path) as f:
            content = f.read()

        for var in self.REQUIRED_ENV_VARS:
            assert (
                var in content
            ), f".env.example must contain placeholder for {var}"

    def test_env_in_gitignore(self):
        """Verify .env added to .gitignore (security requirement)"""
        gitignore_path = PROJECT_ROOT / ".gitignore"
        assert gitignore_path.exists(), ".gitignore must exist"

        with open(gitignore_path) as f:
            content = f.read()

        assert (
            ".env" in content
        ), ".env must be in .gitignore to prevent committing secrets"

    def test_gitignore_covers_python_artifacts(self):
        """Verify .gitignore covers all required Python artifacts"""
        gitignore_path = PROJECT_ROOT / ".gitignore"

        with open(gitignore_path) as f:
            content = f.read()

        for pattern in self.REQUIRED_GITIGNORE_PATTERNS:
            assert (
                pattern in content
            ), f".gitignore must contain pattern: {pattern}"


@pytest.mark.unit
class TestProjectDocumentation:
    """Verify comprehensive project documentation exists"""

    def test_readme_exists_and_comprehensive(self):
        """Verify README.md exists and documents key setup information"""
        readme_path = PROJECT_ROOT / "README.md"
        assert readme_path.exists(), "README.md must exist in project root"

        with open(readme_path) as f:
            content = f.read()

        # Verify README documents essential setup information
        assert (
            "uv" in content.lower()
        ), "README must document uv package manager usage"
        assert (
            "setup" in content.lower() or "installation" in content.lower()
        ), "README must include setup/installation instructions"

        # Verify comprehensive sections
        assert len(content) > 1000, "README should be comprehensive (>1000 chars)"
