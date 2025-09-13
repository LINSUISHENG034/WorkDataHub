"""
Tests for build_run_config mapping of backfill CLI flags.
"""

from types import SimpleNamespace

from src.work_data_hub.orchestration.jobs import build_run_config


def test_build_run_config_backfill_flags():
    args = SimpleNamespace(
        domain="annuity_performance",
        mode="delete_insert",
        plan_only=True,
        execute=False,
        sheet=0,
        max_files=1,
        pk=None,
        backfill_refs="all",
        backfill_mode="insert_missing",
    )

    run_config = build_run_config(args)

    assert "ops" in run_config
    # backfill op config
    cfg = run_config["ops"]["backfill_refs_op"]["config"]
    assert cfg["targets"] == ["all"]
    assert cfg["mode"] == "insert_missing"
    assert cfg["plan_only"] is True

    # load op config exists and is consistent
    load_cfg = run_config["ops"]["load_op"]["config"]
    assert load_cfg["mode"] == "delete_insert"


def test_build_run_config_skip_facts_flag():
    """Test that --skip-facts flag is passed to load_op config."""
    args = SimpleNamespace(
        domain="annuity_performance",
        mode="delete_insert",
        plan_only=True,
        execute=False,
        skip_facts=True,  # NEW: skip facts flag
        sheet=0,
        max_files=1,
        pk=None,
        backfill_refs=None,
        backfill_mode="insert_missing",
    )

    run_config = build_run_config(args)

    # Verify skip flag passed to load_op
    load_cfg = run_config["ops"]["load_op"]["config"]
    assert load_cfg["skip"] is True


def test_build_run_config_skip_facts_flag_defaults_false():
    """Test that skip flag defaults to False when not provided."""
    args = SimpleNamespace(
        domain="annuity_performance",
        mode="delete_insert",
        plan_only=True,
        execute=False,
        sheet=0,
        max_files=1,
        pk=None,
        backfill_refs=None,
        backfill_mode="insert_missing",
        # Note: no skip_facts attribute
    )

    run_config = build_run_config(args)

    # Verify skip flag defaults to False
    load_cfg = run_config["ops"]["load_op"]["config"]
    assert load_cfg["skip"] is False
