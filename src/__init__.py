"""
Compatibility package to support imports like ``src.work_data_hub``.

Pytest fixtures and legacy tooling import modules via the ``src`` namespace,
so we expose the namespace explicitly rather than relying on implicit namespace
package discovery.
"""

from . import work_data_hub  # re-export for type checkers  # type: ignore[attr-defined]

__all__ = ["work_data_hub"]
