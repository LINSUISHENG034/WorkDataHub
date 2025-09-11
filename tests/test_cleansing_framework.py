"""
数据清洗框架功能测试

验证新框架的核心功能是否正常工作，
确保能够成功替代现有的重复实现。
"""

from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ValidationError

# 测试前先设置 Python 路径
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from src.work_data_hub.cleansing import (
        registry,
        decimal_fields_cleaner,
        comprehensive_decimal_cleaning,
        get_framework_info,
        find_rules_for_field
    )
    FRAMEWORK_AVAILABLE = True
except ImportError as e:
    print(f"框架导入失败: {e}")
    FRAMEWORK_AVAILABLE = False


class TestCleansingFramework:
    """清洗框架核心功能测试"""
    
    def test_registry_functionality(self):
        """测试注册表基本功能"""
        # 检查是否有注册的规则
        all_rules = registry.list_all_rules()
        assert len(all_rules) > 0, "应该有已注册的清洗规则"
        
        # 检查是否能按名称查找规则
        decimal_rule = registry.find_by_name("comprehensive_decimal_cleaning")
        assert decimal_rule is not None, "应该能找到 comprehensive_decimal_cleaning 规则"
        
        # 检查是否能按字段模式查找规则
        asset_rules = registry.find_by_field_pattern("期初资产规模")
        assert len(asset_rules) > 0, "应该能为 '期初资产规模' 字段找到适用规则"
    
    def test_decimal_cleaning_rules(self):
        """测试数值清洗规则"""
        # 测试货币符号清理
        result = comprehensive_decimal_cleaning("¥1,234.56", "期初资产规模")
        assert result == Decimal("1234.5600"), f"货币符号清理失败: {result}"
        
        # 测试百分比转换
        result = comprehensive_decimal_cleaning("5.25%", "当期收益率")
        assert result == Decimal("0.052500"), f"百分比转换失败: {result}"
        
        # 测试空值处理
        result = comprehensive_decimal_cleaning("-", "供款")
        assert result is None, f"空值处理失败: {result}"
        
        # 测试精度量化
        result = comprehensive_decimal_cleaning("123.456789", "期初资产规模")
        assert str(result) == "123.4568", f"精度量化失败: {result}"
    
    def test_pydantic_integration(self):
        """测试与 Pydantic 的集成"""
        
        @decimal_fields_cleaner(
            "amount", "rate",
            precision_config={"rate": 6, "amount": 4}
        )
        class TestModel(BaseModel):
            amount: Optional[Decimal] = None
            rate: Optional[Decimal] = None
        
        # 测试正常数据
        model = TestModel(amount="¥1,234.567", rate="5.25%")
        assert model.amount == Decimal("1234.5670")
        assert model.rate == Decimal("0.052500")
        
        # 测试空值
        model = TestModel(amount="-", rate="N/A")
        assert model.amount is None
        assert model.rate is None
    
    def test_framework_info(self):
        """测试框架信息功能"""
        info = get_framework_info()
        
        assert "version" in info
        assert "total_rules" in info
        assert info["total_rules"] > 0
        
        # 测试字段规则查找
        rules = find_rules_for_field("期初资产规模")
        assert len(rules) > 0, "应该能为金额字段找到适用规则"
    
    def test_extensibility(self):
        """测试框架扩展性"""
        from src.work_data_hub.cleansing import rule, RuleCategory
        
        # 动态添加新规则
        @rule(
            name="test_custom_rule",
            category=RuleCategory.STRING,
            description="测试自定义规则",
            field_patterns=["test_*"]
        )
        def custom_cleaner(value):
            return str(value).upper() if value else None
        
        # 验证规则已注册
        custom_rule = registry.find_by_name("test_custom_rule")
        assert custom_rule is not None
        
        # 验证规则功能
        result = custom_cleaner("hello")
        assert result == "HELLO"


def test_framework_solves_duplication():
    """
    集成测试: 验证框架成功解决重复实现问题
    
    模拟原来在两个 domain 中重复的场景
    """
    
    # 模拟年金业绩模型
    @decimal_fields_cleaner(
        "期初资产规模", "当期收益率",
        precision_config={"当期收益率": 6, "期初资产规模": 4}
    )
    class AnnuityModel(BaseModel):
        期初资产规模: Optional[Decimal] = None
        当期收益率: Optional[Decimal] = None
    
    # 模拟受托业绩模型  
    @decimal_fields_cleaner(
        "return_rate", "fund_scale",
        precision_config={"return_rate": 6, "fund_scale": 2}
    )
    class TrusteeModel(BaseModel):
        return_rate: Optional[Decimal] = None
        fund_scale: Optional[Decimal] = None
    
    # 使用相同的测试数据
    test_data = {
        "currency_field": "¥1,234.567",
        "percentage_field": "5.25%",
        "null_field": "-"
    }
    
    # 测试年金模型
    annuity = AnnuityModel(
        期初资产规模=test_data["currency_field"],
        当期收益率=test_data["percentage_field"]
    )
    
    # 测试受托模型
    trustee = TrusteeModel(
        return_rate=test_data["percentage_field"], 
        fund_scale=test_data["currency_field"]
    )
    
    # 验证两个模型使用相同的清洗逻辑得到一致的结果
    assert annuity.当期收益率 == trustee.return_rate  # 相同的百分比处理
    assert str(annuity.期初资产规模) == "1234.5670"     # 4位精度
    assert str(trustee.fund_scale) == "1234.57"        # 2位精度


if __name__ == "__main__":
    # 运行测试
    test = TestCleansingFramework()
    
    print("=== 运行清洗框架测试 ===\n")
    
    try:
        print("1. 测试注册表功能...")
        test.test_registry_functionality()
        print("   ✅ 通过")
        
        print("2. 测试数值清洗规则...")
        test.test_decimal_cleaning_rules()
        print("   ✅ 通过")
        
        print("3. 测试 Pydantic 集成...")
        test.test_pydantic_integration()
        print("   ✅ 通过")
        
        print("4. 测试框架信息功能...")
        test.test_framework_info()
        print("   ✅ 通过")
        
        print("5. 测试扩展性...")
        test.test_extensibility()
        print("   ✅ 通过")
        
        print("6. 测试重复问题解决...")
        test_framework_solves_duplication()
        print("   ✅ 通过")
        
        print("\n🎉 所有测试通过！清洗框架可以正常使用。")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()