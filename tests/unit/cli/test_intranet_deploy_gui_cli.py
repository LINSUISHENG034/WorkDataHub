"""Unit tests for the intranet deployment GUI CLI command."""

import sys
from types import ModuleType

import pytest

from work_data_hub.cli.__main__ import main


@pytest.mark.unit
def test_intranet_deploy_gui_command_launches_gui(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launched = {"called": False}

    fake_module = ModuleType("work_data_hub.gui.intranet_deploy.app")

    def fake_launch_gui() -> None:
        launched["called"] = True

    fake_module.launch_gui = fake_launch_gui  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules,
        "work_data_hub.gui.intranet_deploy.app",
        fake_module,
    )

    exit_code = main(["intranet-deploy-gui"])

    assert exit_code == 0
    assert launched["called"] is True
