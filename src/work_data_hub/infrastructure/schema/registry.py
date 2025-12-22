"""Domain schema registry management for WorkDataHub.

Story 7.5: Domain Registry Pre-modularization
Extracted from domain_registry.py for clean separation of concerns.
"""

from __future__ import annotations

from typing import Dict, List

from .core import DomainSchema


_DOMAIN_REGISTRY: Dict[str, DomainSchema] = {}


def register_domain(schema: DomainSchema) -> None:
    """Register a domain schema in the global registry."""
    if schema.domain_name in _DOMAIN_REGISTRY:
        raise ValueError(
            f"Domain '{schema.domain_name}' is already registered. "
            "Use a different domain_name or unregister first."
        )
    _DOMAIN_REGISTRY[schema.domain_name] = schema


def get_domain(name: str) -> DomainSchema:
    """Retrieve a domain schema from the registry by name."""
    if name not in _DOMAIN_REGISTRY:
        available = list(_DOMAIN_REGISTRY.keys())
        raise KeyError(f"Domain '{name}' not found in registry. Available: {available}")
    return _DOMAIN_REGISTRY[name]


def list_domains() -> List[str]:
    """List all registered domain names."""
    return sorted(_DOMAIN_REGISTRY.keys())


def get_composite_key(domain_name: str) -> List[str]:
    """Get the composite key for a domain."""
    return get_domain(domain_name).composite_key


def get_delete_scope_key(domain_name: str) -> List[str]:
    """Get the delete scope key for a domain."""
    return get_domain(domain_name).delete_scope_key


__all__ = [
    "register_domain",
    "get_domain",
    "list_domains",
    "get_composite_key",
    "get_delete_scope_key",
]
