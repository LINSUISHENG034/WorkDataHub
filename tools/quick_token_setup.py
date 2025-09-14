#!/usr/bin/env python3
"""
快速配置EQC Token脚本
简单直接的token配置方式
"""

import os
import sys

def set_token():
    """设置token到.env文件"""

    # 默认token（从用户提供的验证中获得）
    DEFAULT_TOKEN = "a8fea726fdb4e4e67d031e32e43b9e9a"

    print("🔐 EQC Token 快速配置")
    print("=" * 50)

    # 检查.env文件是否存在
    env_file = ".env"

    # 读取现有的.env内容
    existing_lines = []
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            existing_lines = f.readlines()

    # 查找是否已有WDH_EQC_TOKEN
    token_line_index = -1
    for i, line in enumerate(existing_lines):
        if line.strip().startswith("WDH_EQC_TOKEN"):
            token_line_index = i
            break

    # 构建新的token行
    new_token_line = f"WDH_EQC_TOKEN={DEFAULT_TOKEN}\n"

    # 更新或添加token
    if token_line_index >= 0:
        existing_lines[token_line_index] = new_token_line
        print("✅ 更新现有的WDH_EQC_TOKEN")
    else:
        existing_lines.append(new_token_line)
        print("✅ 添加新的WDH_EQC_TOKEN")

    # 写回.env文件
    with open(env_file, "w") as f:
        f.writelines(existing_lines)

    print(f"✅ Token已配置到 {env_file}")
    print(f"Token: {DEFAULT_TOKEN[:8]}...")

    print("\n📝 接下来的步骤：")
    print("1. Token已经配置完成")
    print("2. 可以开始执行S-001: Legacy映射迁移")
    print("3. 可以并行执行S-002: EQC客户端集成")

    print("\n💡 如需更新token，请编辑.env文件中的WDH_EQC_TOKEN值")

    return True

if __name__ == "__main__":
    if set_token():
        print("\n🎉 配置成功！")
    else:
        print("\n❌ 配置失败")
        sys.exit(1)