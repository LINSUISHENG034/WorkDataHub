EQC Auth OpenCV Module – Current Issues Report
Date: 2025-09-16

Scope
- File under investigation: src/work_data_hub/auth/eqc_auth_opencv.py
- Related helpers/tools:
  - scripts/demos/eqc_login_driver.py (semi‑auto driver that can fill creds successfully)
  - scripts/demos/record_eqc_login_flow.py (auto recorder; latest logs at logs/eqc_login_record/20250916-000932)
  - src/work_data_hub/auth/eqc_settings.py (.env loader)

Symptoms (as reported and reproduced)
- Auto fill: Module does not reliably fill username/password on the login page.
- Slider: Module does not auto-solve the Geetest slider after clicking login.
- Token capture: In some cases a token is captured immediately without an explicit login (likely due to session reuse or broad capture criteria). We partially addressed this with capture filtering and reset controls, but the core auto-login remains unstable.

Environment/Config Notes
- .env support is active via EQCAuthSettings (pydantic-settings). Relevant keys:
  EQC_LOGIN_URL, EQC_USERNAME, EQC_PASSWORD, EQC_OTP, EQC_AUTO_SLIDER,
  EQC_REUSE_SESSION, EQC_CLEAR_SESSION, EQC_RESET_STORAGE,
  EQC_STORAGE_STATE, EQC_CAPTURE_URL_SUBSTR.
- For clean runs, EQC_RESET_STORAGE=true and EQC_REUSE_SESSION=false should remove session influence.
- Login URL commonly used: https://eqc.pingan.com/#/login?redirect=%2Fhome

Reproduction Steps
1) Prepare .env (clean login):
   - EQC_LOGIN_URL=https://eqc.pingan.com/#/login?redirect=%2Fhome
   - EQC_USERNAME=<um>
   - EQC_PASSWORD=<pwd>
   - EQC_RESET_STORAGE=true
   - EQC_REUSE_SESSION=false
2) Run: uv run python scripts/demos/eqc_login_flow.py (choose enhanced), or call run_get_token() from eqc_auth_opencv.
3) Observe: inputs are not filled; after manual assist, the slider is not auto-solved.

Evidence Collected
- Recorder output at logs/eqc_login_record/20250916-000932 shows early navigations to #/login but no captured DOM-level click/input events (recorder aggregates via console bridge). That suggests our module likely clicks too early or targets elements that are not yet visible/attached.
- The separate driver (scripts/demos/eqc_login_driver.py) successfully fills credentials, using:
  - Explicit “account login” tab switch (get_by_text("账号登录"/"UM账号登录"/...))
  - Placeholder-first selectors (get_by_placeholder("平安集团UM账号"/"开机密码")) with relaxed CSS fallback.
  - Agreement checkbox click before login.

Current Hypotheses
1) Tab switch prerequisite not always satisfied
   - The module’s _fill_login_form attempts tab switch but may miss the actual tab label (variants), or runs before the tab is mounted/visible. As a result, username/password fields are not present when attempting to fill.

2) Timing/visibility race conditions
   - The app is SPA (Vue/React-like route /#/login). Elements appear after route transition. We might fill/click prior to state "visible"; add state="visible" waits.

3) Selector fragility
   - Password CSS in earlier versions depended on stateful classes (is-success/active). We replaced it with relaxed CSS but still rely on top-level page; if the login pane is nested in layers/dialogs, scoping may be required (container locator, or frame iframes are introduced in some variants).

4) Agreement checkbox gating login
   - If the agreement is not checked, the click on #loginBtn may be ignored. Our helper tries both label and checkbox; needs confirmation that it is present in current DOM.

5) Slider panel variance & image capture
   - Geetest fullbg may be rendered under a different canvas path, or temporarily hidden behind opacity/mask. Our code toggles .geetest_canvas_fullbg display, but some deployments use a single <canvas> or different nesting. Offset calculation degrades to single-image edge projection, which can be insufficient. Also, drag distance mapping may be off when device scale or CSS transforms apply.

6) Session/token capture side-effects
   - Even with URL filtering, if authenticated APIs fire early, token capture can happen before form interaction. Reset controls help (EQC_RESET_STORAGE/EQC_CLEAR_SESSION), but we should also gate on post-login element presence to assert login completion before returning.

Gaps/Unknowns
- Exact tab label/DOM for the current environment (may differ from "账号登录"/"UM账号登录").
- Whether the login form sits inside an iframe or shadow root in specific deployments (recorder didn’t surface iframes, but needs explicit check in module).
- Precise Geetest DOM in runtime (we have docs/company_id/EQC/login_page_elements.md with selectors; need to verify live version using recorder screenshots/snapshots when slider is shown).

Action Plan (Proposed)
1) Harden login flow:
   - Wait for URL to match .*#/login.* and for a stable container (e.g., .password-login) state="visible".
   - Tab switch retry: click any of ["账号登录","UM账号登录","账号","UM"] with wait_for_selector state="visible"; if still absent, re-check after minimal delay.
   - Use placeholder-first fill with .wait_for(state="visible") on inputs. On failure, widen CSS selector and log a screenshot + outerHTML snippet of the login section.
   - Ensure agreement checkbox: prefer label text; fallback to .el-checkbox__input/.el-checkbox__inner; after click, verify it has "is-checked" class.

2) Add deterministic debugging hooks (behind EQC_DEBUG=true):
   - Save step screenshots: before tab switch, after switch, after fill, after click.
   - Dump short DOM snapshots for the login container and geetest panel (.innerHTML truncated) into logs/eqc_debug/.
   - Log which selector path succeeded for each field.

3) Assert login completion before accepting token:
   - Gate the token_future resolution by requiring detection of a post-login element (e.g., absence of #loginBtn AND presence of a stable nav/search element). Only then accept token.

4) Slider robustness:
   - Wait for 'div.geetest_panel' (state=visible) before image capture.
   - Try both documented precise selectors and generic class fallbacks; if fullbg missing, attempt to extract the slice canvas and do template matching against the background.
   - Add device scale compensation via page.evaluate to read devicePixelRatio and adjust distance.
   - Add a tiny correction drag (±3px) after initial placement and re-check panel dismissal.

5) Explicit session control in code path:
   - At function entry: if EQC_RESET_STORAGE=true, remove storage_state file (already implemented).
   - Honor EQC_CLEAR_SESSION to ignore storage_state when creating context.
   - Only save storage_state after a confirmed login gate (see 3).

How To Reproduce Consistently (for future debugging)
1) Set in .env:
   EQC_LOGIN_URL=https://eqc.pingan.com/#/login?redirect=%2Fhome
   EQC_USERNAME=<um>
   EQC_PASSWORD=<pwd>
   EQC_RESET_STORAGE=true
   EQC_REUSE_SESSION=false
2) Run: uv run python scripts/demos/eqc_login_driver.py
   - Observe that this driver fills credentials successfully (baseline behavior).
3) Run: uv run python -c "from src.work_data_hub.auth.eqc_auth_opencv import run_get_token; print(run_get_token(180))"
   - Observe the module not filling or slider not solved.

Next Steps (Concrete Tasks)
- [ ] Add EQC_DEBUG toggles and step screenshots/DOM dumps to eqc_auth_opencv.py.
- [ ] Make tab switch deterministic with retries and confirm visibility.
- [ ] Replace plain waits with state="visible" and .wait_for() before fill/click.
- [ ] Enhance slider image capture with precise selectors from docs and fallback to slice-template matching.
- [ ] Add post-login gating before accepting token to avoid early capture.
- [ ] Add optional frame detection for slider/login panel (future‑proofing).
- [ ] Write an integration test stub that runs the flow in headed mode and asserts step-by-step checkpoints (skipped in CI, used locally).

Owners/References
- Code owners: Auth module maintainers
- Docs: docs/company_id/EQC/login_page_elements.md
- Last recorder run: logs/eqc_login_record/20250916-000932

