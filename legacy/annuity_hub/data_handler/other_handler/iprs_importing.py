import numpy as np
import pandas as pd

from common_utils.common_utils import get_valid_files
from database_operations.mysql_ops import MySqlDBManager


if __name__ == '__main__':
    path = r'D:\Share\DATABASE\IPRS\承保清单\2024\承保口径'
    files = get_valid_files(path)
    with MySqlDBManager(database='iprs') as mysqldb:
        for file in files:
            df = mysqldb.read_data_from_excel(str(file))

            # Replace the /_x001B_ in columns
            df.replace({
                '条形码': {
                    '_x001B_': '',
                    '_x0001_': '',
                    '\x1b': '',
                    '\x01': ''
                },
                '保单联系人办公电话': {
                    '_x001B_': '',
                    '_x0001_': '',
                    '\x1b': '',
                    '\x01': ''
                },
                '保单联系人联系电话': {
                    '_x001B_': '',
                    '_x0001_': '',
                    '\x1b': '',
                    '\x01': ''
                }
            }, regex=True, inplace=True)

            # 检查 '投保性质' 列是否存在，如果不存在则创建
            if '投保性质' not in df.columns:
                df['投保性质'] = np.nan

            # 现在安全地进行操作
            df['投保性质'] = np.where(
                df['投保性质'].notnull() & df['投保性质'].ne(""),
                df['投保性质'],
                np.where(df['保单号'].str.contains("00A"), "个人", "团体")
            )

            # 替换原有报表中出单系统和累计保费字段
            # df.rename(columns={'出单系统': '一级出单系统', '累计保费': '保费收入'}, inplace=True)

            # 安全地删除旧列，即使它们不存在也不会报错
            # df.drop(columns=['出单系统', '累计保费'], errors='ignore', inplace=True)

            # 更新套餐代码
            conditions = [
                df['套餐代码'].notnull() & df['套餐代码'].ne(""),  # 套餐代码不为空
                df['套餐名称'].eq("深圳重特大疾病保险") | df['业务大类'].eq("笼子外非大病"),  # 深圳重疾险对应组合险代码P0556SZ99
                df['主险代码'].isin(["P0782", "P078201"]),  # 个账产品六年期组合险代码P0782SZ99
                df['主险代码'].isin(["P0783", "P078301"]),  # 个账产品一年期组合险代码P0783SZ99
                df['险种分类'].isin(["一年以上定期", "终身"]) | df['业务大类'].eq("长险"),  # 长险业务对应组合险代码P0990SZ00
                df['业务大类'].eq("学生险"),  # 学生险对应组合险代码P1151SZ00
                df['业务大类'].eq("口子业务"),  # 口子业务对应组合险代码P1125SZ00
                df['业务大类'].eq("在售自助卡"),  # 在售自助卡对应组合险代码PACSZ0000
                df['投保性质'].eq("团体"),  # 团体业务默认组合险代码P1445SZ00
                df['投保性质'].eq("个人")  # 个人业务默认组合险代码P1125SZ00
            ]
            choices = [
                df['套餐代码'],  # 套餐代码不为空
                "P0556SZ99",  # 深圳重疾险组合险代码
                "P0782SZ99",  # 个账产品六年期组合险代码
                "P0783SZ99",  # 个账产品一年期组合险代码
                "P0990SZ00",  # 长险业务组合险代码
                "P1151SZ00",  # 学生险组合险代码
                "P1125SZ00",  # 口子业务组合险代码
                "PACSZ0000",  # 在售自助卡对应组合险代码
                "P1445SZ00",  # 团体业务默认组合险代码
                "P1125SZ00"  # 个人业务默认组合险代码
            ]
            df['套餐代码'] = np.select(conditions, choices, default="P1445SZ00")

            # Rename columns
            df.rename(columns={
                "主招揽业务员姓名": "主揽业务员姓名",
                "联系业务姓名": "联系业务员姓名",
                "联系业务代码": "联系业务员代码",
                "他证件号码": "其他证件号码"
            }, inplace=True)

            # 向量化字符串操作，简单且更有效率
            df['投保人名称'] = df['投保人名称'].str.replace("(", "（").str.replace(")", "）")

            # Instead of dropping and then concatenating, directly select the rows
            invalid_gp_mask = ~df['保单状态'].isin(["缴清", "缴费有效"])
            # Instead of using append, use concat
            df = pd.concat([df[invalid_gp_mask], df[~invalid_gp_mask]]).drop_duplicates(subset='保单号')

            mysqldb.import_data_with_update_on_conflict(
                table_name='承保清单_2024',
                data=df,
                update_field='承保日期'
            )

            print(f'''导入{str(file)}''')
