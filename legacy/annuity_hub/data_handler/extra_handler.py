import pandas as pd

from datetime import datetime
from typing import List
from tqdm import tqdm
from logger.logger import logger as logger
from textwrap import dedent

from database_operations.mongo_ops import MongoDBManager
from database_operations.mysql_ops import MySqlDBManager


def get_sql_statements():
    sql_insert = dedent("""
        INSERT INTO customer.`企年受托战客`(
          年金计划号, 年金计划全称,
          计划类型, 管理资格, 备注
        )
        SELECT
          mapping.`年金计划`.`年金计划号`,
          mapping.`年金计划`.`年金计划全称`,
          mapping.`年金计划`.`计划类型`,
          mapping.`年金计划`.`管理资格`,
          '新增' AS `备注`
        FROM
          (
            customer.`企年受托中标`
            INNER JOIN mapping.`年金计划` ON customer.`企年受托中标`.`年金计划号` = mapping.`年金计划`.`年金计划号`
          )
          LEFT JOIN customer.`企年受托战客` ON customer.`年金计划`.`年金计划号` = customer.`企年受托战客`.`年金计划号`
        WHERE
          customer.`企年受托中标`.`年金计划号` NOT IN ('AN001', 'AN002')
          AND ISNULL(customer.`企年受托战客`.`年金计划号`);
    """)

    sql_update = dedent("""
        UPDATE mapping.`组合计划`
        SET mapping.`组合计划`.`是否存款组合` = 1
        WHERE 
            INSTR(mapping.`组合计划`.`组合名称`, '存款') 
            OR INSTR(mapping.`组合计划`.`组合名称`, '定存') 
            OR INSTR(mapping.`组合计划`.`组合名称`, '协存');
    """)

    return [sql_insert, sql_update]


def execute_sql_statements():
    sql_statements = get_sql_statements()
    with MySqlDBManager(database="customer") as mysqldb:
        for sql in sql_statements:
            try:
                mysqldb.cursor.execute(sql)
                mysqldb.conn.commit()
                logger.info(f"SQL executed successfully: {sql.strip()}...")
            except Exception as e:
                mysqldb.conn.rollback()
                logger.error(f"Error executing SQL: {sql.strip()}: {e}", exc_info=True)


def process_worksheet(df, annuity_code, portfolio_code):
    # 数据重命名
    df.rename(
        columns={"计划号": "计划代码", "流失（含待遇支付）": "流失(含待遇支付)"},
        inplace=True,
    )

    # 修正组合编号
    df["组合代码"] = df["组合代码"].str.replace("^F", "", regex=True)

    # 整理未入库年金计划号
    new_annuity_code = (
        df[~df["计划代码"].isin(annuity_code["年金计划号"])]
        .groupby(["计划类型", "计划代码", "计划名称", "客户名称"])["业务类型"]
        .apply(lambda x: "+".join(sorted(set(x))))
        .reset_index()
    )
    new_annuity_code.rename(
        columns={
            "计划代码": "年金计划号",
            "计划名称": "计划全称",
            "业务类型": "管理资格",
        },
        inplace=True,
    )
    new_annuity_code["备注"] = datetime.now().strftime("%y年%m月") + "创建"

    # 整理未入库组合编号
    new_portfolio_code = (
        df[~df["组合代码"].isin(portfolio_code["组合代码"])]
        .groupby(["计划代码", "组合代码", "组合名称", "组合类型"])
        .size()
        .reset_index(name="Count")
        .drop("Count", axis=1)
    )
    new_portfolio_code.rename(columns={"计划代码": "年金计划号"}, inplace=True)
    new_portfolio_code["备注"] = datetime.now().strftime("%y年%m月") + "创建"

    return new_annuity_code, new_portfolio_code


def prefix_processing(files):
    with MySqlDBManager(database="mapping") as mysqldb:
        annuity_code = mysqldb.get_full_table("年金计划")
        portfolio_code = mysqldb.get_full_table("组合计划")

    new_annuity_codes = []
    new_portfolio_codes = []

    for file in tqdm(files, desc="Prefix Processing"):
        if "年金终稿数据" not in file.name:
            continue

        for sheet_name in ["规模明细", "收入明细"]:
            try:
                df = pd.read_excel(file, sheet_name=sheet_name, header=0, dtype=str)
            except Exception as e:
                logger.error(
                    f"Error reading file {file} for sheet {sheet_name}", exc_info=e
                )
                continue

            annuity, portfolio = process_worksheet(df, annuity_code, portfolio_code)
            new_annuity_codes.append(annuity)
            new_portfolio_codes.append(portfolio)

    # 去重并写入数据库
    with MySqlDBManager(database="mapping") as mysqldb:
        if new_annuity_codes:
            mysqldb.import_data(
                "年金计划",
                pd.concat(new_annuity_codes).drop_duplicates(
                    subset=["年金计划号"], keep="last"
                ),
            )
        if new_portfolio_codes:
            mysqldb.import_data(
                "组合计划",
                pd.concat(new_portfolio_codes).drop_duplicates(
                    subset=["组合代码"], keep="last"
                ),
            )


def import_company_id_mapping(start_time=None):
    """
    导入公司 ID 映射，将当前和曾用名合并后写入 MySQL 数据库。

    :param start_time: datetime, 可选。指定从何时开始获取 MongoDB 中的记录。
    """
    if not start_time:
        # 设置为当天午夜（UTC）
        start_time = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    # 创建 MongoDBManager 实例
    mongo_manager = MongoDBManager()

    try:
        # 获取最新的 current_mapping 数据
        current_mapping = mongo_manager.get_latest_unique_data(
            collection_name="base_info",
            unique_fields=["company_id", "company_full_name"],
            start_time=start_time,
        )

        if current_mapping.empty:
            logger.warning("No current mapping data found.")
        else:
            # 保留与 former_mapping 结构一致的列
            current_mapping = current_mapping[
                ["company_id", "company_full_name", "unite_code"]
            ]
            # 重命名列并添加类型标识
            current_mapping.rename(
                columns={"company_full_name": "company_name"}, inplace=True
            )
            current_mapping["type"] = "current"

        # 获取 former_mapping 并展开数组字段
        former_mapping = mongo_manager.merge_fields_to_dataframe(
            collection_name="base_info",
            fields=["company_id", "unite_code", "company_former_name"],
            expand_array=True,  # 垂直展开
            start_time=start_time,
        )

        if former_mapping.empty:
            logger.warning("No former mapping data found.")
        else:
            former_mapping.rename(
                columns={"company_former_name": "company_name"}, inplace=True
            )
            former_mapping["type"] = "former"

        # 合并 DataFrame
        company_id_mapping = pd.concat(
            [former_mapping, current_mapping], ignore_index=True
        )

        if company_id_mapping.empty:
            logger.info("No data to import after concatenation.")
            return

        # 删除重复数据
        company_id_mapping.drop_duplicates(
            subset=["company_id", "company_name"], keep="last", inplace=True
        )

        # 删除 'company_name' 为空的行
        company_id_mapping.dropna(subset=["company_name"], inplace=True)

        # 将结果插入 MySQL 数据库
        with MySqlDBManager(database="enterprise") as mysqldb:
            mysqldb.import_data_with_ignore("company_id_mapping", company_id_mapping)

        logger.info(
            f"Successfully imported {len(company_id_mapping)} records into MySQL."
        )

    except Exception as e:
        logger.error(f"An error occurred during import: {e}")
        raise


def sync_mongo_to_mysql(
    mongo_table_name: str,
    mysql_table_name: str,
    mongo_db: str = "enterprise_data",
    mysql_db: str = "enterprise",
    unique_fields: List[str] = None,
    drop_columns: List[str] = None,
    expand_array: bool = False,
    start_time: datetime = None,
) -> None:
    """
    从MongoDB同步数据到MySQL数据库的通用函数。

    参数:
    - mongo_table_name (str): MongoDB集合名称
    - mysql_table_name (str): MySQL表名
    - unique_fields (list, optional): MongoDB中唯一标识字段列表，用于去重。
    - drop_columns (list, optional): 需要从DataFrame中删除的列。
    - expand_array (bool, optional): 是否横向展开MongoDB中的数组字段，默认为False。
    - start_time (datetime, optional): 起始时间，用于过滤MongoDB的数据。
    """
    if not start_time:
        # 设置为当天午夜（UTC）
        start_time = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    mongodb = MongoDBManager(database_name=mongo_db)

    try:
        # 从MongoDB获取数据
        if unique_fields:
            # 获取最新唯一数据
            data = mongodb.get_latest_unique_data(
                collection_name=mongo_table_name,
                unique_fields=unique_fields,
                start_time=start_time,
            )
        else:
            # 普通数据处理
            data = mongodb.merge_fields_to_dataframe(
                collection_name=mongo_table_name,
                fields=mongodb.get_collection_fields(mongo_table_name),
                expand_array=expand_array,
                start_time=start_time,
            )

        if data.empty:
            logger.info(
                f"No new data to sync from MongoDB '{mongo_table_name}' since {start_time}."
            )
            return

        # 删除指定的列（如果存在）
        if drop_columns:
            existing_columns = [col for col in drop_columns if col in data.columns]
            if existing_columns:
                data.drop(columns=existing_columns, inplace=True)

        # 填充 companyId 列的缺失值
        if "companyId" in data.columns:
            if data["companyId"].isnull().any():
                data["companyId"].ffill(inplace=True)

        # 向MySQL写入数据
        with MySqlDBManager(database=mysql_db) as mysqldb:
            if mysql_table_name == "business_info":
                if "updateTime" in data.columns:
                    data["updateTime"] = pd.to_datetime(
                        data["updateTime"], errors="coerce"
                    )
                else:
                    logger.warning("Column 'updateTime' not found in data.")
                # 将 'updateTime' 列转换为日期格式 (格式为 yyyy-mm-dd)
                data["updateTime"] = pd.to_datetime(
                    data["updateTime"], format="%Y-%m-%d"
                )
                mysqldb.import_data_with_update_on_conflict(
                    mysql_table_name, data, "updateTime"
                )
            else:
                mysqldb.import_data_with_ignore(mysql_table_name, data)

        logger.info(
            f"Data synced from MongoDB '{mongo_table_name}' to MySQL '{mysql_table_name}' successfully."
        )

    except Exception as e:
        logger.error(
            f"Error syncing data from MongoDB '{mongo_table_name}' to MySQL '{mysql_table_name}': {e}"
        )
        raise


def sync_enterprise_data(start_time: datetime = None):
    if not start_time:
        # 设置为当天午夜（UTC）
        start_time = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    sync_mongo_to_mysql(
        "eqc_search_result",
        "eqc_search_result",
        unique_fields=["key_word"],
        start_time=start_time,
    )
    sync_mongo_to_mysql(
        "base_info",
        "base_info",
        start_time=start_time,
        drop_columns=[
            "highlightCode",
            "highlight_content",
            "highlight_code",
            "nameHighlight",
        ],
    )
    sync_mongo_to_mysql("business_info", "business_info", start_time=start_time)
    sync_mongo_to_mysql("biz_label", "biz_label", start_time=start_time)
    import_company_id_mapping(start_time=start_time)


def update_company_id():
    with MySqlDBManager(database="config") as mysqldb:
        tables = pd.read_sql("SELECT * FROM config.annuity_mapping;", mysqldb.engine)
        tables = tables[~pd.isna(tables["customer_based_on_field"])]
        handlers = tables.to_dict(orient="records")

        # 定义 SQL 更新模板
        sql_templates = {
            "sql1": """
                UPDATE {database}.`{table}` a
                INNER JOIN mapping.`年金计划` b
                ON a.`{plan_code}` = b.`年金计划号`
                SET a.company_id = b.company_id
                WHERE 
                    a.company_id IS NULL
                    AND b.`计划类型` = '单一计划'
                    AND b.`年金计划号` NOT LIKE 'AN%';
            """,
            "sql2": """
                UPDATE {database}.`{table}` t1
                INNER JOIN (
                    SELECT DISTINCT `年金账户号`, company_id
                    FROM enterprise.annuity_account_mapping
                ) t2
                ON t1.`{annuity_account}` = t2.`年金账户号`
                SET t1.company_id = t2.company_id
                WHERE 
                    t1.company_id IS NULL;
            """,
            "sql3": """
                UPDATE {database}.`{table}` t1
                SET t1.company_id = 
                    CASE
                        WHEN t1.`{plan_code}` IN ('FP0001', 'FP0002') THEN '614810477'
                        WHEN t1.`{plan_code}` IN ('FP0003') THEN '610081428'
                        WHEN t1.`{plan_code}` IN ('P0809') THEN '608349737'
                        WHEN t1.`{plan_code}` IN ('SC002') THEN '604809109'
                        WHEN t1.`{plan_code}` IN ('SC007') THEN '602790403'
                        WHEN t1.`{plan_code}` IN ('XNP466', 'XNP467') THEN '603968573'
                        WHEN t1.`{plan_code}` IN ('XNP596') THEN '601038164'
                        ELSE '600866980'
                    END
                WHERE 
                    t1.company_id IS NULL 
                    AND (t1.`{company_name}` IS NULL OR t1.`{company_name}` = '');
            """,
            "sql4": """
                UPDATE {database}.`{table}` a
                INNER JOIN enterprise.company_id_mapping b
                ON a.`{company_name}` = b.company_name
                SET a.company_id = b.company_id
                WHERE a.company_id IS NULL;
            """,
            "sql5": """
                UPDATE {database}.`{table}` t1
                INNER JOIN (
                    SELECT DISTINCT `年金账户名`, company_id
                    FROM enterprise.annuity_account_mapping
                ) t2
                ON t1.`{company_name}` = t2.`年金账户名`
                SET t1.company_id = t2.company_id
                WHERE t1.company_id IS NULL;
            """,
        }

        for handler in handlers:
            update_fields = handler["customer_based_on_field"]
            field_list = update_fields.split("+")
            try:
                mysqldb.conn.begin()  # 开始事务
                if len(field_list) == 3:
                    # 执行 sql1, sql2, sql3, sql4, sql5
                    # sql1
                    sql1 = sql_templates["sql1"].format(
                        database=handler["target_database"],
                        table=handler["target_table"],
                        plan_code=field_list[0],
                    )
                    mysqldb.cursor.execute(sql1)

                    # sql2
                    sql2 = sql_templates["sql2"].format(
                        database=handler["target_database"],
                        table=handler["target_table"],
                        annuity_account=field_list[1],
                    )
                    mysqldb.cursor.execute(sql2)

                    # sql3
                    sql3 = sql_templates["sql3"].format(
                        database=handler["target_database"],
                        table=handler["target_table"],
                        plan_code=field_list[0],
                        company_name=field_list[2],
                    )
                    mysqldb.cursor.execute(sql3)

                    # sql4
                    sql4 = sql_templates["sql4"].format(
                        database=handler["target_database"],
                        table=handler["target_table"],
                        company_name=field_list[2],
                    )
                    mysqldb.cursor.execute(sql4)

                    # sql5
                    sql5 = sql_templates["sql5"].format(
                        database=handler["target_database"],
                        table=handler["target_table"],
                        company_name=field_list[2],
                    )
                    mysqldb.cursor.execute(sql5)

                elif len(field_list) == 2:
                    # 执行 sql1, sql3, sql4, sql5
                    # sql1
                    sql1 = sql_templates["sql1"].format(
                        database=handler["target_database"],
                        table=handler["target_table"],
                        plan_code=field_list[0],
                    )
                    mysqldb.cursor.execute(sql1)

                    # sql3
                    sql3 = sql_templates["sql3"].format(
                        database=handler["target_database"],
                        table=handler["target_table"],
                        plan_code=field_list[0],
                        company_name=field_list[1],
                    )
                    mysqldb.cursor.execute(sql3)

                    # sql4
                    sql4 = sql_templates["sql4"].format(
                        database=handler["target_database"],
                        table=handler["target_table"],
                        company_name=field_list[1],
                    )
                    mysqldb.cursor.execute(sql4)

                    # sql5
                    sql5 = sql_templates["sql5"].format(
                        database=handler["target_database"],
                        table=handler["target_table"],
                        company_name=field_list[1],
                    )
                    mysqldb.cursor.execute(sql5)

                elif len(field_list) == 1:
                    # 执行 sql4, sql5
                    # sql4
                    sql4 = sql_templates["sql4"].format(
                        database=handler["target_database"],
                        table=handler["target_table"],
                        company_name=field_list[0],
                    )
                    mysqldb.cursor.execute(sql4)

                    # sql5
                    sql5 = sql_templates["sql5"].format(
                        database=handler["target_database"],
                        table=handler["target_table"],
                        company_name=field_list[0],
                    )
                    mysqldb.cursor.execute(sql5)
                else:
                    # 如果字段列表长度不符合预期，可以选择记录日志或抛出异常
                    print(f"Unexpected number of fields: {len(field_list)}")
                mysqldb.conn.commit()  # 提交事务
            except Exception as e:
                mysqldb.conn.rollback()  # 回滚事务
                print(f"Error occurred: {e}")


if __name__ == "__main__":
    selected_sub_process = int(input("Please enter an integer: "))

    # region >> 预处理年金计划信息
    if selected_sub_process == 1:
        from config_manager.config_manager import config
        from common_utils.common_utils import get_valid_files

        valid_files = get_valid_files(config.MONTHLY_SOURCE, exclude_keyword="已写入")
        prefix_processing(valid_files)
    # endregion

    # region >> 数据库信息同步
    if selected_sub_process == 2:
        sync_mongo_to_mysql(
            mongo_table_name="bid_info",
            mysql_table_name="bid_info",
            unique_fields=["data_url"],
            expand_array=False,
            start_time=datetime(2024, 10, 29, 0, 0),
        )
    # endregion
