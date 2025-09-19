import importlib
import sys
from pathlib import Path


def _reload_settings_module():
    module_name = "src.work_data_hub.config.settings"
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_settings_reads_custom_env_file(tmp_path, monkeypatch):
    env_path = tmp_path / "custom.env"
    env_path.write_text("WDH_DATA_BASE_DIR=/tmp/custom-data\n")

    monkeypatch.setenv("WDH_ENV_FILE", str(env_path))

    settings_module = _reload_settings_module()
    try:
        settings_module.get_settings.cache_clear()
        settings = settings_module.get_settings()
        assert settings.data_base_dir == "/tmp/custom-data"
    finally:
        settings_module.get_settings.cache_clear()
        monkeypatch.delenv("WDH_ENV_FILE", raising=False)
        _reload_settings_module()
