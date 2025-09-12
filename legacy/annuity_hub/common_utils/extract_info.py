import pandas as pd
import re
import os


def process_um_info(data):
    # 处理数据
    pattern = r'"(.*?)"(?: \((.*?)\))? <(.*?)@(.*?)>'
    matches = re.findall(pattern, data)

    # 创建DataFrame
    columns = ['姓名', '邮箱名', 'um账号', '邮箱后缀']
    df = pd.DataFrame(matches, columns=columns)

    # 增加邮箱字段
    df['邮箱'] = df['um账号'] + '@' + df['邮箱后缀']
    df['邮箱名'] = df['姓名'] + df.apply(lambda x: f"({x['邮箱名']})" if x['邮箱名'] else '', axis=1)

    # 重排列
    df = df[['姓名', '邮箱名', 'um账号', '邮箱']]

    # 保存到Excel
    desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop', 'um_info.xlsx')
    df.to_excel(desktop_path, index=False)
    print(f"文件已保存到: {desktop_path}")


if __name__ == '__main__':
    # 用户输入字符串
    data = input('请输入需要处理的UM账号信息: ')
    # 调用函数
    process_um_info(data)
