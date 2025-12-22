"""
Tests for FileDiscoveryService (Epic 3 Schema).
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from work_data_hub.io.connectors.file_connector import (
    FileDiscoveryService,
    DiscoveryMatch,
)
from work_data_hub.io.connectors.exceptions import (
    DiscoveryError,
)
from work_data_hub.infrastructure.settings.data_source_schema import (
    DataSourceConfigV2,
    DomainConfigV2,
)


@pytest.fixture
def mock_settings(tmp_path):
    """Mock settings with a temporary config file."""
    config_path = tmp_path / "data_sources.yml"
    
    # Create valid V2 config
    config_data = {
        "version": "2.0",
        "domains": {
            "test_domain": {
                "base_path": str(tmp_path / "data" / "{YYYYMM}"),
                "file_patterns": ["test_*.xlsx"],
                "sheet_name": "Sheet1",
                "version_strategy": "highest_number",
            }
        }
    }
    
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f)
        
    mock = MagicMock()
    mock.data_sources_config = str(config_path)
    return mock


@pytest.fixture
def file_discovery_service(mock_settings):
    """Create service instance with mocked settings."""
    return FileDiscoveryService(settings=mock_settings)


class TestFileDiscoveryService:
    """Tests for FileDiscoveryService."""

    def test_discover_file_success(self, file_discovery_service, tmp_path):
        """Test successful file discovery."""
        # Setup filesystem
        month = "202401"
        base_dir = tmp_path / "data" / month / "V1"
        base_dir.mkdir(parents=True)
        (base_dir / "test_file.xlsx").touch()
        
        # Execute
        result = file_discovery_service.discover_file(
            domain="test_domain",
            YYYYMM=month
        )
        
        # Verify
        assert isinstance(result, DiscoveryMatch)
        assert result.version == "V1"
        assert result.sheet_name == "Sheet1"
        assert result.file_path.name == "test_file.xlsx"

    def test_discover_file_version_override(self, file_discovery_service, tmp_path):
        """Test version override."""
        # Setup filesystem for override version
        month = "202401"
        base_dir = tmp_path / "data" / month / "V99"
        base_dir.mkdir(parents=True)
        (base_dir / "test_file.xlsx").touch()
        
        # Execute with override
        result = file_discovery_service.discover_file(
            domain="test_domain",
            version_override="V99",
            YYYYMM=month
        )
        
        # Verify
        assert result.version == "V99"
        assert "V99" in str(result.file_path)

    def test_discover_file_no_match(self, file_discovery_service, tmp_path):
        """Test fallback when no file matches."""
        # Setup filesystem but no matching file
        month = "202401"
        base_dir = tmp_path / "data" / month / "V1"
        base_dir.mkdir(parents=True)
        (base_dir / "other_file.txt").touch()
        
        # Execute and expect error
        with pytest.raises(DiscoveryError) as exc:
            file_discovery_service.discover_file(
                domain="test_domain",
                YYYYMM=month
            )
        assert exc.value.failed_stage == "file_matching"

    def test_discover_file_missing_template_var(self, file_discovery_service):
        """Test error when template variable is missing."""
        with pytest.raises(DiscoveryError) as exc:
            file_discovery_service.discover_file(domain="test_domain")
        
        assert exc.value.failed_stage == "config_validation"  # Template resolution falls under validation usually
        assert "YYYYMM" in str(exc.value)

    def test_discover_file_unknown_domain(self, file_discovery_service):
        """Test error when domain is unknown."""
        with pytest.raises(DiscoveryError) as exc:
            file_discovery_service.discover_file(domain="unknown_domain")
            
        assert exc.value.failed_stage == "config_validation"
        assert "not found" in str(exc.value)
