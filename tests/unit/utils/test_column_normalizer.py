import time

import pytest

from work_data_hub.utils.column_normalizer import normalize_column_names


@pytest.mark.unit
def test_basic_whitespace_normalization():
    columns = ["月度  ", "  计划代码", "客户名称\n", "期末资产规模"]
    assert normalize_column_names(columns) == ["月度", "计划代码", "客户名称", "期末资产规模"]


@pytest.mark.unit
def test_fullwidth_space_replacement():
    assert normalize_column_names(["客户　名称"]) == ["客户名称"]


@pytest.mark.unit
def test_newline_tab_handling_removes_all_whitespace():
    columns = ["客户\n名称", "计划\t代码", "期 末 资 产"]
    assert normalize_column_names(columns) == ["客户名称", "计划代码", "期末资产"]


@pytest.mark.unit
def test_empty_column_name_placeholders(caplog):
    columns = ["", "   ", "\n", "月度"]
    result = normalize_column_names(columns)
    assert result == ["Unnamed_1", "Unnamed_2", "Unnamed_3", "月度"]
    # Ensure warnings emitted for placeholders
    assert "column_normalizer.empty_name_placeholder_generated" in caplog.text


@pytest.mark.unit
def test_duplicate_handling_with_suffix(caplog):
    columns = ["月度", "月度  ", "  月度"]
    result = normalize_column_names(columns)
    assert result == ["月度", "月度_1", "月度_2"]
    assert "column_normalizer.duplicate_name_resolved" in caplog.text


@pytest.mark.unit
def test_nonstring_type_handling():
    columns = [None, 123, "月度", True, 3.14]
    result = normalize_column_names(columns)
    assert result == ["Unnamed_1", "123", "月度", "True", "3.14"]


@pytest.mark.unit
def test_mixed_edge_cases():
    columns = ["月度  ", "客户　名称", "", "月度\n", 123]
    result = normalize_column_names(columns)
    assert result == ["月度", "客户名称", "Unnamed_1", "月度_1", "123"]


@pytest.mark.unit
def test_chinese_character_preservation():
    columns = ["月度", "计划代码", "客户名称", "期末资产规模", "当期收益率"]
    assert normalize_column_names(columns) == columns


@pytest.mark.unit
def test_emoji_in_column_names():
    columns = ["客户名称 😀", "月度 🎉"]
    assert normalize_column_names(columns) == ["客户名称😀", "月度🎉"]


@pytest.mark.unit
def test_normalization_performance_100_columns():
    columns = [f"列 {i}  " for i in range(100)]
    start = time.perf_counter()
    normalize_column_names(columns)
    duration_ms = (time.perf_counter() - start) * 1000
    assert duration_ms < 100


@pytest.mark.unit
def test_normalization_performance_realistic_23_columns():
    columns = [
        "月度",
        "业务类型",
        "计划类型",
        "计划代码",
        "计划名称",
        "组合类型",
        "组合代码",
        "组合名称",
        "客户名称",
        "期初资产规模",
        "期末资产规模",
        "供款",
        "流失(含待遇支付)",
        "流失",
        "待遇支付",
        "投资收益",
        "当期收益率",
        "机构代码",
        "机构",
        "子企业号",
        "子企业名称",
        "集团企业客户号",
        "集团企业客户名称",
    ]
    start = time.perf_counter()
    normalize_column_names(columns)
    duration_ms = (time.perf_counter() - start) * 1000
    assert duration_ms < 10
