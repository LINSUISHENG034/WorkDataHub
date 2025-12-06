import pandas as pd

from pathlib import Path
from textwrap import dedent

from database_operations.mysql_ops import MySqlDBManager
from common_utils.common_utils import get_valid_files


TEMPLATE_FILE_PATH = r"D:\Share\PAFcloud\年金考核\指标库\【上载】企划指标库梳理.xlsx"


def sql_memos():
    # 更新企年投资新增组合
    sql1 = dedent("""
        CREATE TABLE customer.`企年投资新增组合` AS
        SELECT A.`组合编号`, A.`组合名称`, A.`投资风格`, A.`年金计划号`, A.`运作开始日`, A.`受托人`
        FROM business.`组合业绩` A LEFT JOIN customer.`企年投资已客` B
        ON A.`年金计划号` = B.`年金计划号`
        WHERE ISNULL(B.`年金计划号`) AND A.`运作开始日` >= '2023-12-01';
    """)

    # 创建职年投资已客清单
    sql2 = dedent("""
        CREATE TABLE customer.`职年投资已客` AS (
            SELECT A.`年金计划号`, A.`年金计划全称`, A.`计划类型`, A.`管理资格`, A.`客户名称`, null AS '备注', SUM(B.`期初资产规模`) AS '23年11月底资产规模'
            FROM mapping.`年金计划` A LEFT JOIN business.`规模明细` B
            ON A.`年金计划号` = B.`计划代码`
            WHERE (A.`管理资格` LIKE '%职年投资%' OR ISNULL(A.`管理资格`)) AND (B.`业务类型` = '职年投资' AND B.`月度` = '2023-12-01')
            GROUP BY A.`年金计划号`, A.`年金计划全称`, A.`计划类型`, A.`管理资格`
            HAVING SUM(B.`期初资产规模`) > 0
        );
    """)

    # 更新NO_年金计划号
    sql3 = dedent("""
        -- 初始化一个用户变量
        SET @row_number := 0;
        
        -- 更新`年金计划`表，为`NO_年金计划`设置行号
        UPDATE `年金计划`
        JOIN (
            SELECT `年金计划号`, (@row_number:=@row_number + 1) AS row_num
            FROM `年金计划`
            ORDER BY `23年11月底资产规模` DESC  -- 根据资产规模降序排序
        ) AS ranked ON `年金计划`.`年金计划号` = ranked.`年金计划号`
        SET `年金计划`.`NO_年金计划` = ranked.row_num;
    """)

    # 更新年金计划号管理资格
    sql4 = dedent("""
        UPDATE mapping.`年金计划` Renewal INNER JOIN (
            SELECT 
                A.`年金计划号`,  
                GROUP_CONCAT(DISTINCT B.`业务类型` ORDER BY B.`业务类型` SEPARATOR '+') AS `管理资格`
            FROM 
                mapping.`年金计划` A 
            INNER JOIN 
                business.`规模明细` B
            ON 
                A.`年金计划号` = B.`计划代码`
            WHERE 
                ISNULL(A.`管理资格`) 
            GROUP BY 
                A.`年金计划号`
        ) Result
        ON Renewal.`年金计划号` = Result.`年金计划号`
        SET Renewal.`管理资格` = Result.`管理资格`
        WHERE ISNULL(Renewal.`管理资格`);
    """)

    # 为所有年金计划创建默认虚拟组合
    sql5 = dedent("""
        INSERT INTO `组合计划`(年金计划号, 组合代码, 组合名称, 组合类型, 组合状态, 备注)
        SELECT 
            `年金计划`.`年金计划号` AS '年金计划号', 
            CONCAT('QT', `年金计划`.`年金计划号`) AS '组合代码', 
            '默认组合-虚拟' AS '组合名称',
            IF(`年金计划`.`计划类型` = '单一计划', '单一', '集合') AS '组合类型',
            '虚拟' AS '组合状态',
            '自动写入' AS '备注'
        FROM `年金计划`
        WHERE `年金计划`.`年金计划号` NOT IN (
            SELECT `组合计划`.`年金计划号`
            FROM `组合计划`
            WHERE `组合计划`.`组合状态` = '虚拟');
    """)

    # 使用正则表达式替换组合代码首字母F
    sql6 = dedent("""
        UPDATE customer.`企年投资估值流失` A
        SET A.`组合代码` = REGEXP_REPLACE(A.`组合代码`, '^F', '')
        WHERE A.`组合代码` LIKE 'F%';
    """)

    # 更新企年受托战客名单
    sql7 = dedent("""
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
          LEFT JOIN customer.`企年受托战客` ON customer.`企年受托中标`.`年金计划号` = customer.`企年受托战客`.`年金计划号` 
        WHERE 
          customer.`企年受托中标`.`年金计划号` NOT IN ('AN001', 'AN002') 
          AND ISNULL(
            customer.`企年受托战客`.`年金计划号`
          );
    """)

    # 集合分拆数据准确性校验
    sql8 = dedent("""
        SELECT 
            new_tab.`月度`, 
            new_tab.`业务类型`, 
            new_tab.`计划代码`, 
            new_tab.`组合代码`, 
            new_tab.`机构代码`,
            new_tab.`期初资产规模` AS `新_期初资产规模`, 
            new_tab.`期末资产规模` AS `新_期末资产规模`,
            new_tab.`供款` AS `新_供款`,
            new_tab.`流失` AS `新_流失`, 
            new_tab.`待遇支付` AS `新_待遇支付`,
            new_tab.`投资收益` AS `新_投资收益`,
            old_tab.`期初资产规模` AS `原_期初资产规模`,  
            old_tab.`期末资产规模` AS `原_期末资产规模`,
            old_tab.`供款` AS `原_供款`,
            old_tab.`流失` AS `原_流失`,
            old_tab.`待遇支付` AS `原_待遇支付`,
            old_tab.`投资收益` AS `原_投资收益`
        FROM (
            SELECT 
                `月度`, 
                `业务类型`, 
                `计划代码`, 
                `组合代码`, 
                `机构代码`,
                SUM(`期初资产规模`) AS `期初资产规模`, 
                SUM(`期末资产规模`) AS `期末资产规模`, 
                SUM(`供款`) AS `供款`,
                SUM(`流失`) AS `流失`, 
                SUM(`待遇支付`) AS `待遇支付`, 
                SUM(`投资收益`) AS `投资收益`
            FROM business.`集合计划拆分`
            GROUP BY `月度`, `业务类型`, `计划代码`, `组合代码`, `机构代码`
        ) AS new_tab
        INNER JOIN (
            SELECT 
                `月度`, 
                `业务类型`, 
                `计划代码`, 
                `组合代码`, 
                `机构代码`,
                SUM(`期初资产规模`) AS `期初资产规模`, 
                SUM(`期末资产规模`) AS `期末资产规模`, 
                SUM(`供款`) AS `供款`,
                SUM(`流失`) AS `流失`, 
                SUM(`待遇支付`) AS `待遇支付`, 
                SUM(`投资收益`) AS `投资收益`
            FROM business.`规模明细`
            GROUP BY `月度`, `业务类型`, `计划代码`, `组合代码`, `机构代码`
        ) AS old_tab
        ON new_tab.`月度` = old_tab.`月度` 
           AND new_tab.`业务类型` = old_tab.`业务类型` 
           AND new_tab.`计划代码` = old_tab.`计划代码` 
           AND new_tab.`组合代码` = old_tab.`组合代码` 
           AND new_tab.`机构代码` = old_tab.`机构代码`;
        WHERE 
            ROUND(new_tab.`期初资产规模` - old_tab.`期初资产规模`, 4) != 0
            OR ROUND(new_tab.`期初资产规模` - old_tab.`期初资产规模`, 4) != 0
            OR ROUND(new_tab.`期末资产规模` - old_tab.`期末资产规模`, 4) != 0
            OR ROUND(new_tab.`供款` - old_tab.`供款`, 4) != 0
            OR ROUND(new_tab.`流失` - old_tab.`流失`, 4) != 0
            OR ROUND(new_tab.`待遇支付` - old_tab.`待遇支付`, 4) != 0
            OR ROUND(new_tab.`投资收益` - old_tab.`投资收益`, 4) != 0;
    """)

    # XXX
    sqlx = dedent("""
    """)


def get_upload_template_info():
    file_path = Path(r"D:\Share\PAFcloud\年金考核\指标库\上载模板")
    saved_path = TEMPLATE_FILE_PATH

    tab_info_dic = {
        file.stem: "/".join(
            pd.read_excel(file, sheet_name=0, header=0, dtype=str).columns
        )
        for file in file_path.glob("*.xlsx")
    }

    tab_info_df = pd.DataFrame.from_dict(tab_info_dic, orient="index", columns=["字段"])

    with pd.ExcelWriter(
        saved_path, engine="openpyxl", mode="a", if_sheet_exists="replace"
    ) as writer:
        tab_info_df.to_excel(writer, sheet_name="上载模板")


def create_upload_data(year_month):
    upload_template_df = pd.read_excel(
        TEMPLATE_FILE_PATH, sheet_name="上载模板", header=0, usecols=[1, 2, 3]
    )

    # 将 '上载模板' 列设置为索引并转换为字典
    upload_template_dic = upload_template_df.set_index("上载模板").to_dict(
        orient="index"
    )

    upload_metrics_df = pd.read_excel(
        TEMPLATE_FILE_PATH, sheet_name="上载指标", header=0
    )
    upload_metrics_df = upload_metrics_df[
        (upload_metrics_df["类型"] != "删除") & (upload_metrics_df["已上传"] == 0)
    ]

    # 读取组织架构表
    branch_df = pd.read_excel(
        TEMPLATE_FILE_PATH,
        sheet_name="组织架构",
        header=0,
        usecols=["机构", "年金中心", "战区", "机构代码"],
    )
    region_df = branch_df[["战区"]].drop_duplicates()

    upload_folder = Path(r"D:\Share\PAFcloud\年金考核\指标库\上载数据")

    def create_branch_data(
        row, org_structure_df, year_month, product_type, is_branch=True
    ):
        if row["上载表格"] == "METRICS_TEMPLATE_COST":
            columns = [
                "指标编码",
                "指标名称",
                "业务线",
                "年月",
                "费用科目",
                "机构",
                "属地",
                "战区",
                "数值（元）",
                "描述",
            ]
            template = {
                "业务线": product_type,
                "费用科目": "",
                "数值（元）": 0,
            }
        elif row["上载表格"] == "METRICS_TEMPLATE_MGT_FEE":
            columns = [
                "指标编码",
                "指标名称",
                "组合代码",
                "组合名称",
                "业绩报酬",
                "机构",
                "产品类别",
                "浮费年度",
                "年月",
                "描述",
            ]
            template = {
                "组合代码": "",
                "组合名称": "",
                "业绩报酬": 0,
                "产品类别": product_type,
                "浮费年度": "",
            }
        elif row["上载表格"] == "METRICS_TEMPLATE_RATE_CAT":
            columns = [
                "指标编码",
                "指标名称",
                "年月",
                "产品类别",
                "客户",
                "机构",
                "属地",
                "战区",
                "数值（%）",
                "描述",
            ]
            template = {
                "产品类别": product_type,
                "客户": "",
                "数值（%）": 0,
            }
        elif row["上载表格"] == "METRICS_TEMPLATE_SCALE":
            columns = [
                "指标编码",
                "指标名称",
                "业务线",
                "年月",
                "计划代码",
                "计划名称",
                "组合代码",
                "组合名称",
                "客户",
                "地区",
                "机构",
                "属地",
                "战区",
                "数值（元）",
                "描述",
            ]
            template = {
                "业务线": product_type,
                "计划代码": "",
                "计划名称": "",
                "组合代码": "",
                "组合名称": "",
                "客户": "",
                "地区": "",
                "数值（元）": 0,
            }
        else:
            print(f"Unexpected template type: {row['上载表格']}")
            return []

        virtual_data = []

        for _, org_row in org_structure_df.iterrows():
            data_row = {
                "指标编码": row["指标编码"],
                "指标名称": row["指标名称"],
                "年月": year_month,
                "机构": org_row["机构"] if is_branch else "",
                "属地": org_row["年金中心"] if is_branch else "",
                "战区": org_row["战区"],
                "描述": "",
            }
            data_row.update(template)
            virtual_data.append(data_row)

        return virtual_data, columns

    for _, row in upload_metrics_df.iterrows():
        upload_table = row["上载表格"]
        indicator_code = row["指标编码"]
        indicator_name = row["指标名称"]
        product_types = row["所属产品线"].split("/")  # 对"所属产品线"进行分割
        file_name = f"{upload_table}_{indicator_code}_{indicator_name}.xlsx"

        if upload_table in upload_template_dic:
            template_info = upload_template_dic[upload_table]
            sheet_name = template_info["表名"]

            all_virtual_data = []
            all_columns = None

            for product_type in product_types:
                if "区域" in indicator_name:
                    # 仅创建区域虚拟数据
                    virtual_data, columns = create_branch_data(
                        row, region_df, year_month, product_type, is_branch=False
                    )
                else:
                    virtual_data, columns = create_branch_data(
                        row, branch_df, year_month, product_type
                    )

                if all_columns is None:
                    all_columns = columns

                all_virtual_data.extend(virtual_data)

            template_df = pd.DataFrame(all_virtual_data, columns=all_columns)

            save_path = upload_folder / year_month / file_name
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
                template_df.to_excel(writer, sheet_name=sheet_name, index=False)

            print(f"Created file: {file_name}")
        else:
            print(f"Template for {upload_table} not found")


def merge_upload_files(period_time, folder_path, output_folder):
    folder_path = Path(folder_path)
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    combined_data = {
        "METRICS_TEMPLATE_COST": [],
        "METRICS_TEMPLATE_MGT_FEE": [],
        "METRICS_TEMPLATE_RATE_CAT": [],
        "METRICS_TEMPLATE_SCALE": [],
    }

    # 定义可能的前缀
    valid_prefixes = set(combined_data.keys())

    # 遍历文件夹中的所有文件
    for file in folder_path.glob("*.xlsx"):
        file_name = file.stem

        # 判断文件名的前缀
        upload_table = None
        for prefix in valid_prefixes:
            if file_name.startswith(prefix):
                upload_table = prefix
                break

        if upload_table is None:
            print(f"Skipping file with unexpected name format: {file_name}")
            continue

        df = pd.read_excel(file)
        combined_data[upload_table].append(df)

    # 保存合并后的文件
    for upload_table, dataframes in combined_data.items():
        if dataframes:  # 仅在有数据时才保存文件
            combined_df = pd.concat(dataframes, ignore_index=True)
            save_path = output_folder / f"{upload_table}_{period_time}.xlsx"
            with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
                combined_df.to_excel(writer, sheet_name="Combined", index=False)
            print(f"Created combined file: {save_path}")


if __name__ == "__main__":
    period_time = "202405"
    is_created = True
    if is_created:
        source_folder = rf"D:\Share\PAFcloud\年金考核\指标库\上载数据\{period_time}"
        destination_folder = (
            rf"D:\Share\PAFcloud\年金考核\指标库\上载数据\{period_time}\合并数据"
        )
        merge_upload_files(period_time, source_folder, destination_folder)
    else:
        create_upload_data(year_month=period_time)
