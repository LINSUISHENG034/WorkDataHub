import pandas as pd

from sqlalchemy import text
from textwrap import dedent

from config_manager.config_manager import config
from database_operations.mysql_ops import MySqlDBManager


# 业务类型代码映射
def get_business_type_mapping(database_name="mapping", reverse=False):
    with MySqlDBManager(database=database_name) as mysqldb:
        cursor = mysqldb.cursor
        try:
            cursor.execute("SELECT 产品线, 产品线代码 FROM 产品线")
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return (
        {row[1]: row[0] for row in rows}
        if reverse
        else {row[0]: row[1] for row in rows}
    )


BUSINESS_TYPE_CODE_MAPPING = get_business_type_mapping()


# 产品明细映射（与业务类型代码映射存在重叠）
def get_product_id_mapping(database_name="mapping", reverse=False):
    with MySqlDBManager(database=database_name) as mysqldb:
        cursor = mysqldb.cursor
        try:
            cursor.execute("SELECT 产品明细, 产品ID FROM 产品明细")
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return (
        {row[1]: row[0] for row in rows}
        if reverse
        else {row[0]: row[1] for row in rows}
    )


PRODUCT_ID_MAPPING = get_product_id_mapping()


# 利润指标代码映射
def get_profit_metrics_mapping(database_name="mapping", reverse=False):
    with MySqlDBManager(database=database_name) as mysqldb:
        cursor = mysqldb.cursor
        try:
            cursor.execute("SELECT 指标名称, 指标编码 FROM 利润指标")
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return (
        {row[1]: row[0] for row in rows}
        if reverse
        else {row[0]: row[1] for row in rows}
    )


PROFIT_METRICS_MAPPING = get_profit_metrics_mapping()


def get_data_handler_mapping(
    database_name: str = "config", update_frequency: str = "daily"
):
    update_frequency = (
        update_frequency if update_frequency in ["daily", "monthly"] else "%"
    )
    with MySqlDBManager(database=database_name) as mysqldb:
        select_statement = f"""
            SELECT keyword, cleaner_class, target_database, target_table, update_based_on_field
            FROM {config.DATA_HANDLER_MAPPING} 
            WHERE is_database_created=1 AND is_cleaner_class_created=1 AND update_frequency LIKE '%{update_frequency}%';
        """
        df = pd.read_sql(sql=text(select_statement), con=mysqldb.engine)
    return df


# 默认组合代码设定
DEFAULT_PORTFOLIO_CODE_MAPPING = {
    "集合计划": "QTAN001",
    "单一计划": "QTAN002",
    "职业年金": "QTAN003",
}


def get_default_plan_code_mapping():
    with MySqlDBManager(database="mapping") as mysqldb:
        cursor = mysqldb.cursor
        cursor.execute(
            f""" SELECT 年金计划号, 组合代码 FROM 组合计划 WHERE 组合状态 != "虚拟"; """
        )
        rows = cursor.fetchall()

        mapping = {row[1]: row[0] for row in rows}

    return mapping


DEFAULT_PLAN_CODE_MAPPING = get_default_plan_code_mapping()


def get_company_branch_mapping(database_name="mapping", reverse=False):
    with MySqlDBManager(database=database_name) as mysqldb:
        cursor = mysqldb.cursor
        try:
            cursor.execute("SELECT 机构, 机构代码 FROM 组织架构")
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return (
        {row[1]: row[0] for row in rows}
        if reverse
        else {row[0]: row[1] for row in rows}
    )


# 二级机构代码映射：增加调整
company_branch_dic = get_company_branch_mapping()
company_branch_dic.update(
    {
        "内蒙": "G31",
        "战略": "G37",
        "中国": "G37",
        "济南": "G21",
        "北京其他": "G37",
        "北分": "G37",
    }
)
COMPANY_BRANCH_MAPPING = company_branch_dic


# 客户编号1
def get_company_id1_mapping(database_name="mapping", reverse=False):
    with MySqlDBManager(database=database_name) as mysqldb:
        cursor = mysqldb.cursor
        try:
            cursor.execute(
                dedent(r"""
                SELECT `年金计划号`, `company_id` FROM mapping.`年金计划` WHERE `计划类型`= '单一计划' AND `年金计划号` != 'AN002';
            """)
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return (
        {row[1]: row[0] for row in rows}
        if reverse
        else {row[0]: row[1] for row in rows}
    )


COMPANY_ID1_MAPPING = get_company_id1_mapping()


# 客户编号2
def get_company_id2_mapping(database_name="enterprise", reverse=False):
    with MySqlDBManager(database=database_name) as mysqldb:
        cursor = mysqldb.cursor
        try:
            cursor.execute(
                dedent(r"""
                SELECT DISTINCT `年金账户号`, `company_id` FROM `annuity_account_mapping` WHERE `年金账户号` NOT LIKE 'GM%';
            """)
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return (
        {row[1]: row[0] for row in rows}
        if reverse
        else {row[0]: row[1] for row in rows}
    )


COMPANY_ID2_MAPPING = get_company_id2_mapping()

COMPANY_ID3_MAPPING = {
    "FP0001": "614810477",
    "FP0002": "614810477",
    "FP0003": "610081428",
    "P0809": "608349737",
    "SC002": "604809109",
    "SC007": "602790403",
    "XNP466": "603968573",
    "XNP467": "603968573",
    "XNP596": "601038164",
}


# 客户编号4
def get_company_id4_mapping(database_name="enterprise", reverse=False):
    with MySqlDBManager(database=database_name) as mysqldb:
        cursor = mysqldb.cursor
        try:
            cursor.execute(
                dedent(r"""
                SELECT DISTINCT `company_name`, `company_id` FROM `company_id_mapping`;
            """)
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return (
        {row[1]: row[0] for row in rows}
        if reverse
        else {row[0]: row[1] for row in rows}
    )


COMPANY_ID4_MAPPING = get_company_id4_mapping()


# 客户编号5（修正匹配逻辑）
def get_company_id5_mapping(database_name="business", reverse=False):
    with MySqlDBManager(database=database_name) as mysqldb:
        cursor = mysqldb.cursor
        try:
            cursor.execute(
                dedent(r"""
                SELECT DISTINCT `年金账户名`, `company_id` FROM `规模明细` WHERE `company_id` IS NOT NULL;
            """)
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return (
        {row[1]: row[0] for row in rows}
        if reverse
        else {row[0]: row[1] for row in rows}
    )


COMPANY_ID5_MAPPING = get_company_id5_mapping()


if __name__ == "__main__":
    print(COMPANY_ID2_MAPPING)
