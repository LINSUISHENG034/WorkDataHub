"""
列名标准化工具

统一处理Excel数据中的列名标准化问题，包括：
- 中文括号转换为下划线格式
- 移除特殊字符和空格
- 统一命名规范

用于解决跨域数据处理中的列名不一致问题。
"""

import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ColumnNormalizer:
    """列名标准化器"""

    def __init__(self):
        # 预定义的列名映射规则
        self._standard_mappings = {
            # 年金业绩域特定映射
            "流失(含待遇支付)": "流失_含待遇支付",
            "流失（含待遇支付）": "流失_含待遇支付",  # 全角括号
            # 其他常见的括号格式
            "净值(元)": "净值_元",
            "净值（元）": "净值_元",
            "规模(万元)": "规模_万元",
            "规模（万元）": "规模_万元",
            # 时间相关
            "报告期(年月)": "报告期_年月",
            "报告期（年月）": "报告期_年月",
        }

        # 需要移除的字符模式
        # 需要移除的模式（不包括普通空格）
        self._remove_patterns = [
            r"[\r\n\t]+",  # 换行符、制表符
        ]

        # 括号转换模式
        self._bracket_patterns = [
            (r"（([^）]+)）", r"_\1"),  # 全角括号
            (r"\(([^)]+)\)", r"_\1"),  # 半角括号
        ]

    def normalize_column_name(self, column_name: str) -> str:
        """
        标准化单个列名

        Args:
            column_name: 原始列名

        Returns:
            标准化后的列名
        """
        if not column_name or not isinstance(column_name, str):
            return ""

        # 步骤1: Unicode规范化 - 将全角字符转为半角
        normalized = unicodedata.normalize("NFKC", column_name)

        # 步骤2: 去除前后空格
        normalized = normalized.strip()

        # 步骤3: 检查预定义映射
        if normalized in self._standard_mappings:
            return self._standard_mappings[normalized]

        # 步骤4: 移除特殊字符（换行符、制表符等）
        for pattern in self._remove_patterns:
            normalized = re.sub(pattern, "", normalized)

        # 步骤5: 括号转换（在移除特殊字符后进行）
        for pattern, replacement in self._bracket_patterns:
            normalized = re.sub(pattern, replacement, normalized)

        # 步骤6: 清理连续下划线
        normalized = re.sub(r"_+", "_", normalized)

        # 步骤7: 去除首尾下划线
        normalized = normalized.strip("_")

        return normalized

    def normalize_columns(self, columns: List[str]) -> Dict[str, str]:
        """
        批量标准化列名

        Args:
            columns: 原始列名列表

        Returns:
            原始列名到标准化列名的映射字典
        """
        mapping = {}
        normalized_set = set()
        conflicts = []

        for original in columns:
            normalized = self.normalize_column_name(original)

            if normalized:
                if normalized in normalized_set:
                    conflicts.append(f"重复的标准化列名: '{normalized}' 来自 '{original}'")
                else:
                    normalized_set.add(normalized)
                    mapping[original] = normalized
            else:
                logger.warning(f"列名标准化后为空: '{original}'")
                mapping[original] = original  # 保持原样

        if conflicts:
            logger.warning(f"发现列名标准化冲突: {conflicts}")

        return mapping

    def apply_normalization(
        self, data_rows: List[Dict[str, Any]], column_mapping: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        对数据行应用列名标准化

        Args:
            data_rows: 原始数据行列表
            column_mapping: 列名映射字典，如果不提供则自动生成

        Returns:
            标准化后的数据行列表
        """
        if not data_rows:
            return data_rows

        # 如果没有提供映射，从第一行数据生成
        if column_mapping is None:
            column_mapping = self.normalize_columns(list(data_rows[0].keys()))

        # 应用列名映射
        normalized_rows = []
        for row in data_rows:
            normalized_row = {}
            for original_col, value in row.items():
                normalized_col = column_mapping.get(original_col, original_col)
                normalized_row[normalized_col] = value
            normalized_rows.append(normalized_row)

        # 记录标准化结果
        changed_mappings = {k: v for k, v in column_mapping.items() if k != v}
        if changed_mappings:
            logger.info(f"应用列名标准化: {len(changed_mappings)} 个列名被标准化")
            for original, normalized in changed_mappings.items():
                logger.debug(f"  '{original}' -> '{normalized}'")

        return normalized_rows

    def add_custom_mapping(self, original: str, normalized: str):
        """添加自定义映射规则"""
        self._standard_mappings[original] = normalized
        logger.debug(f"添加自定义列名映射: '{original}' -> '{normalized}'")

    def get_standard_mappings(self) -> Dict[str, str]:
        """获取当前的标准映射规则"""
        return self._standard_mappings.copy()


# 全局实例
_default_normalizer = ColumnNormalizer()


def normalize_column_name(column_name: str) -> str:
    """便捷函数：标准化单个列名"""
    return _default_normalizer.normalize_column_name(column_name)


def normalize_columns(columns: List[str]) -> Dict[str, str]:
    """便捷函数：批量标准化列名"""
    return _default_normalizer.normalize_columns(columns)


def apply_column_normalization(
    data_rows: List[Dict[str, Any]], column_mapping: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """便捷函数：对数据行应用列名标准化"""
    return _default_normalizer.apply_normalization(data_rows, column_mapping)


def add_domain_mapping(original: str, normalized: str):
    """便捷函数：添加领域特定的映射规则"""
    _default_normalizer.add_custom_mapping(original, normalized)
