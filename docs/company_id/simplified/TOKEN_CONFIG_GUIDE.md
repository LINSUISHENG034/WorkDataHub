# EQC Token配置指南

## 🎯 配置方式

EQC token已经集成到项目的标准配置流程中，通过`.env`文件进行管理。

## 📋 配置步骤

### 1. 获取Token

1. 访问 https://eqc.pingan.com/
2. 使用账号密码登录（需要手机验证码和滑动验证）
3. 登录成功后，按F12打开开发者工具
4. 切换到Network标签
5. 在EQC网站上执行任意企业搜索（如搜索"中国平安"）
6. 在Network中找到包含`/api/search`的请求
7. 点击该请求，查看Headers标签
8. 找到Request Headers中的`token`字段
9. 复制token值（32位字符串）

### 2. 配置Token

在项目根目录的`.env`文件中配置：

```bash
# EQC API Token
WDH_EQC_TOKEN=你的32位token值
```

示例：
```bash
WDH_EQC_TOKEN=a8fea726fdb4e4e67d031e32e43b9e9a
```

### 3. 验证配置

运行以下命令验证token是否有效：

```bash
# 使用Python脚本验证
uv run python -c "
import os
token = os.getenv('WDH_EQC_TOKEN')
if token and len(token) == 32:
    print(f'✅ Token已配置: {token[:8]}...')
else:
    print('❌ Token未配置或格式错误')
"
```

## ⚠️ 注意事项

1. **Token有效期**：Token在30分钟不活动后会过期
2. **定期更新**：需要使用时重新获取并更新`.env`文件
3. **安全性**：不要将包含真实token的`.env`文件提交到Git
4. **格式要求**：Token必须是32位字符串

## 🚀 使用方式

配置完成后，S-002 EQC客户端会自动从环境变量读取token：

```python
import os
from src.work_data_hub.io.connectors.eqc_client import EQCClient

# 自动从环境变量获取token
token = os.getenv('WDH_EQC_TOKEN')
client = EQCClient(token=token)

# 使用客户端
results = client.search_company("测试企业")
```

## 📅 后续优化

当前采用手动配置方式，后续将开发半自动化token获取模块，降低使用门槛。