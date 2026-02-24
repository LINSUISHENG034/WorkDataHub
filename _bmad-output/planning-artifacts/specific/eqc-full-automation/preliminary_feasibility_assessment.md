# EQC 全自动登录方案初步可行性评估

**日期**: 2025年12月7日
**状态**: 初步评估完成，待深入验证

## 1. 背景
目前 `src/work_data_hub/auth/eqc_auth_handler.py` 为半自动化脚本，依赖人工干预完成登录（输入验证码/令牌、处理滑块）。目标是将其升级为全自动无人值守脚本。

## 2. 关键卡点评估

### 2.1 验证码/令牌获取 (OTP)
*   **现状**: 
    *   现有 Chrome 插件通过调用 `otp.paic.com.cn` 接口获取验证码。
    *   项目中已存在 `src/work_data_hub/utils/patoken_client.py` 文件。
*   **分析**: 
    *   该文件完整实现了基于 `gmssl` (国密算法) 的 OTP 获取逻辑，模仿了 Chrome 插件的行为。
    *   支持从环境变量读取账号密码，自动请求 API 获取当前有效的 OTP。
*   **结论**: **高可行性**。无需重新开发，只需将 `PATokenClient` 集成到 Playwright 登录流程中，在检测到验证码输入框时自动填入。

### 2.2 滑块验证 (Slider Captcha)
*   **现状**: 
    *   `src/work_data_hub/auth/eqc_auth_opencv.py` 已包含基于 OpenCV 的处理逻辑。
    *   依赖 `opencv-python-headless` 和 `numpy`。
*   **分析**: 
    *   **图像识别**: 实现了 `_capture_slider_images` 和 `_solve_offset_with_opencv`，通过对比背景图和缺口图（或边缘检测）计算滑块位移。
    *   **轨迹模拟**: 实现了 `_drag_by_offset`，包含简单的物理轨迹模拟（加速/减速）以规避基本的机器人检测。
*   **结论**: **中高可行性**。基础逻辑已就绪，但滑块验证对抗性较强（如通过率波动、新版验证码出现等），需要进一步验证在实际环境中的稳定性和成功率。

## 3. 下一步计划 (Deep Analysis & Verification)
尽管代码资产已存在，但要实现生产级全自动，仍需解决以下集成挑战：

1.  **OTP 客户端连通性验证**: 确认 `patoken_client.py` 在当前网络环境（非浏览器环境）下是否能稳定连接 PAIC OTP 服务。
2.  **滑块识别率测试**: 针对 EQC 实际出现的滑块类型进行反复测试，调整 OpenCV 参数或轨迹算法。
3.  **流程整合**: 将 OTP 获取与滑块处理无缝编排进 `playwright` 的异步流程中，处理可能出现的异常（如 OTP 过期、滑块多次失败重试）。

## 4. 目录结构规划
后续验证文档与测试代码将存放于 `docs/specific/eqc-full-automation/` 下。
