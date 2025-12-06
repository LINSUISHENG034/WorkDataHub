"""
Generate 10,000-row CSV fixture for performance testing.

This script generates a realistic annuity performance dataset with:
- 10,000 rows total
- 15-25 columns (typical production data)
- Mix of valid (90%) and invalid (10%) rows for validation testing
- Realistic data types: dates, decimals, strings, Chinese characters
- Data characteristics matching production annuity performance data

Usage:
    uv run python scripts/generate_performance_fixture.py

Output:
    tests/fixtures/performance/annuity_performance_10k.csv
"""

import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


def generate_report_dates(count: int) -> List[str]:
    """Generate realistic monthly report dates in YYYYMM format."""
    dates = []
    start_date = datetime(2020, 1, 1)

    for i in range(count):
        # Generate sequential months with some gaps
        date = start_date + timedelta(days=30 * i)
        dates.append(date.strftime("%Y%m"))

    return dates


def generate_plan_codes(count: int) -> List[str]:
    """Generate realistic plan codes."""
    prefixes = ["P", "PLAN", "YJ", "QY"]
    codes = []

    for i in range(count):
        prefix = random.choice(prefixes)
        number = random.randint(1, 9999)
        codes.append(f"{prefix}{number:04d}")

    return codes


def generate_portfolio_codes(plan_codes: List[str]) -> List[str]:
    """Generate portfolio codes matching plan code prefixes."""
    portfolio_codes = []

    for plan_code in plan_codes:
        # Portfolio code should start with plan prefix
        prefix = plan_code[:3]
        suffix = random.randint(1, 999)
        portfolio_codes.append(f"{prefix}{suffix:03d}")

    return portfolio_codes


def generate_company_names(count: int) -> List[str]:
    """Generate realistic Chinese company names."""
    prefixes = ["北京", "上海", "广州", "深圳", "杭州", "南京", "成都", "武汉"]
    suffixes = ["科技", "实业", "集团", "股份", "有限公司"]
    middles = ["XX", "YY", "ZZ", "AA", "BB", "CC", "DD", "EE"]

    names = []
    for _ in range(count):
        prefix = random.choice(prefixes)
        middle = random.choice(middles)
        suffix = random.choice(suffixes)
        names.append(f"{prefix}{middle}{suffix}")

    return names


def generate_plan_types(count: int) -> List[str]:
    """Generate plan types."""
    types = ["企业年金", "职业年金", "养老金产品"]
    return [random.choice(types) for _ in range(count)]


def generate_scales(count: int, invalid_ratio: float = 0.1) -> List[float]:
    """Generate scale values (规模) with some invalid negative values."""
    scales = []
    invalid_count = int(count * invalid_ratio)

    for i in range(count):
        if i < invalid_count:
            # Generate invalid negative values
            scales.append(round(random.uniform(-100000, -0.01), 2))
        else:
            # Generate valid positive values
            scales.append(round(random.uniform(1000, 999999999), 2))

    random.shuffle(scales)
    return scales


def generate_returns(count: int) -> List[float]:
    """Generate return rates (收益率)."""
    return [round(random.uniform(-0.05, 0.15), 4) for _ in range(count)]


def generate_invalid_dates(count: int) -> List[str]:
    """Generate some invalid date formats for testing."""
    invalid_formats = [
        "INVALID",
        "20250115",  # YYYYMMDD instead of YYYYMM
        "2025-01",  # Hyphenated
        "2025年01月",  # Chinese format (might be valid depending on parser)
        "202513",  # Invalid month
        "999999",  # Nonsense
    ]
    return [random.choice(invalid_formats) for _ in range(count)]


def main():
    """Generate 10,000-row performance test fixture."""
    print("🚀 Generating 10,000-row annuity performance test fixture...")

    total_rows = 10000
    invalid_ratio = 0.10  # 10% invalid rows

    # Generate base data (90% valid)
    valid_count = int(total_rows * (1 - invalid_ratio))
    invalid_count = total_rows - valid_count

    print(f"   Total rows: {total_rows:,}")
    print(f"   Valid rows: {valid_count:,} ({(1 - invalid_ratio) * 100:.0f}%)")
    print(f"   Invalid rows: {invalid_count:,} ({invalid_ratio * 100:.0f}%)")

    # Generate valid data
    report_dates = generate_report_dates(valid_count)
    plan_codes = generate_plan_codes(valid_count)
    portfolio_codes = generate_portfolio_codes(plan_codes)
    company_names = generate_company_names(valid_count)
    plan_types = generate_plan_types(valid_count)
    scales = generate_scales(total_rows, invalid_ratio=invalid_ratio)
    returns = generate_returns(valid_count)

    # Build DataFrame with valid rows
    valid_data = {
        "月度": report_dates,
        "计划代码": plan_codes,
        "计划全称": [f"{name}年金计划" for name in company_names],
        "计划类型": plan_types,
        "组合代码": portfolio_codes,
        "组合名称": [f"{code}组合" for code in portfolio_codes],
        "规模": scales[:valid_count],
        "单位净值": [round(random.uniform(1.0, 2.0), 4) for _ in range(valid_count)],
        "收益率": returns,
        "累计收益率": [
            round(random.uniform(0.01, 0.50), 4) for _ in range(valid_count)
        ],
        "客户名称": company_names,
        "company_id": [random.randint(1000000, 9999999) for _ in range(valid_count)],
    }

    df_valid = pd.DataFrame(valid_data)

    # Generate invalid rows (with various error types)
    invalid_data_list: List[Dict[str, Any]] = []

    for i in range(invalid_count):
        error_type = random.choice(
            ["invalid_date", "negative_scale", "empty_required", "invalid_plan_type"]
        )

        if error_type == "invalid_date":
            invalid_row = {
                "月度": random.choice(generate_invalid_dates(10)),
                "计划代码": f"P{random.randint(1, 9999):04d}",
                "计划全称": f"测试计划{i}",
                "计划类型": random.choice(["企业年金", "职业年金"]),
                "组合代码": f"P{random.randint(1, 999):03d}",
                "组合名称": f"测试组合{i}",
                "规模": scales[valid_count + i],
                "单位净值": round(random.uniform(1.0, 2.0), 4),
                "收益率": round(random.uniform(-0.05, 0.15), 4),
                "累计收益率": round(random.uniform(0.01, 0.50), 4),
                "客户名称": f"测试公司{i}",
                "company_id": random.randint(1000000, 9999999),
            }
        elif error_type == "negative_scale":
            invalid_row = {
                "月度": datetime.now().strftime("%Y%m"),
                "计划代码": f"P{random.randint(1, 9999):04d}",
                "计划全称": f"测试计划{i}",
                "计划类型": random.choice(["企业年金", "职业年金"]),
                "组合代码": f"P{random.randint(1, 999):03d}",
                "组合名称": f"测试组合{i}",
                "规模": -abs(scales[valid_count + i]),  # Force negative
                "单位净值": round(random.uniform(1.0, 2.0), 4),
                "收益率": round(random.uniform(-0.05, 0.15), 4),
                "累计收益率": round(random.uniform(0.01, 0.50), 4),
                "客户名称": f"测试公司{i}",
                "company_id": random.randint(1000000, 9999999),
            }
        elif error_type == "empty_required":
            invalid_row = {
                "月度": datetime.now().strftime("%Y%m"),
                "计划代码": "",  # Empty required field
                "计划全称": f"测试计划{i}",
                "计划类型": random.choice(["企业年金", "职业年金"]),
                "组合代码": f"P{random.randint(1, 999):03d}",
                "组合名称": f"测试组合{i}",
                "规模": abs(scales[valid_count + i]),
                "单位净值": round(random.uniform(1.0, 2.0), 4),
                "收益率": round(random.uniform(-0.05, 0.15), 4),
                "累计收益率": round(random.uniform(0.01, 0.50), 4),
                "客户名称": f"测试公司{i}",
                "company_id": random.randint(1000000, 9999999),
            }
        else:  # invalid_plan_type
            invalid_row = {
                "月度": datetime.now().strftime("%Y%m"),
                "计划代码": f"P{random.randint(1, 9999):04d}",
                "计划全称": f"测试计划{i}",
                "计划类型": "INVALID_TYPE",  # Invalid enum value
                "组合代码": f"P{random.randint(1, 999):03d}",
                "组合名称": f"测试组合{i}",
                "规模": abs(scales[valid_count + i]),
                "单位净值": round(random.uniform(1.0, 2.0), 4),
                "收益率": round(random.uniform(-0.05, 0.15), 4),
                "累计收益率": round(random.uniform(0.01, 0.50), 4),
                "客户名称": f"测试公司{i}",
                "company_id": random.randint(1000000, 9999999),
            }

        invalid_data_list.append(invalid_row)

    df_invalid = pd.DataFrame(invalid_data_list)

    # Combine and shuffle
    df_combined = pd.concat([df_valid, df_invalid], ignore_index=True)
    df_combined = df_combined.sample(frac=1, random_state=42).reset_index(drop=True)

    # Create output directory if not exists
    output_dir = Path("tests/fixtures/performance")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save to CSV
    output_file = output_dir / "annuity_performance_10k.csv"
    df_combined.to_csv(output_file, index=False, encoding="utf-8-sig")

    print(f"✅ Generated test fixture: {output_file}")
    print(f"   File size: {output_file.stat().st_size / 1024:.1f} KB")
    print(f"   Columns: {len(df_combined.columns)}")
    print(f"   Rows: {len(df_combined):,}")

    # Display sample rows
    print("\n📊 Sample rows (first 3):")
    print(df_combined.head(3).to_string())

    # Display column info
    print("\n📋 Column information:")
    print(df_combined.dtypes)

    # Validation summary
    print("\n🔍 Validation characteristics:")
    negative_scales = (df_combined["规模"] < 0).sum()
    empty_plan_codes = (df_combined["计划代码"] == "").sum()
    invalid_dates = (
        df_combined["月度"]
        .apply(lambda x: not str(x).isdigit() or len(str(x)) != 6)
        .sum()
    )

    print(f"   Rows with negative 规模: {negative_scales}")
    print(f"   Rows with empty 计划代码: {empty_plan_codes}")
    print(f"   Rows with invalid 月度 format: {invalid_dates}")
    print(
        f"   Total validation errors: {negative_scales + empty_plan_codes + invalid_dates}"
    )

    print("\n✅ Fixture generation complete!")


if __name__ == "__main__":
    main()
