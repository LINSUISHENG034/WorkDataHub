"""
Test script to diagnose Dagster GenericBackfillConfig validation error.
"""
import traceback

try:
    # Try to validate the config directly
    from work_data_hub.orchestration.ops import GenericBackfillConfig
    
    # This is what CLI sends
    config_dict = {
        "domain": "annuity_performance",
        "plan_only": False,
        "add_tracking_fields": False,
    }
    
    print("Testing GenericBackfillConfig validation...")
    print(f"Input config: {config_dict}")
    
    # Try creating the config
    config = GenericBackfillConfig(**config_dict)
    print(f"SUCCESS: {config}")
    
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    traceback.print_exc()

# Also test the full job execution with minimal setup
print("\n" + "=" * 60)
print("Testing job execution with minimal config...")
print("=" * 60)

try:
    from work_data_hub.orchestration.jobs import annuity_performance_job
    
    run_config = {
        "ops": {
            "discover_files_op": {"config": {"domain": "annuity_performance", "period": "202510"}},
            "read_excel_op": {"config": {"sheet": "规模明细"}},
            "load_op": {"config": {"table": "business.规模明细", "mode": "delete_insert", "pk": [], "plan_only": True, "skip": False}},
            "generic_backfill_refs_op": {"config": {"domain": "annuity_performance", "plan_only": True, "add_tracking_fields": False}},
            "process_annuity_performance_op": {"config": {"enrichment_enabled": False, "enrichment_sync_budget": 0, "export_unknown_names": True, "plan_only": True, "use_pipeline": None}},
        }
    }
    
    print(f"Run config for generic_backfill_refs_op: {run_config['ops']['generic_backfill_refs_op']}")
    
    # Just test config parsing, not full execution
    result = annuity_performance_job.execute_in_process(
        run_config=run_config,
        raise_on_error=True,
    )
    print(f"Result: success={result.success}")
    
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    traceback.print_exc()
