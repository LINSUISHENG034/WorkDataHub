# /common_utils/common_utils.py

import dateutil.parser as dp
import hashlib
import pandas as pd
import re

from datetime import datetime, date
from pathlib import Path

# 定义公司简称相关的正则表达式及其替换模式
ABB_FIXED_REG_FORMULAS = [
    (r"([一-龥]+)(\（[一-龥]+\）)?([一-龥]+)(\（[一-龥]+\）)?$", r"\1\3"),
    (r"([一-龥]+?)([^市]+)([一-龥]+\2)$", r"\1\2"),
    (r"^(?:(?:[^深多].+省)?(?:.+[^城超都博]市(?!政|场|部|集))?(?:.+[^海园社]区(?!块))?(?:.+街道)?)([\w一-龥 ]+?)", r"\1"),
    (
        (
            r"((?:加工|管理|日用品|商|批发|美容化妆品|配件)店|(?:回收|养老服务)?站|(?:建筑师|税务师|律师)?(?:事务|会)所|(?:总|分)?公司|"
            r"(?:批发|材料|维修|商)行|(?:管理|维修)中心|(?:经销|经营|制作|美容门诊)部|养老服务(?:站|社|中心))$"
        ),
        ""),
    (r"^(中国|北京|深圳|湖南|上海)?", ""),
    (r"(深圳代表处|工会委员会|再生资源回收站)$", ""),
    (r"((?:控股|股份|控股股份|企业)?有限(责任)?|(?:股份|技术)合作|综合|(?:集团)([一-龥]+)?有限)$", "")
]

ABB_INDUSTRY_REG_FORMULAS = [
    (r"(?:派遣|建设监理|自动化装备|智能装备|产品配送|知识产权|美容养生|美容中心|印刷器材|智能系统|体育发展|国际旅行)$", ""),
    (r"((?:教育|餐饮|艺术|国际|影视|托育娱教|体育|教育|国际|饮食|科技)?文化(?:传播|传媒|艺术|科技|管理|艺术培训|投资|产业|教育|创意|用品|娱乐)?(?:发展)?)$", ""),
    (r"((?:塑胶|五金|科技|精密|汽车|光)?电子(?:科技|科技发展|商务|技术|材料|产品|包装|材料|设备|制品|加工|五金|发展|塑胶|实业|工程|线材|产品|销售|开发)?(?:科技)?)$", ""),
    (r"((?:置业|股权|房?地产|酒店|教育|实业|科技|创业|医疗|国际|建设|管理|环保)?投资(?:发展|管理|咨询|顾问|基金|实业|服务|策划)?(?:管理)?)$", ""),
    (r"((?:塑胶|精密|模具|机械)?五金(?:塑胶|电器|模具|配件|机电|机械|建材|模具|设备|交电|饰品)?(?:制品|科技|加工|贸易|模具|实业)?)$", ""),
    (r"((?:企业|建筑|安全|健康)?(?:管理|教育|商务|技术|设计|财务|地产|财税|设计|科技|建筑|培训|顾问)?咨询(?:服务|管理|顾问)?)$", ""),
    (r"((?:建筑|设计|广告|工程|五金|消防|材料|玻璃|不锈钢|建材|园林)装饰(?:工程|设计|材料|服务|建筑|建材|五金)?(?:工程|设计)?)$", ""),
    (r"((?:艺术|形象|服装|空间|广告|室内|规划|模型|景观|印刷|勘测|图文|家具|工业|产品|装修)?设计(?:顾问|研究|服务|制作)?)$", ""),
    (r"(汽车(?:配件|维修|贸易|用品|租售|美容|租赁|科技|检测|技术|销售|装饰|养护)?(?:服务)?(?:中心|美容)?)$", ""),
    (r"((?:教育|科技|智能|金融|国际|网络|商务|汽车|投资)?信息(?:技术|科技|咨询|工程|系统)?(?:服务|发展)?)$", ""),
    (r"((?:纸品|印刷|首饰|环保|制品|塑胶|礼品|塑料)?包装(?:制品|材料|设计|科技|机械|印刷|纸品|技术|机械)?)$", ""),
    (r"(餐饮(?:管理|服务|文化|投资|连锁|娱乐|策划|发展|科技|实业|文化传播|投资发展|企业)?(?:管理|服务)?)$", ""),
    (r"((?:智能|电力|制冷|厨房|医疗|办公|印刷|工业|电气|电器|净化|数控|消防|厨具)?设备(?:租赁|安装)?)$", ""),
    (r"((?:金属|建筑|绝缘|印刷|环保|工业|光电|应用|胶粘|塑胶|复合|电工|广告)?材料(?:科技|技术|制品)?)$", ""),
    (r"((?:国际)?建筑(?:规划)?(?:设计|劳务|材料|科技|设备|机械|规划|加固)?(?:顾问|技术)?)$", ""),
    (r"((?:光电子|半导体|清洁|智能|创新|农业|电力|医疗|设备|电路)?科技(?:集团|发展|开发|服务)?)$", ""),
    (r"((?:设备|节能)?环保(?:科技|技术|通风|材料|服务|建材|产业|机电)?(?:服务|资源|设备)?)$", ""),
    (r"((?:模具|精密)?塑胶(?:模具|科技|包装|材料|颜料|技术|精密|玩具)?(?:制品|加工|贸易)?)$", ""),
    (r"((?:生态|建筑)?环境(?:科技|技术|艺术|建设|管理|综合|卫生|发展)?(?:设计|服务|发展)?)$", ""),
    (r"((?:企业|饮食|运营|策划|连锁|养生|资本|品牌|经营|项目|娱乐|资产)?管理(?:顾问|策划|发展)?)$", ""),
    (
        (
            r"((?:建设|建筑|设计|照明|环境|电力|环保|机电通信|科技|消防|园林|安装|智能|净化|技术|勘测|绿化|景观|防水|结构|装修|系统|机械|网络|交通|加固)?"
            r"(?:设备|劳务|绿化|安装|加固|艺术)?工程(?:技术|设计|服务|设备|咨询|建设|顾问|劳务|项目管理|机械|管理|科技|劳务|监理|机械设备|实业|项目)?)$"
        ),
        ""),
    (r"((?:国际|艺术|儿童|培训)?教育(?:科技|培训|发展|服务|管理|技术)?(?:中心|发展)?)$", ""),
    (r"((?:科技|环保|电器|发展|照明|汽车|纺织|印刷|电气|饮食)?实业(?:发展|科技|管理)?)$", ""),
    (r"((?:保安|技术|管理|销售|金融|美容|企业|饮食|保洁|产权|租赁|装卸)?服务(?:中心|管理))$", ""),
    (r"((?:数码)?(?:通信|通讯)(?:技术|科技|设备|服务|发展|器材|建设|配件|产品)?)$", ""),
    (r"((?:国际|产品|食品|设备|出口|科技|汽配|农产品|建材|服装)?贸易(?:发展|服务)?)$", ""),
    (r"(物业(?:管理|服务|发展|清洁|投资|顾问|配套|运营)?(?:管理|服务|顾问|发展)?)$", ""),
    (r"((?:母婴|国际)?健康(?:管理|科技|养生|服务|产业|美容)?(?:管理|服务)?)$", ""),
    (r"((?:珠宝|首饰)(?:首饰|科技|设计|管理|包装|实业)?(?:制品|设计)?)$", ""),
    (r"((?:精密|模具|印刷)?机械(?:设备|配件|科技|销售|加工|模具|租赁)?)$", ""),
    (r"((?:印刷|手袋|皮具|胶粘|不锈钢|玻璃|塑料|硅胶|塑胶)?制品(?:加工))$", ""),
    (r"((?:精密|橡胶)?模具(?:制品|配件|科技|钢材|加工|技术|维修|制造)?)$", ""),
    (r"((?:初级)?农副?产品(?:贸易|发展|批发|供应|加工|配送)?)$", ""),
    (r"(房?地产(?:经纪|开发|顾问|发展|代理|评估)?(?:服务)?)$", ""),
    (r"((?:环保|园林)?清洁(?:服务|管理|用品|服务)?(?:中心)?)$", ""),
    (r"((?:国际)?人力(?:资源|咨询)?(?:服务|管理|开发|顾问)?)$", ""),
    (r"((?:国际|食品|物流|生态)?供应链(?:管理|服务|科技|物流)?)$", ""),
    (r"((?:智能|安全|检测|电力|设备|电器)?技术(?:开发|发展)?)$", ""),
    (r"((?:电器|设备|配件|汽配)维修(?:服务|美容)?(?:中心)?)$", ""),
    (r"((?:企业)?(?:营销|形象|品牌|展览)?策划(?:顾问)?)$", ""),
    (r"(商业(?:运营|服务|发展|连锁|贸易|经营)?(?:管理)?)$", ""),
    (r"((?:通信)?网络(?:科技|技术|服务|通信|通讯|设备)?)$", ""),
    (r"((?:商务|国际|精品)?酒店(?:管理|用品|设备|设计)?)$", ""),
    (r"((?:新)?能源(?:技术|科技|汽车|电气|产品|管理)?)$", ""),
    (r"((?:消防)?机电(?:制冷|科技|技术)?(?:设备)?)$", ""),
    (r"((?:母婴)?家政(?:服务|清洁)?(?:中心|管理)?)$", ""),
    (r"((?:科技|国际)?物流(?:服务|发展|管理|设备)?)$", ""),
    (r"((?:家居|母婴|体育|宠物|运动|劳保|办公)?用品)$", ""),
    (r"((?:国际)?生物(?:科技|技术)?(?:发展)?)$", ""),
    (r"((?:智能)?照明(?:科技|电器|技术|设计)?)$", ""),
    (r"((?:国际)?货运(?:代理)?(?:服务)?)$", ""),
    (r"((?:宠物)?医疗(?:器械|美容|器材))$", ""),
    (r"(资源(?:服务|回收|管理|开发|科技)?)$", ""),
    (r"(再生资源(?:回收|贸易|服务|资源)?)$", ""),
    (r"(母婴(?:健康管理|健康|用品|护理))$", ""),
    (r"(数码(?:科技|技术|产品|电器)?)$", ""),
    (r"((?:艺术)?培训(?:中心|学校))$", ""),
    (r"(精密(?:科技|技术|设备|配件)?)$", ""),
    (r"(办公(?:用品|包装用品|设备))$", ""),
    (r"((?:自动|工业)化(?:设备|科技|技术)?)$", ""),
    (r"((?!创)新?技术(?:合作)?)$", ""),
    (r"(金属(?:制品|科技|回收)?)$", ""),
    (r"(光电(?:科技|技术|设备)?)$", ""),
    (r"(不锈钢(?:材料|制品|装饰|工程)?)$", ""),
    (r"(工艺(?:制品|礼品|厂)?)$", ""),
    (r"(基金(?:管理|销售)?)$", ""),
    (r"(橡胶(?:制品|科技)?)$", ""),
    (r"((?:农产品|产品)?配送)$", ""),
    (r"((?:生鲜|生活|百货)?超市)$", "")
]


# 提取简称
def abbreviate_company_name(company_name):
    abbreviation = company_name
    pilot_str = company_name
    for pattern, repl in ABB_FIXED_REG_FORMULAS:
        new_name = re.sub(pattern, repl, abbreviation)
        if new_name != abbreviation:  # 如果发生了替换，则更新简称
            abbreviation = new_name
        if len(new_name) <= 2:  # 如果替换后的名称太短，则停止替换
            break
    for pattern, repl in ABB_INDUSTRY_REG_FORMULAS:
        new_name = re.sub(pattern, repl, abbreviation)
        if new_name != abbreviation:  # 如果发生了替换，则更新简称
            abbreviation = new_name
            break
    if len(abbreviation) > 6:  # 如果简称过长，只保留前四个字符
        return abbreviation[:4]
    elif len(abbreviation) == 0:  # 如果替换后为空，取中间字段
        return pilot_str[:4]
    elif len(abbreviation) <= 2:  # 如果简称太短，尝试从原名称中提取四个字符
        start = pilot_str.find(abbreviation)
        return pilot_str[start:start + 4]
    return abbreviation  # 返回处理后的简称


def extract_date_from_filename(file_name: str):
    # 匹配 "xxxxxx_20230101.xxxx" 格式的日期
    match1 = re.search(r'_(\d{8})\.', file_name)
    if match1:
        return datetime.strptime(match1.group(1), '%Y%m%d').date()

    # 匹配 "xxxxxx_202301.xxxx" 格式的日期
    match2 = re.search(r'_(\d{6})\.', file_name)
    if match2:
        return datetime.strptime(match2.group(1), '%Y%m').date()

    return None


def get_valid_files(source_path: str, suffixes=None, exclude_keyword=None):
    source = Path(source_path)
    if suffixes:
        suffixes = set(suffixes)  # Convert to set for efficient look-up

    # Use a single list comprehension to filter files based on all conditions
    return [f for f in source.rglob('*') if f.is_file() and
            '~$' not in f.name and
            (suffixes is None or f.suffix in suffixes) and
            (exclude_keyword is None or exclude_keyword not in f.as_posix())]


def get_unique_values(data: pd.DataFrame, col_name: str, convert_to_year_month=False) -> list:
    """
    Extract unique values from a DataFrame column and optionally format date columns to year-month.

    Args:
    - data (pd.DataFrame): The source DataFrame.
    - col_name (str): The column name from which to extract unique values.
    - year_month (bool): Whether to convert date-like columns to 'year-month' format.

    Returns:
    - list: A list of unique values, possibly after formatting dates to 'year-month'.
    """
    if col_name not in data.columns:
        raise ValueError(f"'{col_name}' is not a column in the DataFrame.")

    try:
        unique_values = data[col_name].unique()
        if convert_to_year_month:
            # 将 unique_values 转换为 DatetimeIndex，然后转换为 Series
            unique_values = pd.Series(pd.to_datetime(unique_values, format='%Y-%m-%d'))
            # 转换为年月格式并去重
            unique_values = unique_values.dt.to_period('M').unique()
        return unique_values.astype(str).tolist()

    except Exception as e:
        print(f"Error extracting unique values: {e}")
        return []


def get_unique_combinations(data: pd.DataFrame, fields: list) -> pd.DataFrame:
    """
    获取多个字段的唯一组合。

    Args:
    - data (pd.DataFrame): 源数据集。
    - fields (list): 需要计算唯一组合的字段列表。

    Returns:
    - pd.DataFrame: 包含唯一组合的DataFrame。
    """
    if not all(field in data.columns for field in fields):
        raise ValueError(f"Some fields are not present in the DataFrame: {fields}")

    # 保持日期字段为标准的datetime格式
    for field in fields:
        if pd.api.types.is_datetime64_any_dtype(data[field]):
            data[field] = pd.to_datetime(data[field])

    return data[fields].drop_duplicates()


# 转换标准时间格式
def parse_to_standard_date(data):
    if isinstance(data, (date, datetime)):
        return data
    else:
        date_string = str(data)

    try:
        # Match YYYY年MM月 or YY年MM月 format
        if re.match(r'(\d{2}|\d{4})年\d{1,2}月$', date_string):
            return datetime.strptime(date_string + '1日', '%Y年%m月%d日')

        # Match YYYY年MM月DD日 or YY年MM月DD日 format
        elif re.match(r'(\d{2}|\d{4})年\d{1,2}月\d{1,2}日$', date_string):
            return datetime.strptime(date_string, '%Y年%m月%d日')

        # Match YYYYMMDD format
        elif re.match(r'\d{8}', date_string):
            return datetime.strptime(date_string, '%Y%m%d')

        # Match YYYYMM format
        elif re.match(r'\d{6}', date_string):
            return datetime.strptime(date_string + '01', '%Y%m%d')

        # Match YYYY-MM format
        elif re.match(r'\d{4}-\d{2}', date_string):
            return datetime.strptime(date_string + '-01', '%Y-%m-%d')

        # For any other date format
        else:
            return dp.parse(date_string)

    except (ValueError, TypeError):
        return data


# 去除多余空格并转换全角字符为半角字符
def normalize_name(name: str, to_fullwidth: bool = False) -> str:
    if not name:
        return ''

    # 去除多余空格
    name = re.sub(r'\s+', '', name)
    # 去除开头和结尾多余字符
    name = re.sub(r'^[\(\（][^\(\（\)\）]*[\)\）]|[\(\（][^\(\（\)\）]*[\)\）]$|-\w+$', '', name)

    if to_fullwidth:
        # 将半角字符转换为全角字符
        name = ''.join([chr(ord(char) + 0xFEE0) if 0x21 <= ord(char) <= 0x7E else char for char in name])
    else:
        # 将全角字符转换为半角字符
        name = ''.join([chr(ord(char) - 0xFEE0) if 0xFF01 <= ord(char) <= 0xFF5E else char for char in name])

    return name


# 使用哈希函数生成固定长度的编码(截取前14位)
def generate_unique_code(name: str, is_branch: bool = False) -> str:
    normalized_name = normalize_name(name)
    # 使用哈希函数生成固定长度的编码
    hash_code = hashlib.md5(normalized_name.encode()).hexdigest()

    # 截取前14位并加上前缀组成16位编码(集团前缀为GM, 子企业前缀为GC)
    if is_branch:
        unique_code = f"GC{hash_code[:14].upper()}"
    else:
        unique_code = f"GM{hash_code[:14].upper()}"

    return unique_code


# 文件名批量添加前缀
def add_prefix_to_files(files, prefix: str):
    for file in files:
        new_name = file.parent / (prefix + file.name)
        file.rename(new_name)


if __name__ == '__main__':
    # 示例使用
    names = ["(原)厦门市建设工程(原)施工图审查有限公司-已转出"]

    # 生成并打印企业编码
    codes = [normalize_name(name) for name in names]

    for name, code in zip(names, codes):
        print(f"Name: {name}, Code: {code}")
