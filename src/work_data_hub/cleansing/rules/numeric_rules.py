"""
可复用的数值类型清洗规则库。

解决了当前架构中 clean_decimal_fields 重复实现的问题，
提供统一、可配置的数值字段清洗解决方案。
"""

import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Optional, Union

from ..registry import RuleCategory, rule

# 字段精度配置 - 可以通过配置文件外部化
DEFAULT_PRECISION_CONFIG = {
    # 收益率类字段 - 高精度
    "return_rate": 6,
    "当期收益率": 6,
    "年化收益率": 6,
    # 金额类字段 - 标准精度
    "net_asset_value": 4,
    "fund_scale": 2,
    "期初资产规模": 4,
    "期末资产规模": 4,
    "供款": 4,
    "流失_含待遇支付": 4,
    "流失": 4,
    "待遇支付": 4,
    "投资收益": 4,
}

# 空值占位符 - 可配置
NULL_PLACEHOLDERS = {"", "-", "N/A", "无", "暂无", "null", "NULL", "None"}

# 货币符号 - 可扩展
CURRENCY_SYMBOLS = {"¥", "$", "￥", "€", "£", "₽"}


@rule(
    name="remove_currency_symbols",
    category=RuleCategory.STRING,
    description="移除货币符号和格式化字符",
)
def remove_currency_symbols(value: str) -> str:
    """
    移除货币符号和常见格式化字符

    Args:
        value: 包含货币符号的字符串

    Returns:
        清理后的字符串
    """
    if not isinstance(value, str):
        return value

    # 移除货币符号
    cleaned = value.strip()
    for symbol in CURRENCY_SYMBOLS:
        cleaned = cleaned.replace(symbol, "")

    # 移除千分位分隔符和空格
    cleaned = cleaned.replace(",", "").replace(" ", "")

    return cleaned


@rule(
    name="handle_percentage_conversion",
    category=RuleCategory.NUMERIC,
    description="处理百分比格式转换为小数",
)
def handle_percentage_conversion(value: Any, field_name: str = "") -> Union[float, str]:
    """
    处理百分比格式，转换为小数

    Args:
        value: 输入值
        field_name: 字段名，用于判断是否为收益率字段

    Returns:
        转换后的值
    """
    # Unicode 规范化处理全角字符
    if isinstance(value, str):
        value = unicodedata.normalize("NFKC", value)

    # 字符串百分比处理
    if isinstance(value, str) and "%" in value:
        try:
            numeric_part = value.replace("%", "").strip()
            return float(numeric_part) / 100.0
        except ValueError:
            raise ValueError(f"Invalid percentage format: {value}")

    # 数值百分比处理（针对收益率字段）
    if isinstance(value, (int, float)) and (
        "收益率" in field_name or "rate" in field_name.lower()
    ):
        if abs(value) > 1:  # 判断是否为百分比格式，支持负百分比
            return value / 100.0

    # 字符串数值的百分比处理（针对收益率字段）
    if isinstance(value, str) and (
        "收益率" in field_name or "rate" in field_name.lower()
    ):
        try:
            # 尝试将字符串转换为数值进行百分比判断
            numeric_value = float(value)
            if abs(numeric_value) > 1:  # 判断是否为百分比格式，支持负百分比
                return numeric_value / 100.0
        except (ValueError, TypeError):
            # 如果转换失败，继续返回原值
            pass

    return value


@rule(
    name="standardize_null_values",
    category=RuleCategory.VALIDATION,
    description="标准化空值表示",
)
def standardize_null_values(value: Any) -> Optional[Any]:
    """
    标准化各种空值表示方式

    Args:
        value: 输入值

    Returns:
        标准化后的值，空值返回None
    """
    if value is None:
        return None

    if isinstance(value, str) and value.strip() in NULL_PLACEHOLDERS:
        return None

    return value


@rule(
    name="decimal_quantization",
    category=RuleCategory.NUMERIC,
    description="Decimal字段精度量化处理",
)
def decimal_quantization(
    value: Any,
    field_name: str = "",
    precision: Optional[int] = None,
    precision_config: Optional[Dict[str, int]] = None,
) -> Optional[Decimal]:
    """
    统一的Decimal字段精度量化处理

    这个函数整合了原来在两个domain中重复的clean_decimal_fields逻辑

    Args:
        value: 输入值
        field_name: 字段名，用于查找精度配置
        precision: 显式指定的精度，优先级最高
        precision_config: 字段精度配置字典

    Returns:
        量化后的Decimal值，无效值返回None
    """
    if value is None:
        return None

    # 使用提供的配置或默认配置
    config = precision_config or DEFAULT_PRECISION_CONFIG

    # 确定精度
    target_precision = precision or config.get(field_name, 4)  # 默认4位小数

    try:
        # 转换为Decimal
        if isinstance(value, Decimal):
            decimal_value = value
        else:
            # 通过字符串转换避免浮点精度问题
            decimal_value = Decimal(str(value))

        # 执行量化
        quantizer = Decimal(1).scaleb(-target_precision)
        quantized = decimal_value.quantize(quantizer, rounding=ROUND_HALF_UP)

        return quantized

    except (ValueError, TypeError, ArithmeticError) as e:
        raise ValueError(f"Cannot convert to decimal: {value} - {e}")


@rule(
    name="comprehensive_decimal_cleaning",
    category=RuleCategory.NUMERIC,
    description="综合数值字段清洗管道 - 整合所有清洗步骤",
)
def comprehensive_decimal_cleaning(
    value: Any,
    field_name: str = "",
    precision: Optional[int] = None,
    handle_percentage: bool = True,
    precision_config: Optional[Dict[str, int]] = None,
) -> Optional[Decimal]:
    """
    综合数值字段清洗管道

    这是一个高级清洗规则，整合了多个清洗步骤，
    可以直接替代现有的clean_decimal_fields函数

    Args:
        value: 输入值
        field_name: 字段名
        precision: 精度
        handle_percentage: 是否处理百分比转换
        precision_config: 精度配置

    Returns:
        清洗后的Decimal值
    """
    # 步骤1: 空值标准化
    cleaned_value = standardize_null_values(value)
    if cleaned_value is None:
        return None

    # 步骤2: 字符串预处理
    if isinstance(cleaned_value, str):
        # 移除货币符号
        cleaned_value = remove_currency_symbols(cleaned_value)

        # 再次检查空值
        cleaned_value = standardize_null_values(cleaned_value)
        if cleaned_value is None:
            return None

    # 步骤3: 百分比处理
    if handle_percentage:
        cleaned_value = handle_percentage_conversion(cleaned_value, field_name)

    # 步骤4: 转换和量化
    try:
        if isinstance(cleaned_value, str):
            # 验证字符串是否为有效数字
            float(cleaned_value)  # 验证但不使用结果

        return decimal_quantization(
            cleaned_value,
            field_name=field_name,
            precision=precision,
            precision_config=precision_config,
        )

    except (ValueError, TypeError) as e:
        raise ValueError(
            f"Invalid numeric value for field '{field_name}': {value} - {e}"
        )


# 便捷函数 - 为特定领域提供预配置的清洗函数
def create_domain_decimal_cleaner(precision_config: Dict[str, int]):
    """
    为特定域创建预配置的数值清洗函数

    Args:
        precision_config: 该域的字段精度配置

    Returns:
        配置好的清洗函数
    """

    def domain_decimal_cleaner(value: Any, field_name: str = "") -> Optional[Decimal]:
        return comprehensive_decimal_cleaning(
            value=value, field_name=field_name, precision_config=precision_config
        )

    return domain_decimal_cleaner


# 预定义的域清洗器
annuity_decimal_cleaner = create_domain_decimal_cleaner(
    {
        "期初资产规模": 4,
        "期末资产规模": 4,
        "供款": 4,
        "流失_含待遇支付": 4,
        "流失": 4,
        "待遇支付": 4,
        "投资收益": 4,
        "当期收益率": 6,
    }
)

trustee_decimal_cleaner = create_domain_decimal_cleaner(
    {
        "return_rate": 6,
        "net_asset_value": 4,
        "fund_scale": 2,
    }
)
