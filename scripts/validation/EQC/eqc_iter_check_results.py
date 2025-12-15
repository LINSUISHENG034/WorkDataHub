"""
Step 4: 检查清洗结果

按照 cleansing-rules-iteration-guide.md 的指引，执行清洗结果检查。
"""

from sqlalchemy import create_engine, text
from work_data_hub.config.settings import get_settings

def main():
    settings = get_settings()
    engine = create_engine(settings.get_database_connection_string())

    with engine.connect() as conn:
        print("=" * 80)
        print("4.1 字段完整性检查")
        print("=" * 80)

        result = conn.execute(text("""
            SELECT
                COUNT(*) AS total,
                COUNT(company_name) AS has_company_name,
                COUNT(registered_date) AS has_reg_date,
                COUNT(registered_capital) AS has_reg_capital,
                COUNT(legal_person_name) AS has_legal_person,
                COUNT(credit_code) AS has_credit_code,
                COUNT(industry_name) AS has_industry
            FROM enterprise.business_info
            WHERE company_id IN (
                SELECT company_id FROM enterprise.archive_base_info WHERE for_check = true
            )
        """)).fetchone()

        print(f"Total records: {result[0]}")
        print(f"  has_company_name:    {result[1]}/{result[0]} ({100*result[1]/result[0]:.0f}%)")
        print(f"  has_registered_date: {result[2]}/{result[0]} ({100*result[2]/result[0]:.0f}%)")
        print(f"  has_reg_capital:     {result[3]}/{result[0]} ({100*result[3]/result[0]:.0f}%)")
        print(f"  has_legal_person:    {result[4]}/{result[0]} ({100*result[4]/result[0]:.0f}%)")
        print(f"  has_credit_code:     {result[5]}/{result[0]} ({100*result[5]/result[0]:.0f}%)")
        print(f"  has_industry:        {result[6]}/{result[0]} ({100*result[6]/result[0]:.0f}%)")

        print("\n" + "=" * 80)
        print("4.2 数据类型验证")
        print("=" * 80)

        rows = conn.execute(text("""
            SELECT
                company_id,
                company_name,
                registered_date,
                pg_typeof(registered_date) AS date_type,
                registered_capital,
                pg_typeof(registered_capital) AS capital_type
            FROM enterprise.business_info
            WHERE company_id IN (
                SELECT company_id FROM enterprise.archive_base_info WHERE for_check = true
            )
        """)).fetchall()

        for row in rows:
            print(f"\ncompany_id: {row[0]}")
            print(f"  company_name: {row[1]}")
            print(f"  registered_date: {row[2]} (type: {row[3]})")
            print(f"  registered_capital: {row[4]} (type: {row[5]})")

        print("\n" + "=" * 80)
        print("4.3 清洗状态分析")
        print("=" * 80)

        rows = conn.execute(text("""
            SELECT
                company_id,
                company_name,
                _cleansing_status->>'registered_date' AS date_status,
                _cleansing_status->>'registered_capital' AS capital_status,
                _cleansing_status->>'colleagues_num' AS colleagues_status
            FROM enterprise.business_info
            WHERE company_id IN (
                SELECT company_id FROM enterprise.archive_base_info WHERE for_check = true
            )
        """)).fetchall()

        for row in rows:
            print(f"\ncompany_id: {row[0]} ({row[1]})")
            print(f"  registered_date:    {row[2]}")
            print(f"  registered_capital: {row[3]}")
            print(f"  colleagues_num:     {row[4]}")

        print("\n" + "=" * 80)
        print("检查完成")
        print("=" * 80)

if __name__ == "__main__":
    main()
