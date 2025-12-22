#!/usr/bin/env python3
"""
Script to validate the EQC API token configured in the environment.

Usage:
    python scripts/validation/EQC/check_token.py
"""

import logging
import sys

from work_data_hub.config.settings import get_settings
from work_data_hub.infrastructure.enrichment.eqc_provider import validate_eqc_token

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main():
    try:
        settings = get_settings()
        token = settings.eqc_token
        base_url = settings.eqc_base_url

        if not token:
            logger.error(
                "❌ Error: WDH_EQC_TOKEN is not set in environment or .wdh_env file."
            )
            sys.exit(1)

        print(f"Checking token against {base_url}...")
        is_valid = validate_eqc_token(token, base_url)

        if is_valid:
            print("✅ Token is VALID.")
            sys.exit(0)
        else:
            print("❌ Token is INVALID or EXPIRED.")
            print("Run the following command to refresh it:")
            print("python -m work_data_hub.io.auth --capture --save")
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Unexpected error validating token: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
