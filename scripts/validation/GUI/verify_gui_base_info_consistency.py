#!/usr/bin/env python
"""
Verification script for GUI EQC Query base_info persistence consistency.

This script verifies that Solution C (using findDepart as raw_data fallback)
produces consistent results compared to the original ETL lookup behavior.

Usage:
    # Interactive mode (requires EQC token)
    PYTHONPATH=src uv run python scripts/validation/verify_gui_base_info_consistency.py

    # With specific company for testing
    PYTHONPATH=src uv run python \\
        scripts/validation/verify_gui_base_info_consistency.py \\
        --company-name "中国平安"
    PYTHONPATH=src uv run python \\
        scripts/validation/verify_gui_base_info_consistency.py \\
        --company-id "1000065057"

Test Strategy:
    1. Query by keyword (lookup) - captures search API response as raw_data
    2. Extract company_id from result
    3. Query by company_id (lookup_by_id) - uses findDepart as raw_data (Solution C)
    4. Compare the two raw_data structures to identify differences
    5. Verify downstream parsing compatibility

Expected Differences (Solution C):
    - raw_data structure differs: search API vs findDepart API response
    - Key fields should be present in both: companyId, companyFullName, unite_code
    - findDepart response has richer business details (address, legal_person, etc.)
    - search response has match-specific fields (type, _score, etc.)
"""

import argparse
import json
import sys
from typing import Any, Dict, Optional

# Ensure correct import path
sys.path.insert(0, "src")


def compare_raw_data_structures(
    search_raw: Optional[Dict[str, Any]],
    finddepart_raw: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compare raw_data structures from search API vs findDepart API.

    Returns a comparison report with:
    - common_keys: Keys present in both
    - search_only_keys: Keys only in search response
    - finddepart_only_keys: Keys only in findDepart response
    - value_differences: Keys with different values
    """
    report = {
        "common_keys": [],
        "search_only_keys": [],
        "finddepart_only_keys": [],
        "value_differences": [],
        "critical_fields_present": {},
    }

    if search_raw is None and finddepart_raw is None:
        report["error"] = "Both raw_data sources are None"
        return report

    if search_raw is None:
        report["search_only_keys"] = []
        report["finddepart_only_keys"] = (
            list(finddepart_raw.keys()) if finddepart_raw else []
        )
        return report

    if finddepart_raw is None:
        report["search_only_keys"] = list(search_raw.keys()) if search_raw else []
        report["finddepart_only_keys"] = []
        return report

    # Extract the relevant data structure
    # search API returns: {"list": [...], ...}
    # findDepart API returns: {"businessInfodto": {...}, ...}
    search_data = (
        search_raw.get("list", [{}])[0] if "list" in search_raw else search_raw
    )
    finddepart_data = (
        search_raw.get("businessInfodto", finddepart_raw)
        if "businessInfodto" in search_raw
        else finddepart_raw
    )

    # If finddepart_raw has businessInfodto, extract it
    if isinstance(finddepart_raw, dict) and "businessInfodto" in finddepart_raw:
        finddepart_data = finddepart_raw["businessInfodto"]

    search_keys = set(search_data.keys()) if isinstance(search_data, dict) else set()
    finddepart_keys = (
        set(finddepart_data.keys()) if isinstance(finddepart_data, dict) else set()
    )

    report["common_keys"] = sorted(list(search_keys & finddepart_keys))
    report["search_only_keys"] = sorted(list(search_keys - finddepart_keys))
    report["finddepart_only_keys"] = sorted(list(finddepart_keys - search_keys))

    # Check critical fields
    critical_fields = ["companyId", "companyFullName", "unite_code", "company_id"]
    for field in critical_fields:
        in_search = field in search_keys or any(
            field.lower() in k.lower() for k in search_keys
        )
        in_finddepart = field in finddepart_keys or any(
            field.lower() in k.lower() for k in finddepart_keys
        )
        report["critical_fields_present"][field] = {
            "in_search": in_search,
            "in_finddepart": in_finddepart,
        }

    return report


def run_verification(  # noqa: PLR0912, PLR0915
    company_name: Optional[str] = None,
    company_id: Optional[str] = None,
    save_results: bool = False,
) -> Dict[str, Any]:
    """
    Run verification comparing lookup() vs lookup_by_id() raw_data.

    Args:
        company_name: Company name for keyword search
        company_id: Company ID for direct lookup
        save_results: Whether to save results to database

    Returns:
        Verification report dictionary
    """
    from work_data_hub.gui.eqc_query.controller import EqcQueryController

    controller = EqcQueryController()
    report = {
        "test_input": {
            "company_name": company_name,
            "company_id": company_id,
        },
        "lookup_result": None,
        "lookup_by_id_result": None,
        "raw_data_comparison": None,
        "conclusion": None,
    }

    # Try to load existing token
    if not controller.try_load_existing_token():
        print("No valid token found. Please authenticate first.")
        print("Run: uv run python -m work_data_hub.io.auth --capture --save")
        report["error"] = "Authentication required"
        return report

    print(
        f"Token loaded. Budget: {controller.remaining_budget}/{controller.total_budget}"
    )

    # Step 1: Keyword lookup (if company_name provided)
    search_raw_data = None
    if company_name:
        print(f"\n[Step 1] Lookup by keyword: {company_name}")
        result = controller.lookup(company_name)
        report["lookup_result"] = {
            "success": result.success,
            "company_id": result.company_id,
            "official_name": result.official_name,
            "unified_credit_code": result.unified_credit_code,
            "confidence": result.confidence,
            "match_type": result.match_type,
            "error": result.error_message,
        }

        if result.success:
            print(f"  Found: {result.company_id} - {result.official_name}")
            search_raw_data = controller._last_raw_search
            company_id = result.company_id  # Use for Step 2

            # Show raw_data structure
            if search_raw_data:
                print("  raw_data type: search API response")
                print(f"  raw_data keys: {list(search_raw_data.keys())[:5]}...")
        else:
            print(f"  Error: {result.error_message}")
            report["error"] = result.error_message
            return report

    # Step 2: Direct ID lookup
    if company_id:
        print(f"\n[Step 2] Lookup by ID: {company_id}")
        result_by_id = controller.lookup_by_id(company_id)
        report["lookup_by_id_result"] = {
            "success": result_by_id.success,
            "company_id": result_by_id.company_id,
            "official_name": result_by_id.official_name,
            "unified_credit_code": result_by_id.unified_credit_code,
            "confidence": result_by_id.confidence,
            "match_type": result_by_id.match_type,
            "error": result_by_id.error_message,
        }

        if result_by_id.success:
            print(f"  Found: {result_by_id.company_id} - {result_by_id.official_name}")
            finddepart_raw_data = controller._last_raw_search  # Now contains findDepart

            # Show raw_data structure (Solution C)
            if finddepart_raw_data:
                print("  raw_data type: findDepart API response (Solution C)")
                print(f"  raw_data keys: {list(finddepart_raw_data.keys())[:5]}...")

            # Step 3: Compare raw_data structures
            if search_raw_data and finddepart_raw_data:
                print("\n[Step 3] Comparing raw_data structures...")
                comparison = compare_raw_data_structures(
                    search_raw_data, finddepart_raw_data
                )
                report["raw_data_comparison"] = comparison

                print(f"  Common keys: {len(comparison['common_keys'])}")
                print(f"  Search-only keys: {len(comparison['search_only_keys'])}")
                print(
                    f"  FindDepart-only keys: {len(comparison['finddepart_only_keys'])}"
                )
                print("\n  Critical fields presence:")
                for field, presence in comparison["critical_fields_present"].items():
                    status = "✓" if presence["in_finddepart"] else "✗"
                    print(f"    {field}: {status} (findDepart)")

                # Conclusion
                all_critical_present = all(
                    v["in_finddepart"]
                    for v in comparison["critical_fields_present"].values()
                )
                if all_critical_present:
                    report["conclusion"] = (
                        "PASS: All critical fields present in findDepart response"
                    )
                    print(f"\n  ✓ Conclusion: {report['conclusion']}")
                else:
                    report["conclusion"] = (
                        "WARN: Some critical fields missing in findDepart response"
                    )
                    print(f"\n  ⚠ Conclusion: {report['conclusion']}")
        else:
            print(f"  Error: {result_by_id.error_message}")
            report["error"] = result_by_id.error_message

    # Optional: Save results
    if save_results and controller.can_save:
        print("\n[Step 4] Saving result to database...")
        saved = controller.save_last_result()
        report["saved"] = saved
        print(f"  Saved: {saved}")

    controller.close()
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Verify GUI EQC Query base_info persistence consistency"
    )
    parser.add_argument(
        "--company-name",
        type=str,
        help="Company name for keyword search",
    )
    parser.add_argument(
        "--company-id",
        type=str,
        help="Company ID for direct lookup",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save results to database after verification",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file for verification report",
    )

    args = parser.parse_args()

    # Default test case if no arguments provided
    if not args.company_name and not args.company_id:
        print("=" * 60)
        print("GUI EQC Query - base_info Consistency Verification")
        print("Solution C: Using findDepart as raw_data fallback")
        print("=" * 60)
        print("\nNo test data provided. Using default test case.")
        print("For custom testing, use:")
        print("  --company-name '公司名称'  (keyword search)")
        print("  --company-id '1000065057'  (direct ID lookup)")
        print()

        # Interactive prompt
        company_name = input(
            "Enter company name for testing (or press Enter to skip): "
        ).strip()
        if not company_name:
            company_id = input(
                "Enter company ID for testing (or press Enter to exit): "
            ).strip()
            if not company_id:
                print("No input provided. Exiting.")
                return
            args.company_id = company_id
        else:
            args.company_name = company_name

    # Run verification
    report = run_verification(
        company_name=args.company_name,
        company_id=args.company_id,
        save_results=args.save,
    )

    # Output report
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nReport saved to: {args.output}")

    print("\n" + "=" * 60)
    print("Verification Complete")
    print("=" * 60)

    # Summary
    if report.get("conclusion"):
        print(f"Result: {report['conclusion']}")
    elif report.get("error"):
        print(f"Error: {report['error']}")


if __name__ == "__main__":
    main()
