"""Tests for EQC authentication handler."""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from work_data_hub.io.auth.models import (
    AuthTokenResult,
    AuthenticationError,
    AuthTimeoutError,
    BrowserError,
)
from work_data_hub.io.auth.eqc_auth_handler import (
    get_auth_token_interactively,
    get_auth_token_with_validation,
    run_get_token,
    run_get_token_with_validation,
)


class TestAuthTokenResult:
    """Test AuthTokenResult model validation."""

    def test_valid_token_creation(self):
        """Test creating AuthTokenResult with valid token."""
        result = AuthTokenResult(
            token="valid_token_12345678901234567890",
            source_url="https://eqc.pingan.com/",
        )
        assert result.token == "valid_token_12345678901234567890"
        assert result.source_url == "https://eqc.pingan.com/"
        assert result.validated is False
        assert isinstance(result.captured_at, datetime)

    def test_token_too_short_raises_error(self):
        """Test that tokens shorter than 20 characters are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AuthTokenResult(token="short", source_url="https://example.com")

        assert "at least 20 characters" in str(exc_info.value)

    def test_token_stripped_of_whitespace(self):
        """Test that tokens are stripped of leading/trailing whitespace."""
        result = AuthTokenResult(
            token="  valid_token_12345678901234567890  ",
            source_url="https://example.com",
        )
        assert result.token == "valid_token_12345678901234567890"

    def test_empty_token_raises_error(self):
        """Test that empty tokens are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AuthTokenResult(token="", source_url="https://example.com")

        assert "at least 20 characters" in str(exc_info.value)

    def test_token_max_length_validation(self):
        """Test token maximum length validation."""
        # Create a token that's exactly 100 characters
        valid_token = "a" * 100
        result = AuthTokenResult(token=valid_token, source_url="https://example.com")
        assert len(result.token) == 100

        # Create a token that's too long
        with pytest.raises(ValidationError):
            AuthTokenResult(token="a" * 101, source_url="https://example.com")


class TestCustomExceptions:
    """Test custom exception classes."""

    def test_authentication_error(self):
        """Test AuthenticationError can be raised and caught."""
        with pytest.raises(AuthenticationError) as exc_info:
            raise AuthenticationError("Test auth error")
        assert str(exc_info.value) == "Test auth error"

    def test_auth_timeout_error_inherits_from_auth_error(self):
        """Test that AuthTimeoutError inherits from AuthenticationError."""
        with pytest.raises(AuthenticationError):
            raise AuthTimeoutError("Timeout occurred")

    def test_browser_error_inherits_from_auth_error(self):
        """Test that BrowserError inherits from AuthenticationError."""
        with pytest.raises(AuthenticationError):
            raise BrowserError("Browser failed")


class TestEqcAuthHandler:
    """Test EQC authentication handler functions."""

    @pytest.mark.asyncio
    async def test_successful_token_capture(self):
        """Test successful token capture via network interception."""
        with patch(
            "src.work_data_hub.auth.eqc_auth_handler.async_playwright"
        ) as mock_playwright:
            # Mock the Playwright components
            mock_playwright_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            # Set up the mock chain
            mock_playwright.return_value.__aenter__.return_value = (
                mock_playwright_instance
            )
            mock_playwright_instance.chromium.launch.return_value = mock_browser
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page

            # Mock the route handler to simulate token capture
            captured_token = "captured_test_token_1234567890"

            async def mock_route_handler(route_pattern, handler):
                """Simulate calling the handler with a mock route containing our token."""
                mock_route = AsyncMock()
                mock_request = MagicMock()
                mock_request.url = (
                    "https://eqc.pingan.com/kg-api-hfd/api/search/?key=test"
                )
                mock_request.headers = {"token": captured_token}
                mock_route.request = mock_request
                mock_route.continue_ = AsyncMock()

                # Call the handler to trigger token capture
                await handler(mock_route)

            mock_context.route = mock_route_handler

            # Test the function
            result = await get_auth_token_interactively(timeout_seconds=1)

            # Verify the result
            assert result == captured_token

            # Verify Playwright was called correctly
            mock_playwright_instance.chromium.launch.assert_called_once_with(
                headless=False
            )
            mock_browser.new_context.assert_called_once()
            mock_context.new_page.assert_called_once()
            mock_page.goto.assert_called_once_with(
                "https://eqc.pingan.com/", wait_until="domcontentloaded"
            )
            mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_authentication_timeout(self):
        """Test timeout handling when user doesn't complete login."""
        with patch(
            "src.work_data_hub.auth.eqc_auth_handler.async_playwright"
        ) as mock_playwright:
            # Mock browser that never captures token
            mock_playwright_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            mock_playwright.return_value.__aenter__.return_value = (
                mock_playwright_instance
            )
            mock_playwright_instance.chromium.launch.return_value = mock_browser
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page
            mock_context.route = AsyncMock()  # No token will be captured

            # Test that timeout raises AuthTimeoutError
            with pytest.raises(AuthTimeoutError) as exc_info:
                await get_auth_token_interactively(
                    timeout_seconds=0.1
                )  # Very short timeout

            assert "Authentication timed out after 0.1 seconds" in str(exc_info.value)
            mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_browser_error_handling(self):
        """Test handling of browser-related errors."""
        with patch(
            "src.work_data_hub.auth.eqc_auth_handler.async_playwright"
        ) as mock_playwright:
            # Mock playwright to raise an exception during browser launch
            mock_playwright_instance = AsyncMock()
            mock_playwright.return_value.__aenter__.return_value = (
                mock_playwright_instance
            )
            mock_playwright_instance.chromium.launch.side_effect = Exception(
                "Browser launch failed"
            )

            with pytest.raises(BrowserError) as exc_info:
                await get_auth_token_interactively(timeout_seconds=1)

            assert "Browser operation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_request_interception_continues_non_target_requests(self):
        """Test that non-target requests are properly continued."""
        with patch(
            "src.work_data_hub.auth.eqc_auth_handler.async_playwright"
        ) as mock_playwright:
            mock_playwright_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            mock_playwright.return_value.__aenter__.return_value = (
                mock_playwright_instance
            )
            mock_playwright_instance.chromium.launch.return_value = mock_browser
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page

            # Track the route handler
            route_handler = None

            async def capture_route_handler(route_pattern, handler):
                nonlocal route_handler
                route_handler = handler

            mock_context.route = capture_route_handler

            # Start the authentication process
            task = asyncio.create_task(
                get_auth_token_interactively(timeout_seconds=0.5)
            )

            # Give it a moment to set up
            await asyncio.sleep(0.1)

            # Simulate a non-target request
            mock_route = AsyncMock()
            mock_request = MagicMock()
            mock_request.url = "https://example.com/some-other-api"
            mock_request.headers = {}
            mock_route.request = mock_request
            mock_route.continue_ = AsyncMock()

            if route_handler:
                await route_handler(mock_route)
                mock_route.continue_.assert_called_once()

            # Cancel the task to avoid timeout
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_get_auth_token_with_validation_success(self):
        """Test get_auth_token_with_validation returns AuthTokenResult."""
        with patch(
            "src.work_data_hub.auth.eqc_auth_handler.get_auth_token_interactively"
        ) as mock_get_token:
            test_token = "test_token_1234567890123456"
            mock_get_token.return_value = test_token

            result = await get_auth_token_with_validation(timeout_seconds=1)

            assert isinstance(result, AuthTokenResult)
            assert result.token == test_token
            assert result.source_url == "https://eqc.pingan.com/"
            assert result.validated is False
            assert isinstance(result.captured_at, datetime)

    @pytest.mark.asyncio
    async def test_get_auth_token_with_validation_failure(self):
        """Test get_auth_token_with_validation returns None on failure."""
        with patch(
            "src.work_data_hub.auth.eqc_auth_handler.get_auth_token_interactively"
        ) as mock_get_token:
            mock_get_token.return_value = None

            result = await get_auth_token_with_validation(timeout_seconds=1)

            assert result is None

    def test_run_get_token_sync_wrapper(self):
        """Test synchronous wrapper function."""
        with patch("src.work_data_hub.auth.eqc_auth_handler.asyncio.run") as mock_run:
            test_token = "sync_test_token_1234567890"
            mock_run.return_value = test_token

            result = run_get_token(timeout_seconds=1)

            assert result == test_token
            mock_run.assert_called_once()

    def test_run_get_token_with_validation_sync_wrapper(self):
        """Test synchronous wrapper for validation function."""
        with patch("src.work_data_hub.auth.eqc_auth_handler.asyncio.run") as mock_run:
            test_result = AuthTokenResult(
                token="sync_validation_token_1234567890",
                source_url="https://eqc.pingan.com/",
            )
            mock_run.return_value = test_result

            result = run_get_token_with_validation(timeout_seconds=1)

            assert isinstance(result, AuthTokenResult)
            assert result.token == "sync_validation_token_1234567890"
            mock_run.assert_called_once()

    def test_sync_wrapper_error_handling(self):
        """Test error handling in synchronous wrappers."""
        with patch("src.work_data_hub.auth.eqc_auth_handler.asyncio.run") as mock_run:
            mock_run.side_effect = Exception("Async execution failed")

            result = run_get_token(timeout_seconds=1)
            assert result is None

            result_with_validation = run_get_token_with_validation(timeout_seconds=1)
            assert result_with_validation is None
