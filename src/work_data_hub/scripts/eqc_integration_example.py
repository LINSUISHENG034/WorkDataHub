"""
Modern EQC integration example using new authentication system.

This module demonstrates how to use the new EQC authentication handler
in the modern WorkDataHub architecture, replacing legacy manual token management
with automated browser-based authentication.

Example usage:
    from src.work_data_hub.scripts.eqc_integration_example import EqcIntegrationExample

    example = EqcIntegrationExample()
    await example.authenticate_and_search("中国平安")
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from src.work_data_hub.auth.eqc_auth_handler import get_auth_token_interactively
from src.work_data_hub.config.settings import get_settings

logger = logging.getLogger(__name__)


class EqcIntegrationExample:
    """
    Example integration showing how to use EQC authentication in new architecture.

    This class demonstrates the modern approach to EQC data collection,
    replacing the legacy manual token extraction workflow with automated
    browser-based authentication and clean async API patterns.
    """

    def __init__(self):
        """Initialize the EQC integration with settings."""
        self.settings = get_settings()
        self.token: Optional[str] = None
        self.session_info: Dict = {}

    async def authenticate_interactive(self, timeout_seconds: int = 600) -> bool:
        """
        Perform interactive authentication to obtain EQC token.

        Args:
            timeout_seconds: Maximum time to wait for authentication

        Returns:
            True if authentication successful, False otherwise

        Example:
            >>> integration = EqcIntegrationExample()
            >>> success = await integration.authenticate_interactive()
            >>> if success:
            ...     print("Ready to perform EQC queries")
        """
        logger.info("Starting interactive EQC authentication...")

        try:
            # Use the new authentication handler
            token = await get_auth_token_interactively(timeout_seconds=timeout_seconds)

            if token:
                self.token = token
                self.session_info = {
                    "authenticated_at": datetime.now(),
                    "token_length": len(token),
                    "auth_method": "interactive_browser",
                }
                logger.info(
                    f"Authentication successful! Token length: {len(token)} characters"
                )
                return True
            else:
                logger.error("Authentication failed - no token received")
                return False

        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            return False

    def get_session_info(self) -> Dict:
        """
        Get current session information.

        Returns:
            Dictionary with session details including authentication status
        """
        base_info = {
            "authenticated": self.token is not None,
            "token_present": bool(self.token),
        }

        if self.session_info:
            base_info.update(self.session_info)

        return base_info

    async def simulate_eqc_search(self, company_name: str) -> Dict:
        """
        Simulate an EQC search operation using the authenticated token.

        Note: This is a demonstration function. In real implementation,
        you would integrate with actual EQC API endpoints.

        Args:
            company_name: Company name to search for

        Returns:
            Simulated search result data

        Example:
            >>> integration = EqcIntegrationExample()
            >>> await integration.authenticate_interactive()
            >>> result = await integration.simulate_eqc_search("中国平安")
            >>> print(f"Found company: {result['company_name']}")
        """
        if not self.token:
            raise ValueError(
                "Authentication required. Call authenticate_interactive() first."
            )

        logger.info(f"Simulating EQC search for: {company_name}")

        # Simulate EQC API call structure
        simulated_result = {
            "search_query": company_name,
            "company_name": company_name,
            "company_id": "601318",  # Simulated
            "unified_code": "91110000100006172",  # Simulated
            "search_timestamp": datetime.now().isoformat(),
            "token_used": f"{self.token[:8]}...",  # Show first 8 chars only
            "status": "success",
            "data_source": "eqc_simulation",
        }

        # In real implementation, you would:
        # 1. Use self.token in HTTP headers: {'token': self.token}
        # 2. Make actual requests to EQC API endpoints
        # 3. Parse and validate response data
        # 4. Handle errors and retries

        logger.info(f"Search completed for {company_name}")
        return simulated_result

    async def batch_search_example(self, company_names: List[str]) -> List[Dict]:
        """
        Example of batch processing multiple companies.

        Args:
            company_names: List of company names to search

        Returns:
            List of search results
        """
        if not self.token:
            raise ValueError(
                "Authentication required. Call authenticate_interactive() first."
            )

        logger.info(f"Starting batch search for {len(company_names)} companies")

        results = []
        for company_name in company_names:
            try:
                result = await self.simulate_eqc_search(company_name)
                results.append(result)

                # Rate limiting - wait between requests in real implementation
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error searching for {company_name}: {e}")
                results.append(
                    {"search_query": company_name, "status": "error", "error": str(e)}
                )

        logger.info(f"Batch search completed: {len(results)} results")
        return results


# Example usage functions for demonstration


async def example_single_search():
    """Example: Single company search with interactive authentication."""
    print("🔍 Single Company Search Example")
    print("=" * 50)

    integration = EqcIntegrationExample()

    # Authenticate
    print("Step 1: Authenticating...")
    auth_success = await integration.authenticate_interactive(timeout_seconds=60)

    if not auth_success:
        print("❌ Authentication failed")
        return

    # Show session info
    session = integration.get_session_info()
    print("✅ Authentication successful!")
    print(f"   Authenticated at: {session.get('authenticated_at')}")
    print(f"   Token length: {session.get('token_length')} characters")

    # Perform search
    print("\nStep 2: Searching for company...")
    try:
        result = await integration.simulate_eqc_search("中国平安保险股份有限公司")
        print("✅ Search successful!")
        print(f"   Company: {result['company_name']}")
        print(f"   Company ID: {result['company_id']}")
        print(f"   Unified Code: {result['unified_code']}")

    except Exception as e:
        print(f"❌ Search failed: {e}")


async def example_batch_search():
    """Example: Batch company search with authentication."""
    print("📊 Batch Company Search Example")
    print("=" * 50)

    integration = EqcIntegrationExample()

    # Authenticate
    print("Step 1: Authenticating...")
    auth_success = await integration.authenticate_interactive(timeout_seconds=60)

    if not auth_success:
        print("❌ Authentication failed")
        return

    # Batch search
    companies = [
        "中国平安保险股份有限公司",
        "招商银行股份有限公司",
        "中国建设银行股份有限公司",
    ]

    print(f"\nStep 2: Searching for {len(companies)} companies...")
    results = await integration.batch_search_example(companies)

    print("✅ Batch search completed!")
    print(f"   Total results: {len(results)}")
    for i, result in enumerate(results, 1):
        status = result.get("status", "unknown")
        company = result.get("search_query", "N/A")
        print(f"   {i}. {company}: {status}")


def run_single_search_example():
    """Synchronous wrapper for single search example."""
    asyncio.run(example_single_search())


def run_batch_search_example():
    """Synchronous wrapper for batch search example."""
    asyncio.run(example_batch_search())


if __name__ == "__main__":
    print("🚀 EQC Integration Examples")
    print("Choose an example to run:")
    print("1. Single company search")
    print("2. Batch company search")
    print("3. Exit")

    choice = input("Enter choice (1-3): ").strip()

    if choice == "1":
        run_single_search_example()
    elif choice == "2":
        run_batch_search_example()
    elif choice == "3":
        print("👋 Goodbye!")
    else:
        print("❌ Invalid choice")
