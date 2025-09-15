#!/usr/bin/env python3
"""
EQC 认证最简测试工具（KISS / YAGNI）

用途：用最小实现验证通过浏览器交互登录后，程序能自动捕获并打印 EQC token 前缀。
说明：不包含滑块增强/调试等复杂功能；如需进一步自动化，请参考 docs/company_id/simplified。
"""

import asyncio
import sys

try:
    # Use absolute import from the package root
    from work_data_hub.auth.eqc_auth_handler import get_auth_token_interactively
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请确保已在项目根目录执行 `uv pip install -e .` 以便脚本能找到模块。")
    print("然后运行: uv run python scripts/demos/test_slider_fix.py")
    sys.exit(1)


def print_welcome():
    print("🔐 EQC 认证最简测试")
    print("=" * 40)
    print("目标：通过浏览器登录并自动捕获token")
    print()


def print_menu():
    print("请选择要执行的操作：")
    print()
    print("1. 🚀 启动浏览器并捕获token（推荐）")
    print("2. 📋 显示简要使用说明")
    print("3. ❌ 退出")
    print()


async def run_simple_authentication():
    print("🚀 启动浏览器进行认证")
    print("=" * 30)
    print("请在弹出的浏览器中登录EQC，并执行一次搜索以触发请求")
    print()
    try:
        token = await get_auth_token_interactively(timeout_seconds=300)
        if token:
            print("🎉 认证成功！")
            print(f"Token 前缀: {token}...")
            print(f"Token 长度: {len(token)} 字符")
            return True
        else:
            print("❌ 未捕获到token，请重试")
            return False
    except Exception as e:
        print(f"❌ 认证出错: {e}")
        return False


def show_usage():
    print("📋 使用说明")
    print("=" * 30)
    print("1) 选择 1 启动浏览器")
    print("2) 在EQC页面完成登录（含验证码/滑块）")
    print("3) 在搜索框随便搜索一次，程序将自动捕获token")
    print("4) 捕获成功后可在其他流程中复用该token（建议存入环境变量 WDH_EQC_TOKEN）")


def show_troubleshooting_guide():
    """显示故障排查指南"""
    print("📋 EQC滑块验证故障排查指南")
    print("=" * 50)

    guide = [
        "🔍 常见问题诊断：",
        "",
        "1. 滑块总是验证失败",
        "   原因：浏览器自动化被检测",
        "   解决：使用增强认证模式",
        "",
        "2. 滑块无法移动",
        "   原因：元素定位错误或在iframe中",
        "   解决：运行故障诊断工具检查",
        "",
        "3. 移动了但验证失败",
        "   原因：鼠标轨迹不自然",
        "   解决：使用人类化轨迹算法",
        "",
        "4. 页面卡死或报错",
        "   原因：JavaScript错误或网络问题",
        "   解决：检查控制台错误信息",
        "",
        "🛠️ 立即尝试的解决方案：",
        "",
        "✅ 使用增强认证模式（选项1）",
        "✅ 运行故障诊断工具（选项2）",
        "✅ 检查网络和浏览器设置",
        "✅ 尝试不同时间段登录",
        "",
        "📞 如仍无法解决：",
        "1. 保存故障诊断报告",
        "2. 截图保存错误页面",
        "3. 记录详细错误信息",
        "",
        "💡 预防措施：",
        "• 保持Playwright版本更新",
        "• 避免过于频繁的认证尝试",
        "• 使用稳定的网络环境"
    ]

    for line in guide:
        print(line)


async def main():
    print_welcome()
    while True:
        print_menu()
        try:
            choice = input("请输入选项号码 (1-3): ").strip()
            if choice == "1":
                await run_simple_authentication()
            elif choice == "2":
                show_usage()
            elif choice == "3":
                print("👋 再见！")
                break
            else:
                print("❌ 无效选项，请输入 1-3")
            print("\n" + "=" * 40)
            input("按回车键继续...")
            print()
        except KeyboardInterrupt:
            print("\n\n👋 用户取消操作，再见！")
            break
        except Exception as e:
            print(f"\n❌ 程序出错: {e}")
            input("按回车键继续...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 程序被用户终止")
    except Exception as e:
        print(f"\n❌ 程序运行出错: {e}")
        input("按回车键退出...")
