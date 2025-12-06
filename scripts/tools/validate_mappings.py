#!/usr/bin/env python3
"""
Mapping Validation Script

Validates exported JSON mapping files for:
- JSON structure matches expected schema
- UTF-8 character preservation
- Row counts between source and exported data
- Missing entries and data quality metrics
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import psycopg2

from work_data_hub.config.settings import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MappingValidator:
    """Validates exported mapping JSON files."""

    def __init__(self):
        """Initialize validator with database connection."""
        self.settings = get_settings()
        self.dsn = self.settings.get_database_connection_string()
        self.validation_results: List[Dict[str, Any]] = []

        # Expected structure based on MappingExport model
        self.expected_keys = {"metadata", "data"}
        self.expected_metadata_keys = {
            "description",
            "source",
            "export_timestamp",
            "extractor_version",
            "row_count",
        }

    def validate_json_structure(self, file_path: Path) -> Dict[str, Any]:
        """Validate JSON structure matches expected schema."""
        result: Dict[str, Any] = {
            "file": str(file_path),
            "test": "json_structure",
            "passed": False,
            "issues": [],
        }

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Check top-level keys
            if not isinstance(data, dict):
                result["issues"].append("Root element is not a JSON object")
                return result

            missing_keys = self.expected_keys - set(data.keys())
            if missing_keys:
                result["issues"].append(f"Missing top-level keys: {missing_keys}")

            # Check metadata structure
            if "metadata" in data:
                if not isinstance(data["metadata"], dict):
                    result["issues"].append("metadata is not a JSON object")
                else:
                    missing_meta_keys = self.expected_metadata_keys - set(
                        data["metadata"].keys()
                    )
                    if missing_meta_keys:
                        result["issues"].append(
                            f"Missing metadata keys: {missing_meta_keys}"
                        )

            # Check data structure
            if "data" in data:
                if not isinstance(data["data"], dict):
                    result["issues"].append("data is not a JSON object")
                else:
                    # Verify all values are strings (as per mapping requirement)
                    for key, value in data["data"].items():
                        if not isinstance(key, str) or not isinstance(value, str):
                            result["issues"].append(
                                f"Non-string key-value pair: {key} -> {value}"
                            )
                            break

            result["passed"] = len(result["issues"]) == 0

        except json.JSONDecodeError as e:
            result["issues"].append(f"Invalid JSON: {e}")
        except Exception as e:
            result["issues"].append(f"Validation error: {e}")

        return result

    def validate_utf8_preservation(self, file_path: Path) -> Dict[str, Any]:
        """Validate UTF-8 character preservation, especially Chinese characters."""
        result: Dict[str, Any] = {
            "file": str(file_path),
            "test": "utf8_preservation",
            "passed": False,
            "issues": [],
            "chinese_chars_found": 0,
        }

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                data = json.loads(content)

            # Count Chinese characters in the file
            chinese_char_count = 0
            for char in content:
                if "\u4e00" <= char <= "\u9fff":  # Chinese character range
                    chinese_char_count += 1

            result["chinese_chars_found"] = chinese_char_count

            # Check if Chinese characters are properly preserved (not escaped)
            if chinese_char_count > 0:
                # Look for Unicode escape sequences which indicate improper encoding
                if "\\u" in content:
                    # Count Unicode escapes that might be Chinese characters
                    import re

                    unicode_escapes = re.findall(r"\\u[4-9][0-9a-f]{3}", content)
                    if unicode_escapes:
                        result["issues"].append(
                            f"Found {len(unicode_escapes)} Unicode escape sequences "
                            "for Chinese characters"
                        )
                else:
                    logger.info(
                        f"Chinese characters properly preserved: {chinese_char_count} found"
                    )

            # Verify we can round-trip the data without corruption
            if "data" in data:
                for key, value in data["data"].items():
                    # Try encoding/decoding to check for corruption
                    try:
                        key.encode("utf-8").decode("utf-8")
                        value.encode("utf-8").decode("utf-8")
                    except UnicodeError:
                        result["issues"].append(
                            f"UTF-8 encoding issue with key-value: {key} -> {value}"
                        )

            result["passed"] = len(result["issues"]) == 0

        except Exception as e:
            result["issues"].append(f"UTF-8 validation error: {e}")

        return result

    def validate_row_counts(self, file_path: Path) -> Dict[str, Any]:
        """Validate row counts between source and exported data."""
        result: Dict[str, Any] = {
            "file": str(file_path),
            "test": "row_count_verification",
            "passed": False,
            "issues": [],
            "exported_count": 0,
            "source_count": None,
        }

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "data" not in data or "metadata" not in data:
                result["issues"].append("Missing data or metadata sections")
                return result

            exported_count = len(data["data"])
            result["exported_count"] = exported_count

            # Get expected count from metadata
            metadata_count = data["metadata"].get("row_count")
            if metadata_count != exported_count:
                result["issues"].append(
                    f"Metadata row_count ({metadata_count}) != actual data count ({exported_count})"
                )

            # For database sources, verify against actual table
            source = data["metadata"].get("source")
            if source and source != "hardcoded_dictionary":
                try:
                    with psycopg2.connect(self.dsn) as conn:
                        with conn.cursor() as cursor:
                            # Check if table exists
                            cursor.execute(
                                """
                                SELECT EXISTS (
                                    SELECT 1 FROM information_schema.tables
                                    WHERE table_name = %s
                                );
                            """,
                                (source,),
                            )

                            table_exists_result = cursor.fetchone()
                            if table_exists_result and table_exists_result[0]:
                                # Get actual count from source table
                                cursor.execute(f"SELECT COUNT(*) FROM {source}")
                                count_result = cursor.fetchone()
                                if count_result:
                                    source_count = count_result[0]
                                    result["source_count"] = source_count

                                    # Note: exported count may be less than source due to WHERE
                                    if exported_count > source_count:
                                        result["issues"].append(
                                            f"Exported count ({exported_count}) > "
                                            f"source count ({source_count})"
                                        )
                            else:
                                result["issues"].append(
                                    f"Source table '{source}' not found"
                                )

                except Exception as e:
                    result["issues"].append(f"Database verification failed: {e}")

            result["passed"] = len(result["issues"]) == 0

        except Exception as e:
            result["issues"].append(f"Row count validation error: {e}")

        return result

    def validate_data_quality(self, file_path: Path) -> Dict[str, Any]:
        """Validate data quality metrics."""
        result: Dict[str, Any] = {
            "file": str(file_path),
            "test": "data_quality",
            "passed": False,
            "issues": [],
            "metrics": {},
        }

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "data" not in data:
                result["issues"].append("Missing data section")
                return result

            mappings = data["data"]

            # Calculate quality metrics
            metrics: Dict[str, Any] = {
                "total_mappings": len(mappings),
                "empty_keys": 0,
                "empty_values": 0,
                "duplicate_values": 0,
                "avg_key_length": 0.0,
                "avg_value_length": 0.0,
            }

            if mappings:
                key_lengths = []
                value_lengths = []
                seen_values = set()

                for key, value in mappings.items():
                    # Check for empty keys/values
                    if not key or not key.strip():
                        metrics["empty_keys"] += 1
                    if not value or not value.strip():
                        metrics["empty_values"] += 1

                    # Track lengths
                    key_lengths.append(len(key))
                    value_lengths.append(len(value))

                    # Check for duplicates
                    if value in seen_values:
                        metrics["duplicate_values"] += 1
                    seen_values.add(value)

                # Calculate averages
                metrics["avg_key_length"] = sum(key_lengths) / len(key_lengths)
                metrics["avg_value_length"] = sum(value_lengths) / len(value_lengths)

            result["metrics"] = metrics

            # Flag quality issues
            if metrics["empty_keys"] > 0:
                result["issues"].append(f"Found {metrics['empty_keys']} empty keys")
            if metrics["empty_values"] > 0:
                result["issues"].append(f"Found {metrics['empty_values']} empty values")
            if metrics["duplicate_values"] > 0:
                result["issues"].append(
                    f"Found {metrics['duplicate_values']} duplicate values"
                )

            result["passed"] = len(result["issues"]) == 0

        except Exception as e:
            result["issues"].append(f"Data quality validation error: {e}")

        return result

    def validate_single_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Run all validations on a single file."""
        logger.info(f"Validating {file_path}")

        results = [
            self.validate_json_structure(file_path),
            self.validate_utf8_preservation(file_path),
            self.validate_row_counts(file_path),
            self.validate_data_quality(file_path),
        ]

        return results

    def validate_all_mappings(
        self, mappings_dir: str = "tests/fixtures/mappings"
    ) -> bool:
        """Validate all mapping files in the directory."""
        mappings_path = Path(mappings_dir)

        if not mappings_path.exists():
            logger.error(f"Mappings directory not found: {mappings_path}")
            return False

        json_files = list(mappings_path.glob("*.json"))
        if not json_files:
            logger.error("No JSON mapping files found")
            return False

        logger.info(f"Found {len(json_files)} mapping files to validate")

        all_results = []
        for json_file in json_files:
            file_results = self.validate_single_file(json_file)
            all_results.extend(file_results)

        # Generate validation report
        self.generate_validation_report(all_results, mappings_path)

        # Check overall success
        failed_tests = [r for r in all_results if not r["passed"]]
        success = len(failed_tests) == 0

        if success:
            logger.info("✅ All validation tests passed")
        else:
            logger.error(f"❌ {len(failed_tests)} validation tests failed")

        return success

    def generate_validation_report(
        self, results: List[Dict[str, Any]], output_dir: Path
    ):
        """Generate detailed validation report."""
        report_path = output_dir / "_validation_report.md"

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# Mapping Validation Report\n\n")
            f.write(f"Generated on: {self.get_timestamp()}\n\n")

            # Summary
            total_tests = len(results)
            passed_tests = len([r for r in results if r["passed"]])
            f.write("## Summary\n\n")
            f.write(f"- Total tests: {total_tests}\n")
            f.write(f"- Passed: {passed_tests}\n")
            f.write(f"- Failed: {total_tests - passed_tests}\n\n")

            # Group results by file
            by_file: Dict[str, List[Dict[str, Any]]] = {}
            for result in results:
                file_name = Path(result["file"]).name
                if file_name not in by_file:
                    by_file[file_name] = []
                by_file[file_name].append(result)

            # Detailed results
            f.write("## Detailed Results\n\n")
            for file_name, file_results in by_file.items():
                f.write(f"### {file_name}\n\n")

                for result in file_results:
                    status = "✅ PASS" if result["passed"] else "❌ FAIL"
                    f.write(f"**{result['test']}**: {status}\n\n")

                    if result["issues"]:
                        f.write("Issues:\n")
                        for issue in result["issues"]:
                            f.write(f"- {issue}\n")
                        f.write("\n")

                    # Add metrics if available
                    if "metrics" in result and result["metrics"]:
                        f.write("Metrics:\n")
                        for key, value in result["metrics"].items():
                            f.write(f"- {key}: {value}\n")
                        f.write("\n")

                    if "chinese_chars_found" in result:
                        f.write(
                            f"Chinese characters found: {result['chinese_chars_found']}\n\n"
                        )

        logger.info(f"Validation report saved to {report_path}")

    def get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime

        return datetime.now().isoformat()


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate exported mapping JSON files")
    parser.add_argument("--file", "-f", help="Validate specific file")
    parser.add_argument(
        "--dir", "-d", default="tests/fixtures/mappings", help="Mappings directory"
    )

    args = parser.parse_args()

    try:
        validator = MappingValidator()

        if args.file:
            file_path = Path(args.file)
            if not file_path.exists():
                print(f"❌ File not found: {file_path}")
                return

            results = validator.validate_single_file(file_path)

            # Print results
            for result in results:
                status = "✅ PASS" if result["passed"] else "❌ FAIL"
                print(f"{result['test']}: {status}")
                if result["issues"]:
                    for issue in result["issues"]:
                        print(f"  - {issue}")
        else:
            success = validator.validate_all_mappings(args.dir)
            if success:
                print("✅ All validations passed")
            else:
                print("❌ Some validations failed - check the validation report")

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        print(f"❌ Validation failed: {e}")


if __name__ == "__main__":
    main()
