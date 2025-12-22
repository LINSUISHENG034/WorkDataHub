"""
Auth utilities for ETL CLI.

Story 7.4: CLI Layer Modularization - Token validation and refresh utilities.
"""

import os
def _validate_and_refresh_token(auto_refresh: bool = True) -> bool:
    """
    Validate EQC token at CLI startup and auto-refresh if invalid.

    Story 6.2-P11 T3.1-T3.2: Pre-check Token validity before ETL execution.
    If token is invalid and auto_refresh is True, triggers auto-QR login flow.

    Args:
        auto_refresh: If True, auto-refresh token when validation fails.

    Returns:
        True if token is valid (or was successfully refreshed), False otherwise.
    """
    from work_data_hub.config.settings import get_settings
    from work_data_hub.infrastructure.enrichment.eqc_provider import validate_eqc_token

    try:
        settings = get_settings()
        token = settings.eqc_token
        base_url = settings.eqc_base_url

        if not token:
            print("⚠️  No EQC token configured (WDH_EQC_TOKEN not set)")
            if not auto_refresh:
                print("   Continuing without token (EQC lookup will be disabled)")
                return True
            print("   Attempting to refresh token via QR login...")
            return _trigger_token_refresh()

        # Validate existing token
        print("🔐 Validating EQC token...", end=" ", flush=True)
        if validate_eqc_token(token, base_url):
            print("✅ Token valid")
            return True

        # Token is invalid
        print("❌ Token invalid/expired")

        if not auto_refresh:
            print("⚠️  Auto-refresh disabled (--no-auto-refresh-token)")
            print("   Run: python -m work_data_hub.cli auth refresh")
            return True  # Continue without valid token

        print("   Attempting to refresh token via QR login...")
        return _trigger_token_refresh()

    except Exception as e:
        print(f"⚠️  Token validation error: {e}")
        return True  # Continue anyway to avoid blocking pipeline


def _trigger_token_refresh() -> bool:
    """Trigger automatic token refresh via QR login."""
    try:
        from work_data_hub.io.auth.auto_eqc_auth import run_get_token_auto_qr

        token = run_get_token_auto_qr(save_to_env=True, timeout_seconds=180)
        if token:
            print("✅ Token refreshed successfully")
            # Make the refreshed token effective in the current process as well.
            # Settings are cached (lru_cache), so we must clear it to re-read `.wdh_env`.
            os.environ["WDH_EQC_TOKEN"] = token
            try:
                from work_data_hub.config.settings import get_settings

                get_settings.cache_clear()
            except Exception:
                # Best-effort; even if cache clear fails, the token is persisted to `.wdh_env`.
                pass
            return True
        else:
            print("❌ Token refresh failed")
            print("   Please run manually: python -m work_data_hub.cli auth refresh")
            return False
    except Exception as e:
        print(f"❌ Token refresh error: {e}")
        return False
