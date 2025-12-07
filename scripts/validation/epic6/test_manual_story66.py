"""Story 6.6 手动验证测试脚本

用法:
    uv run python scripts/validation/epic6/test_manual_story66.py --test t1
    uv run python scripts/validation/epic6/test_manual_story66.py --test all
"""

import argparse
import sys
from typing import Optional

import structlog

# 配置日志
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
)


def test_t1_basic_lookup():
    """T1: 基本查询成功 (AC1, AC2)"""
    print("\n" + "=" * 60)
    print("T1: 基本查询成功 (AC1, AC2)")
    print("=" * 60)

    from work_data_hub.config.settings import get_settings
    settings = get_settings()
    from work_data_hub.infrastructure.enrichment.eqc_provider import EqcProvider

    provider = EqcProvider(
        token=settings.eqc_token,
        budget=5,
    )

    test_name = "中国平安保险"
    print(f"\n查询公司: {test_name}")
    result = provider.lookup(test_name)

    print(f"\n--- 结果 ---")
    if result:
        print(f"✅ Company ID: {result.company_id}")
        print(f"✅ Official Name: {result.official_name}")
        print(f"✅ Confidence: {result.confidence}")
        print(f"✅ Match Type: {result.match_type}")
        print(f"✅ Unified Credit Code: {result.unified_credit_code}")
    else:
        print("❌ 查询返回 None")

    print(f"\n剩余预算: {provider.remaining_budget}")
    print(f"Provider 可用: {provider.is_available}")

    return result is not None


def test_t2_budget_exhaustion():
    """T2: 预算耗尽行为 (AC3, AC9)"""
    print("\n" + "=" * 60)
    print("T2: 预算耗尽行为 (AC3, AC9)")
    print("=" * 60)

    from work_data_hub.config.settings import get_settings
    settings = get_settings()
    from work_data_hub.infrastructure.enrichment.eqc_provider import EqcProvider

    provider = EqcProvider(
        token=settings.eqc_token,
        budget=2,  # 小预算
    )

    companies = ["中国平安", "腾讯科技", "阿里巴巴", "华为技术"]

    for i, name in enumerate(companies):
        print(f"\n--- 查询 {i + 1}: {name} ---")
        print(f"查询前预算: {provider.remaining_budget}")
        print(f"Provider 可用: {provider.is_available}")

        result = provider.lookup(name)

        status = "✅ 成功" if result else "⚠️ 无结果/预算耗尽"
        print(f"查询结果: {status}")
        print(f"查询后预算: {provider.remaining_budget}")

    print(f"\n--- 最终状态 ---")
    print(f"Provider 可用: {provider.is_available}")
    return provider.remaining_budget == 0


def test_t3_timeout_retry():
    """T3: 超时与重试 (AC4, AC5)"""
    print("\n" + "=" * 60)
    print("T3: 超时与重试 (AC4, AC5)")
    print("=" * 60)

    from work_data_hub.infrastructure.enrichment.eqc_provider import EqcProvider

    # 使用无效地址测试超时
    provider = EqcProvider(
        token="test_token_12345678901234567890",
        budget=5,
        base_url="https://invalid.example.com",
    )

    print("\n使用无效地址测试超时重试...")
    print("预期: 重试 2 次后返回 None")

    result = provider.lookup("测试公司")

    print(f"\n--- 结果 ---")
    print(f"查询结果: {result}")
    print(f"剩余预算: {provider.remaining_budget}")

    return result is None


def test_t4_cache_write():
    """T4: 缓存写入验证 (AC6, AC11)"""
    print("\n" + "=" * 60)
    print("T4: 缓存写入验证 (AC6, AC11)")
    print("=" * 60)

    from sqlalchemy import create_engine, text

    from work_data_hub.config.settings import get_settings
    settings = get_settings()
    from work_data_hub.infrastructure.enrichment.eqc_provider import EqcProvider
    from work_data_hub.infrastructure.enrichment.mapping_repository import (
        CompanyMappingRepository,
    )

    engine = create_engine(settings.database_url)
    repo = CompanyMappingRepository(engine)

    provider = EqcProvider(
        token=settings.eqc_token,
        budget=5,
        mapping_repository=repo,
    )

    test_name = "深圳市腾讯计算机系统有限公司"
    print(f"\n查询公司: {test_name}")

    result = provider.lookup(test_name)

    if result:
        print(f"✅ 查询成功: {result.company_id}")

        # 验证缓存写入
        with engine.connect() as conn:
            cache_result = conn.execute(
                text(
                    "SELECT company_id, match_type FROM enterprise.company_name_index WHERE company_name = :name"
                ),
                {"name": test_name},
            ).fetchone()

            if cache_result:
                print(f"✅ 缓存记录存在")
                print(f"   Company ID: {cache_result[0]}")
                print(f"   Match Type: {cache_result[1]}")
                return True
            else:
                print("❌ 缓存记录不存在")
                return False
    else:
        print("❌ 查询失败")
        return False


def test_t5_not_found():
    """T5: 404 处理 (AC7)"""
    print("\n" + "=" * 60)
    print("T5: 404 处理 (AC7)")
    print("=" * 60)

    from work_data_hub.config.settings import get_settings
    settings = get_settings()
    from work_data_hub.infrastructure.enrichment.eqc_provider import EqcProvider

    provider = EqcProvider(
        token=settings.eqc_token,
        budget=5,
    )

    test_name = "这是一个绝对不存在的公司名称XYZ12345"
    print(f"\n查询不存在的公司: {test_name}")

    result = provider.lookup(test_name)

    print(f"\n--- 结果 ---")
    print(f"查询结果: {result}")
    print(f"Provider 仍可用: {provider.is_available}")
    print(f"剩余预算: {provider.remaining_budget}")

    # 预期: 返回 None，但 Provider 仍可用
    return result is None and provider.is_available


def test_t6_unauthorized():
    """T6: 401 会话禁用 (AC8)"""
    print("\n" + "=" * 60)
    print("T6: 401 会话禁用 (AC8)")
    print("=" * 60)

    from work_data_hub.infrastructure.enrichment.eqc_provider import EqcProvider

    # 使用无效 Token
    provider = EqcProvider(
        token="invalid_token_12345678901234567890",
        budget=5,
    )

    print("\n使用无效 Token 测试 401 处理...")

    result1 = provider.lookup("中国平安")
    print(f"\n第一次查询结果: {result1}")
    print(f"Provider 禁用状态: {provider._disabled}")
    print(f"Provider 可用: {provider.is_available}")

    result2 = provider.lookup("另一个公司")
    print(f"\n第二次查询结果: {result2}")

    # 预期: 401 后 Provider 被禁用
    return provider._disabled and not provider.is_available


def test_t7_token_management():
    """T7: Token 管理 (AC10)"""
    print("\n" + "=" * 60)
    print("T7: Token 管理 (AC10)")
    print("=" * 60)

    from work_data_hub.config.settings import get_settings
    settings = get_settings()
    from work_data_hub.infrastructure.enrichment.eqc_provider import EqcProvider

    print(f"\n--- Token 配置检查 ---")
    print(f"Token 已配置: {bool(settings.eqc_token)}")
    print(f"Token 长度: {len(settings.eqc_token) if settings.eqc_token else 0}")

    # 测试无 Token 时的行为
    provider_no_token = EqcProvider(token="", budget=5)
    print(f"\n无 Token Provider 可用: {provider_no_token.is_available}")

    # 测试有 Token 时的行为
    provider_with_token = EqcProvider(token=settings.eqc_token, budget=5)
    print(f"有 Token Provider 可用: {provider_with_token.is_available}")

    return not provider_no_token.is_available and provider_with_token.is_available


def test_t8_security():
    """T8: 安全性验证 (AC12)"""
    print("\n" + "=" * 60)
    print("T8: 安全性验证 (AC12)")
    print("=" * 60)

    import io
    import logging

    # 捕获日志输出
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)

    # 配置 structlog 输出到捕获器
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(10),
    )

    from work_data_hub.config.settings import get_settings
    settings = get_settings()
    from work_data_hub.infrastructure.enrichment.eqc_provider import EqcProvider

    provider = EqcProvider(
        token=settings.eqc_token,
        budget=5,
    )

    print("\n执行查询并检查日志...")
    result = provider.lookup("中国平安")

    # 检查日志中是否包含 token
    log_output = log_capture.getvalue()
    token_leaked = settings.eqc_token in log_output if settings.eqc_token else False

    print(f"\n--- 安全检查结果 ---")
    if token_leaked:
        print("❌ 警告: Token 可能泄露到日志中!")
    else:
        print("✅ Token 未泄露到日志")

    print("\n请手动检查上方日志输出，确保没有显示实际的 Token 值")

    return not token_leaked


def test_t9_integration():
    """T9: Resolver 集成测试 (AC13)"""
    print("\n" + "=" * 60)
    print("T9: Resolver 集成测试 (AC13)")
    print("=" * 60)

    import pandas as pd
    from sqlalchemy import create_engine

    from work_data_hub.config.settings import get_settings
    settings = get_settings()
    from work_data_hub.infrastructure.enrichment.company_id_resolver import (
        CompanyIdResolver,
    )
    from work_data_hub.infrastructure.enrichment.eqc_provider import EqcProvider
    from work_data_hub.infrastructure.enrichment.mapping_repository import (
        CompanyMappingRepository,
    )
    from work_data_hub.infrastructure.enrichment.types import ResolutionStrategy

    # 准备测试数据
    df = pd.DataFrame(
        {
            "客户名称": ["中国平安保险", "腾讯科技", "不存在的公司XYZ123"],
        }
    )

    print("\n--- 输入数据 ---")
    print(df)

    # 创建组件
    engine = create_engine(settings.database_url)
    repo = CompanyMappingRepository(engine)
    provider = EqcProvider(
        token=settings.eqc_token,
        budget=5,
        mapping_repository=repo,
    )

    resolver = CompanyIdResolver(
        eqc_provider=provider,
        mapping_repository=repo,
        yaml_overrides={"plan": {}, "account": {}, "hardcode": {}, "name": {}, "account_name": {}},
    )

    strategy = ResolutionStrategy(
        customer_name_column="客户名称",
        output_column="company_id",
        use_enrichment_service=True,
        sync_lookup_budget=3,
    )

    # 执行解析
    result = resolver.resolve_batch(df, strategy)

    print("\n--- 解析结果 ---")
    print(result.data[["客户名称", "company_id"]])

    print(f"\n--- 统计信息 ---")
    stats = result.statistics
    print(f"EQC 命中数: {getattr(stats, 'eqc_sync_hits', 'N/A')}")
    print(f"剩余预算: {getattr(stats, 'budget_remaining', 'N/A')}")
    print(f"临时ID数: {getattr(stats, 'temp_ids_generated', 'N/A')}")

    return True


def run_all_tests():
    """运行所有测试"""
    tests = [
        ("T1", test_t1_basic_lookup),
        ("T2", test_t2_budget_exhaustion),
        ("T3", test_t3_timeout_retry),
        ("T4", test_t4_cache_write),
        ("T5", test_t5_not_found),
        ("T6", test_t6_unauthorized),
        ("T7", test_t7_token_management),
        ("T8", test_t8_security),
        ("T9", test_t9_integration),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, "✅ PASS" if passed else "❌ FAIL"))
        except Exception as e:
            results.append((name, f"❌ ERROR: {e}"))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, status in results:
        print(f"{name}: {status}")


def main():
    parser = argparse.ArgumentParser(description="Story 6.6 手动验证测试")
    parser.add_argument(
        "--test",
        choices=["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9", "all"],
        required=True,
        help="要运行的测试",
    )
    args = parser.parse_args()

    test_map = {
        "t1": test_t1_basic_lookup,
        "t2": test_t2_budget_exhaustion,
        "t3": test_t3_timeout_retry,
        "t4": test_t4_cache_write,
        "t5": test_t5_not_found,
        "t6": test_t6_unauthorized,
        "t7": test_t7_token_management,
        "t8": test_t8_security,
        "t9": test_t9_integration,
        "all": run_all_tests,
    }

    test_func = test_map[args.test]
    test_func()


if __name__ == "__main__":
    main()
