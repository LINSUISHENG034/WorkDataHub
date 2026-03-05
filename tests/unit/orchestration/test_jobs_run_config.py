"""
Tests for build_run_config mapping of backfill CLI flags.

Note: build_run_config was moved from jobs.py to cli/etl.py in Story 6.2-P6
"""

from types import SimpleNamespace

from work_data_hub.cli.etl import build_run_config


def test_build_run_config_backfill_flags():
    args = SimpleNamespace(
        mode="delete_insert",
        plan_only=True,
        execute=False,
        sheet=0,
        max_files=1,
        pk=None,
        backfill_refs="all",
        backfill_mode="insert_missing",
    )

    run_config = build_run_config(args, domain="annuity_performance")

    assert "ops" in run_config
    # backfill op config (Epic 6.2: uses generic_backfill_refs_op)
    cfg = run_config["ops"]["generic_backfill_refs_op"]["config"]
    assert cfg["domain"] == "annuity_performance"
    assert cfg["plan_only"] is True

    # load op config exists and is consistent
    load_cfg = run_config["ops"]["load_op"]["config"]
    assert load_cfg["mode"] == "delete_insert"


def test_build_run_config_skip_facts_flag():
    """Test that --skip-facts flag is passed to load_op config."""
    args = SimpleNamespace(
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

    run_config = build_run_config(args, domain="annuity_performance")

    # Verify skip flag passed to load_op
    load_cfg = run_config["ops"]["load_op"]["config"]
    assert load_cfg["skip"] is True


def test_build_run_config_skip_facts_flag_defaults_false():
    """Test that skip flag defaults to False when not provided."""
    args = SimpleNamespace(
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

    run_config = build_run_config(args, domain="annuity_performance")

    # Verify skip flag defaults to False
    load_cfg = run_config["ops"]["load_op"]["config"]
    assert load_cfg["skip"] is False


def test_build_run_config_enrichment_sync_budget():
    """Test that enrichment_sync_budget is passed to process_domain_op_v2."""
    args = SimpleNamespace(
        mode="delete_insert",
        execute=True,
        sheet=0,
        max_files=1,
        pk=None,
        backfill_refs=None,
        backfill_mode="insert_missing",
        enrichment_sync_budget=300,
    )
    run_config = build_run_config(args, domain="annuity_performance")
    op_cfg = run_config["ops"]["process_domain_op_v2"]["config"]
    assert op_cfg["enrichment_sync_budget"] == 300


def test_build_run_config_enrichment_sync_budget_defaults_zero():
    """Test that enrichment_sync_budget defaults to 0 when not in args."""
    args = SimpleNamespace(
        mode="delete_insert",
        execute=False,
        sheet=0,
        max_files=1,
        pk=None,
        backfill_refs=None,
        backfill_mode="insert_missing",
        # no enrichment_sync_budget attribute
    )
    run_config = build_run_config(args, domain="annuity_performance")
    op_cfg = run_config["ops"]["process_domain_op_v2"]["config"]
    assert op_cfg["enrichment_sync_budget"] == 0
