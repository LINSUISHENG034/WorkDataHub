"""
Utility functions for EQC connector.
"""

def sanitize_url_for_logging(url: str) -> str:
    """
    Sanitize URL for logging by removing token parameters.

    Args:
        url: Original URL that may contain sensitive data

    Returns:
        Sanitized URL safe for logging
    """
    # Remove any token-like query parameters for security
    if "token=" in url:
        return url.split("token=")[0] + "[TOKEN_SANITIZED]"
    return url
