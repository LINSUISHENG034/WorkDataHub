from unittest.mock import MagicMock

import pandas as pd

from work_data_hub.infrastructure.cleansing import normalize_company_name
from work_data_hub.infrastructure.enrichment.company_id_resolver import (
    CompanyIdResolver,
)
from work_data_hub.infrastructure.enrichment.types import ResolutionStrategy


def test_pipeline_flow_verification():
    """
    Validation script to verify the actual flow of data through the CompanyIdResolver.
    Focus: Raw Name vs Normalized Name handling in Lookup and Backflow.
    """
    print("\n--- Starting Pipeline Flow Verification ---\n")

    # 1. Setup Data
    # Scenario:
    # - Raw Name: "  中国平安(集团)股份有限公司-已转出  " (Dirty)
    # - Normalized: "中国平安（集团）股份有限公司" (Clean/Standardized via normalize_company_name)
    # - Existing ID: "999" (Simulating a row that already has an ID, triggering Backflow)

    raw_name = "  中国平安(集团)股份有限公司-已转出  "
    expected_normalized = normalize_company_name(raw_name)
    company_id = "999"

    print(f"Input Raw Name: '{raw_name}'")
    print(f"Expected Normalized Key: '{expected_normalized}'")

    df = pd.DataFrame(
        {
            "客户名称": [raw_name],
            "company_id": [
                company_id
            ],  # Already resolved via some other method (e.g. Account Number)
            "年金账户号": ["ACC123"],
        }
    )

    # 2. Mock Repository to capture what is actually being sent to DB
    mock_repo = MagicMock()
    # Mock insert_batch_with_conflict_check to return success
    mock_insert_result = MagicMock()
    mock_insert_result.inserted_count = 1
    mock_insert_result.skipped_count = 0
    mock_insert_result.conflicts = []
    mock_repo.insert_batch_with_conflict_check.return_value = mock_insert_result

    # 3. Initialize Resolver (supply empty YAML overrides to avoid loading config)
    resolver = CompanyIdResolver(
        yaml_overrides={
            "plan": {},
            "account": {},
            "hardcode": {},
            "name": {},
            "account_name": {},
        },
        mapping_repository=mock_repo,
    )
    strategy = ResolutionStrategy(
        customer_name_column="客户名称",
        output_column="company_id",
        enable_backflow=True,
    )

    # 4. Trigger Backflow Logic (simulating end of resolution process)
    # We manually create the mask for resolved rows (all rows in this case)
    resolved_mask = pd.Series([True], index=df.index)
    resolved_indices = list(df.index[resolved_mask])

    print("\n--- Triggering Backflow ---")
    resolver._backflow_new_mappings(df, resolved_indices, strategy)

    # 5. Inspect what was sent to the Repository
    # We want to see if 'alias_name' passed to insert_batch is RAW or NORMALIZED
    call_args = mock_repo.insert_batch_with_conflict_check.call_args
    if call_args:
        inserted_mappings = call_args[0][0]  # First arg is the list of mappings
        name_mapping = next(
            (m for m in inserted_mappings if m["match_type"] == "name"), None
        )

        if name_mapping:
            actual_alias = name_mapping["alias_name"]
            print("\n[Backflow Result]")
            print(f"Captured Alias Name sent to DB: '{actual_alias}'")

            if actual_alias == expected_normalized:
                print("✅ FINDING: Backflow uses NORMALIZED NAME.")
            elif actual_alias == raw_name.strip():
                print("❌ FINDING: Backflow uses RAW NAME (stripped).")
            else:
                print(f"❓ FINDING: Backflow uses unexpected format: '{actual_alias}'")
        else:
            print("❌ FINDING: No 'name' mapping generated.")
    else:
        print("❌ FINDING: Repository insert was never called.")

    # 6. Verify Lookup Logic
    # Now let's see what happens when we try to LOOKUP this name.
    # We mock the repository to contain the NORMALIZED name (simulating a "correct" Async Worker insert)
    # and see if lookup_batch is called with the Raw name or Normalized name.

    print("\n--- Triggering Lookup ---")
    mock_repo.lookup_batch.reset_mock()

    # Create a new DF with just the name, no ID
    df_lookup = pd.DataFrame({"客户名称": [raw_name]})
    mask_unresolved = pd.Series([True], index=df_lookup.index)

    resolver._resolve_via_db_cache(df_lookup, mask_unresolved, strategy)

    lookup_call_args = mock_repo.lookup_batch.call_args
    if lookup_call_args:
        looked_up_keys = lookup_call_args[0][0]  # First arg is list of keys
        print("\n[Lookup Result]")
        print(f"Keys sent to DB Lookup: {looked_up_keys}")

        if expected_normalized in looked_up_keys:
            print("✅ FINDING: Lookup uses NORMALIZED NAME.")
        elif (
            raw_name in looked_up_keys
        ):  # Note: lookup logic usually doesn't even strip!
            print("❌ FINDING: Lookup uses RAW NAME directly from DataFrame.")
        elif raw_name.strip() in looked_up_keys:
            print("❌ FINDING: Lookup uses STRIPPED RAW NAME.")
        else:
            print("❓ FINDING: Lookup uses unexpected keys.")
    else:
        print("❌ FINDING: Lookup batch was never called.")


if __name__ == "__main__":
    test_pipeline_flow_verification()
