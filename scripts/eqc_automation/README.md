# EQC Auth OpenCV Module

> **Status: PENDING DEVELOPMENT**
>
> 本模块用于 EQC 登录的全自动化（包括自动填充凭据和滑块验证码识别）。
> 目前处于待开发状态，核心功能尚未稳定。
>
> **当前 Token 获取请使用**:
> ```bash
> cd E:/Projects/WorkDataHub && PYTHONPATH=src uv run python -c \
>   "from work_data_hub.io.auth.eqc_auth_handler import run_get_token; run_get_token(timeout_seconds=180, save_to_env=True)"
> ```
> 该命令会打开浏览器进行手动登录，Token 会自动保存到 `.env` 文件。

---

## Current Issues Report

**Date**: 2025-09-16
**Last Updated**: 2025-12-07

### Scope

- File under investigation: `scripts/eqc_automation/eqc_auth_opencv.py`
- Related helpers/tools:
  - `scripts/demos/eqc_login_driver.py` (semi-auto driver that can fill creds successfully)
  - `scripts/demos/record_eqc_login_flow.py` (auto recorder)
  - `scripts/eqc_automation/eqc_settings.py` (.env loader)

### Symptoms (as reported and reproduced)

- **Auto fill**: Module does not reliably fill username/password on the login page.
- **Slider**: Module does not auto-solve the Geetest slider after clicking login.
- **Token capture**: In some cases a token is captured immediately without an explicit login (likely due to session reuse or broad capture criteria).

### Environment/Config Notes

- `.env` support is active via `EQCAuthSettings` (pydantic-settings). Relevant keys:
  - `EQC_LOGIN_URL`, `EQC_USERNAME`, `EQC_PASSWORD`, `EQC_OTP`, `EQC_AUTO_SLIDER`
  - `EQC_REUSE_SESSION`, `EQC_CLEAR_SESSION`, `EQC_RESET_STORAGE`
  - `EQC_STORAGE_STATE`, `EQC_CAPTURE_URL_SUBSTR`
- For clean runs, `EQC_RESET_STORAGE=true` and `EQC_REUSE_SESSION=false` should remove session influence.
- Login URL commonly used: `https://eqc.pingan.com/#/login?redirect=%2Fhome`

---

## Future Development Plan

### Goal
实现 EQC 登录的全自动化，包括：
1. 自动填充 UM 账号和密码
2. 自动识别并解决 Geetest 滑块验证码
3. 自动捕获 Token 并保存到配置文件

### Key Tasks

- [ ] Add `EQC_DEBUG` toggles and step screenshots/DOM dumps
- [ ] Make tab switch deterministic with retries and confirm visibility
- [ ] Replace plain waits with `state="visible"` and `.wait_for()` before fill/click
- [ ] Enhance slider image capture with precise selectors and fallback to slice-template matching
- [ ] Add post-login gating before accepting token to avoid early capture
- [ ] Add optional frame detection for slider/login panel (future-proofing)
- [ ] Write an integration test stub that runs the flow in headed mode

### Technical Approach

1. **Harden login flow**:
   - Wait for URL to match `.*#/login.*` and for a stable container state="visible"
   - Tab switch retry with multiple label variants
   - Use placeholder-first fill with `.wait_for(state="visible")` on inputs

2. **Slider robustness**:
   - Wait for `div.geetest_panel` (state=visible) before image capture
   - Add device scale compensation via `page.evaluate` to read `devicePixelRatio`
   - Add correction drag (±3px) after initial placement

3. **Session control**:
   - Gate token acceptance on post-login element presence
   - Only save `storage_state` after confirmed login

---

## References

- Current manual auth handler: `src/work_data_hub/io/auth/eqc_auth_handler.py`
- Login page elements doc: `docs/company_id/EQC/login_page_elements.md`
