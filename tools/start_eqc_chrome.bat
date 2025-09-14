@echo off
echo ============================================================
echo         EQC 专用 Chrome 浏览器启动器
echo ============================================================
echo.
echo 正在启动Chrome浏览器（调试模式）...
echo.

REM 创建独立的用户数据目录
set CHROME_USER_DIR=%TEMP%\chrome_eqc_%RANDOM%

REM 启动Chrome并打开EQC
start chrome.exe --remote-debugging-port=9222 --user-data-dir="%CHROME_USER_DIR%" https://eqc.pingan.com/

echo ✅ Chrome已启动！
echo.
echo 📋 请按以下步骤操作：
echo.
echo   1. 在浏览器中登录EQC平台
echo      - 输入用户名和密码
echo      - 完成手机验证码
echo      - 完成滑动验证
echo.
echo   2. 登录成功后，保持浏览器开启
echo.
echo   3. 运行Python程序会自动获取token
echo      uv run python tools/eqc_cdp_client.py
echo.
echo ⚠️ 注意：请勿关闭此窗口和浏览器！
echo.
pause