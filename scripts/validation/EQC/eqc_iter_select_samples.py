"""
Step 1: 随机选取验证样本

按照 cleansing-rules-iteration-guide.md 的指引，执行样本选取。
"""

from sqlalchemy import create_engine, text

from work_data_hub.config.settings import get_settings


def main():
    settings = get_settings()
    engine = create_engine(settings.get_database_connection_string())

    with engine.connect() as conn:
        # 1. 清除之前的验证标记
        print("清除之前的验证标记...")
        result = conn.execute(
            text(
                "UPDATE enterprise.archive_base_info SET for_check = false WHERE for_check = true"
            )
        )
        print(f"  清除了 {result.rowcount} 条旧标记")
        conn.commit()

        # 2. 随机选取 5 条记录并标记
        print("\n随机选取 5 条记录并标记...")
        result = conn.execute(
            text("""
            UPDATE enterprise.archive_base_info
            SET for_check = true
            WHERE company_id IN (
                SELECT company_id FROM enterprise.archive_base_info
                ORDER BY RANDOM()
                LIMIT 5
            )
        """)
        )
        print(f"  标记了 {result.rowcount} 条新记录")
        conn.commit()

        # 3. 查看选中的记录
        print("\n选中的验证样本：")
        print("-" * 80)
        rows = conn.execute(
            text("""
            SELECT company_id, search_key_word, "companyFullName"
            FROM enterprise.archive_base_info
            WHERE for_check = true
        """)
        ).fetchall()

        for i, row in enumerate(rows, 1):
            print(f"[{i}] company_id: {row[0]}")
            print(f"    search_key_word: {row[1]}")
            print(f"    companyFullName: {row[2]}")
            print()

        print(f"共选中 {len(rows)} 条记录作为验证样本")


if __name__ == "__main__":
    main()
