# EQC Authentication Integration Guide

This document explains how to use the new EQC authentication system in the modern WorkDataHub architecture.

## Overview

The EQC authentication module provides automated browser-based token acquisition, eliminating the need for manual token extraction from browser developer tools.

## Features

- **Interactive Browser Authentication**: Automated browser launch and token capture
- **Async/Sync API Support**: Both async and synchronous interfaces
- **Comprehensive Error Handling**: Timeout, browser, and authentication error handling
- **Type-Safe Models**: Pydantic v2 validation for all authentication data
- **Integration Ready**: Designed for seamless integration into existing workflows

## Quick Start

### 1. Basic Authentication

```python
from src.work_data_hub.auth.eqc_auth_handler import run_get_token

# Simple synchronous authentication
token = run_get_token(timeout_seconds=300)
if token:
    print(f"Got token: {token[:8]}...")
else:
    print("Authentication failed")
```

### 2. Async Authentication

```python
import asyncio
from src.work_data_hub.auth.eqc_auth_handler import get_auth_token_interactively

async def main():
    token = await get_auth_token_interactively(timeout_seconds=300)
    if token:
        print(f"Got token: {token[:8]}...")

asyncio.run(main())
```

### 3. Authentication with Validation

```python
from src.work_data_hub.auth.eqc_auth_handler import run_get_token_with_validation

result = run_get_token_with_validation(timeout_seconds=300)
if result:
    print(f"Token: {result.token[:8]}...")
    print(f"Captured at: {result.captured_at}")
    print(f"Source: {result.source_url}")
```

## Integration Examples

### Modern Architecture Integration

See `src/work_data_hub/scripts/eqc_integration_example.py` for a complete example:

```python
from src.work_data_hub.scripts.eqc_integration_example import EqcIntegrationExample

# Create integration instance
integration = EqcIntegrationExample()

# Authenticate interactively
await integration.authenticate_interactive()

# Perform searches
result = await integration.simulate_eqc_search("中国平安")
```

### Running Examples

```bash
# Run the integration example
uv run python -m src.work_data_hub.scripts.eqc_integration_example

# Run integration tests
uv run python test_auth_integration.py
```

## Configuration

The authentication system respects the standard WorkDataHub configuration:

```python
from src.work_data_hub.config.settings import get_settings

settings = get_settings()
# Authentication timeout can be configured via WDH_AUTH_TIMEOUT_SECONDS
```

## Error Handling

The system provides specific exceptions for different error scenarios:

```python
from src.work_data_hub.auth.models import (
    AuthenticationError,
    AuthTimeoutError,
    BrowserError
)
from src.work_data_hub.auth.eqc_auth_handler import get_auth_token_interactively

try:
    token = await get_auth_token_interactively()
except AuthTimeoutError:
    print("User didn't complete login in time")
except BrowserError:
    print("Browser failed to launch or operate")
except AuthenticationError:
    print("General authentication failure")
```

## Migration from Legacy

If you're migrating from legacy EQC integration:

1. **Replace manual token input** with `run_get_token()`
2. **Use async patterns** where possible with `get_auth_token_interactively()`
3. **Add proper error handling** for authentication failures
4. **Keep legacy code unchanged** - this is an addition, not a replacement

## Testing

Run the test suite to verify functionality:

```bash
# Unit tests
uv run pytest tests/auth/ -v

# Integration test (requires manual interaction)
uv run python test_auth_integration.py
```

## Architecture

The authentication module follows WorkDataHub conventions:

- **Models**: `src/work_data_hub/auth/models.py` - Pydantic data models
- **Handler**: `src/work_data_hub/auth/eqc_auth_handler.py` - Core authentication logic
- **Tests**: `tests/auth/` - Unit and integration tests
- **Examples**: `src/work_data_hub/scripts/` - Usage examples

## Security Notes

- Tokens are never logged in full (only first 8 characters for debugging)
- Browser sessions are properly cleaned up after authentication
- No persistent token storage (tokens must be re-acquired for each session)

## Troubleshooting

### Browser Won't Launch
- Ensure Playwright browsers are installed: `uv run playwright install`
- Check that Chrome/Chromium is accessible

### Authentication Timeouts
- Increase timeout: `get_auth_token_interactively(timeout_seconds=600)`
- Ensure you perform a search action after logging in to trigger token capture

### Network Issues
- Check proxy settings if in corporate environment
- Verify https://eqc.pingan.com/ is accessible