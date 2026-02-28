"""Extract missing company_id data from 规模明细 and format for 客户明细 insertion.

Simulates what fk_customer backfill would produce using the same aggregation
logic from foreign_keys.yml (max_by, concat_distinct, count_distinct, etc.).
"""

import logging
import os
import sys

import pandas as pd
import psycopg
from dotenv import load_dotenv

logging.disable(logging.CRITICAL)
load_dotenv(".wdh_env", override=True)

conn = psycopg.connect(os.getenv("DATABASE_URL"))

# Step 1: Find all company_ids in 规模明细 but NOT in 客户明细
missing_sql = """
    SELECT DISTINCT s.company_id
    FROM business.规模明细 s
    LEFT JOIN customer."客户明细" c ON s.company_id = c.company_id
    WHERE c.company_id IS NULL
      AND s.company_id IS NOT NULL
      AND s.company_id != ''
"""
missing_ids = pd.read_sql(missing_sql, conn)["company_id"].tolist()
print(f"Found {len(missing_ids)} missing company_ids")

if not missing_ids:
    print("No missing company_ids found. Exiting.")
    conn.close()
    sys.exit(0)

# Step 2: Pull all raw data for these company_ids from 规模明细
placeholders = ",".join(["%s"] * len(missing_ids))
raw_sql = f"""
    SELECT company_id, "客户名称", "机构代码", "机构名称", "业务类型",
           "计划代码", "计划类型", "期末资产规模", "月度"
    FROM business.规模明细
    WHERE company_id IN ({placeholders})
"""
raw_df = pd.read_sql(raw_sql, conn, params=missing_ids)
print(f"Raw records for missing IDs: {len(raw_df)}")

# Step 3: Apply the same aggregation logic as foreign_keys.yml fk_customer.
results = []
for cid, group in raw_df.groupby("company_id"):
    row = {"company_id": cid}

    # 客户名称: first non-null
    customer_names = group["客户名称"].dropna()
    row["客户名称"] = customer_names.iloc[0] if len(customer_names) > 0 else None

    # 主拓机构代码: max_by(期末资产规模)
    if "期末资产规模" in group.columns and group["期末资产规模"].notna().any():
        max_idx = group["期末资产规模"].idxmax()
        row["主拓机构代码"] = group.loc[max_idx, "机构代码"]
        row["主拓机构"] = group.loc[max_idx, "机构名称"]
    else:
        org_codes = group["机构代码"].dropna()
        org_names = group["机构名称"].dropna()
        row["主拓机构代码"] = org_codes.iloc[0] if len(org_codes) > 0 else None
        row["主拓机构"] = org_names.iloc[0] if len(org_names) > 0 else None

    # 管理资格: concat_distinct(业务类型, separator="+")
    biz_types = sorted(group["业务类型"].dropna().unique())
    row["管理资格"] = "+".join(biz_types) if biz_types else None

    # 年金计划类型: concat_distinct(计划类型, separator="/")
    plan_types = sorted(group["计划类型"].dropna().unique())
    row["年金计划类型"] = "/".join(plan_types) if plan_types else None

    # 关键年金计划: max_by(期末资产规模) on 计划代码
    if "期末资产规模" in group.columns and group["期末资产规模"].notna().any():
        row["关键年金计划"] = group.loc[max_idx, "计划代码"]
    else:
        plan_codes_non_null = group["计划代码"].dropna()
        row["关键年金计划"] = (
            plan_codes_non_null.iloc[0] if len(plan_codes_non_null) > 0 else None
        )

    # 其他年金计划: concat_distinct(计划代码, separator=",")
    plan_codes = sorted(group["计划代码"].dropna().unique())
    row["其他年金计划"] = ",".join(plan_codes) if plan_codes else None

    # 关联计划数: count_distinct(计划代码)
    row["关联计划数"] = group["计划代码"].dropna().nunique()

    # 关联机构数: count_distinct(机构名称)
    row["关联机构数"] = group["机构名称"].dropna().nunique()

    # 其他开拓机构: concat_distinct(机构名称, separator=",")
    orgs = sorted(group["机构名称"].dropna().unique())
    row["其他开拓机构"] = ",".join(orgs) if orgs else None

    # tags: jsonb_append → ["YYMM新建"] from first 月度
    if len(group["月度"].dropna()) > 0:
        first_month = pd.to_datetime(group["月度"].dropna().iloc[0])
        row["tags"] = f'["{first_month.strftime("%y%m")}新建"]'
    else:
        row["tags"] = "[]"

    # 年金客户类型: template → "新客"
    row["年金客户类型"] = "新客"

    results.append(row)

result_df = pd.DataFrame(results)

# Step 4: Save to CSV
output_path = "docs/missing_customer_records.csv"
result_df.to_csv(output_path, index=False, encoding="utf-8-sig")
print(f"\nSaved {len(result_df)} records to {output_path}")
print("\nPreview:")
print(result_df.to_string(index=False))

conn.close()
