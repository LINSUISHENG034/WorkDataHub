"""
根据JSON配置文件创建目录结构的Python脚本
用法：python create_structure.py -c config.json -t target_dir
"""

import os
import json
import argparse


def create_structure(base_path, config):
    """
    递归创建目录和文件
    :param base_path: 当前基础路径
    :param config: 当前目录配置节点
    """
    # 创建当前目录
    os.makedirs(base_path, exist_ok=True)

    # 创建文件
    for filename in config.get("files", []):
        file_path = os.path.join(base_path, filename)
        with open(file_path, 'w') as f:
            pass  # 创建空文件
        print(f"文件已创建：{file_path}")

    # 递归处理子目录
    for dir_name, dir_config in config.get("dirs", {}).items():
        new_path = os.path.join(base_path, dir_name)
        create_structure(new_path, dir_config)


def main():
    # 设置命令行参数
    parser = argparse.ArgumentParser(description="根据JSON配置创建目录结构")
    parser.add_argument('-c', '--config', required=True, help='配置文件路径')
    parser.add_argument('-t', '--target', default='.', help='目标目录，默认为当前目录')

    args = parser.parse_args()

    try:
        # 读取配置文件
        with open(args.config, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        # 获取根配置
        root_config = config_data.get("root_dir", {})

        # 从根目录开始创建
        create_structure(os.path.abspath(args.target), root_config)

        print("目录结构创建完成！")
    except Exception as e:
        print(f"发生错误：{str(e)}")


if __name__ == "__main__":
    main()