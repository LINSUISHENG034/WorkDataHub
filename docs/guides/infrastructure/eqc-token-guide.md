# EQC Token 获取和使用指南

本指南介绍如何获取和使用EQC（企业查询中心）API Token，以便访问WorkDataHub的企业数据查询功能。

## 概述

EQC API Token是访问企业查询中心API的认证凭证。WorkDataHub通过配置化的方式管理Token，所有Token都存储在项目根目录的`.env`文件中。

## 获取EQC Token

### 方法一：使用全自动二维码认证脚本（首选推荐）

这是**最高效、最便捷**的方法。脚本会在后台静默运行，自动跳转到扫码界面，并弹出一个精致的二维码窗口。您只需拿出手机扫描即可，Token 会自动捕获并保存。

**特点：**
- **无感体验**：浏览器在后台运行（Headless模式），不打扰工作。
- **自动导航**：自动跳过首页、自动切换到二维码登录模式、自动勾选协议。
- **统一弹窗**：弹出独立的“快乐平安”扫码窗口，体验一致。
- **自动清理**：登录完成后自动关闭窗口并删除临时二维码图片。
- **智能记录**：保存 Token 到 `.env` 时会自动附带时间戳注释。

**运行命令：**

```bash
uv run python src/work_data_hub/io/auth/auto_eqc_auth.py
```

**执行流程：**
1. 在终端运行上述命令。
2. 等待几秒，屏幕会出现一个名为“扫码登录 - 平安E企查”的窗口。
3. 使用手机“快乐平安”App 扫描窗口中的二维码。
4. 手机确认登录后，窗口自动关闭。
5. 终端提示 `✅ Token 已自动保存到 .env`。

---

### 方法二：使用交互式认证脚本（备选）

如果自动脚本遇到问题（如网络环境极其特殊），可以使用此手动交互模式。脚本会打开一个可见的浏览器窗口，由您手动操作登录。

**运行代码：**

```python
from work_data_hub.io.auth.eqc_auth_handler import run_get_token

# 获取Token并自动保存到.env文件
token = run_get_token(timeout_seconds=300, save_to_env=True)
```

**执行步骤：**
1. 运行上述代码。
2. 浏览器会自动打开EQC登录页面。
3. **手动**完成登录操作（点击切换二维码、勾选协议、扫码等）。
4. 登录后进行任意搜索操作。
5. 脚本会自动捕获Token并保存。

## 配置Token

### 1. 编辑.env文件

脚本会自动处理这一步，但您也可以手动查看。在项目根目录的`.env`文件中：

```env
# EQC API Token（必需）
WDH_EQC_TOKEN=eyJhbGciOiJIUzUxMiJ9... # Updated: 2025-12-09 10:30:00

# Token会在30分钟无活动后过期
```

### 2. 验证配置

运行验证脚本确认Token有效：

```bash
PYTHONPATH=src uv run python scripts/validation/epic6/test_manual_story66.py --test t1
```

## 使用Token

### 在代码中使用

```python
from work_data_hub.config.settings import get_settings
from work_data_hub.infrastructure.enrichment.eqc_provider import EqcProvider

# Token会自动从.env文件加载
settings = get_settings()
print(f"Token loaded: {settings.eqc_token[:10]}...")  # 显示前10位

# 使用Provider查询企业
provider = EqcProvider()
result = provider.lookup("中国平安保险")
```

## 重要注意事项

### 1. Token安全
- **不要提交`.env`文件到版本控制系统**
- Token包含敏感信息，仅用于开发环境
- 生产环境应使用安全的凭据管理方案

### 2. Token有效期
- Token在**30分钟无活动后自动过期**
- 如果Token过期，只需重新运行 `auto_eqc_auth.py` 即可快速刷新。

### 3. 环境要求
- 全自动脚本依赖 `tkinter`（Python通常内置）。
- 需要 `playwright` 浏览器驱动（如果没有安装，运行 `uv run playwright install chromium`）。

## 常见问题

### Q: 运行自动脚本时看不到二维码窗口？
A: 
1. 检查任务栏，窗口可能没有置顶。
2. 检查控制台是否有错误日志。
3. 如果依然无法弹出，可以尝试方法二（交互式脚本）。

### Q: Token提示无效怎么办？
A:
1. 确认Token没有过期（30分钟无活动）。
2. 使用 `auto_eqc_auth.py` 重新获取。

## 相关文件位置

- **全自动认证（首选）**：`src/work_data_hub/io/auth/auto_eqc_auth.py`
- 交互式认证（核心逻辑）：`src/work_data_hub/io/auth/eqc_auth_handler.py`
- EQC客户端：`src/work_data_hub/io/connectors/eqc_client.py`
- 配置文件：`src/work_data_hub/config/settings.py`

## 更新历史

- 2025-12-09: 推荐使用 `auto_eqc_auth.py` 进行全自动二维码认证，支持无头模式和统一弹窗。
- 2025-12-08: 初始版本，支持Token自动保存功能。
