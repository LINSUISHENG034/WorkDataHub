"""Post-ETL hook infrastructure for automatic data synchronization.

Story 7.6-6: Contract Status Sync (Post-ETL Hook)
Provides a registry-based pattern for running cleanup, enrichment, or
synchronization tasks after domain ETL completion.

Hook Pattern:
  - Hooks are registered in POST_ETL_HOOKS list
  - Each hook specifies which domains trigger it
  - Hooks run after successful domain ETL completion
  - Execution can be skipped via --no-post-hooks flag

Example Usage:
    # Register a new hook
    POST_ETL_HOOKS.append(
        PostEtlHook(
            name="my_sync_feature",
            domains=["my_domain"],
            hook_fn=my_sync_function,
        )
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from structlog import get_logger

logger = get_logger(__name__)


# Import contract sync function (Story 7.6-6)
def _sync_contract_status_hook(domain: str, period: str | None) -> None:
    """Post-ETL hook wrapper for contract status sync.

    Wraps the customer_mdm.sync_contract_status function to match
    the PostEtlHook signature.

    Args:
        domain: Domain name (should be 'annuity_performance')
        period: Period string (currently unused, syncs all available data)
    """
    from work_data_hub.customer_mdm import sync_contract_status

    logger.info("Triggering contract status sync from post-ETL hook")

    result = sync_contract_status(period=period, dry_run=False)

    logger.info(
        "Contract status sync completed",
        inserted=result["inserted"],
        updated=result["updated"],
        total=result["total"],
    )


@dataclass
class PostEtlHook:
    """A hook that runs after ETL completion for a domain.

    Attributes:
        name: Unique identifier for this hook
        domains: List of domain names that trigger this hook
        hook_fn: Function to execute with signature
            (domain: str, period: str | None) -> None
    """

    name: str
    domains: List[str]
    hook_fn: Callable[[str, str | None], None]


# Import snapshot refresh function (Story 7.6-7)
def _snapshot_refresh_hook(domain: str, period: str | None) -> None:
    """Post-ETL hook wrapper for monthly snapshot refresh.

    Runs AFTER contract_status_sync to ensure fresh contract data is available.

    Args:
        domain: Domain name (should be 'annuity_performance')
        period: Period string in YYYYMM format
    """
    from work_data_hub.customer_mdm import refresh_monthly_snapshot

    logger.info("Triggering monthly snapshot refresh from post-ETL hook")

    result = refresh_monthly_snapshot(period=period, dry_run=False)

    logger.info(
        "Monthly snapshot refresh completed",
        upserted=result["upserted"],
        total=result["total"],
    )


# Registry of post-ETL hooks
# IMPORTANT: Hook execution order follows list order.
# contract_status_sync MUST run before snapshot_refresh
POST_ETL_HOOKS: List[PostEtlHook] = [
    # Hook registration for Story 7.6-6: Contract Status Sync
    # Triggers after annuity_performance domain ETL completes
    PostEtlHook(
        name="contract_status_sync",
        domains=["annuity_performance"],
        hook_fn=_sync_contract_status_hook,
    ),
    # Hook registration for Story 7.6-7: Monthly Snapshot Refresh
    # Must run AFTER contract_status_sync (order matters)
    PostEtlHook(
        name="snapshot_refresh",
        domains=["annuity_performance"],
        hook_fn=_snapshot_refresh_hook,
    ),
]


def run_post_etl_hooks(domain: str, period: str | None) -> None:
    """Execute all registered hooks for the given domain.

    Hooks are executed in registration order. If a hook fails, it logs
    the error but continues with remaining hooks.

    Args:
        domain: Domain name that just completed ETL
        period: Period string (YYYYMM format) for the ETL run

    Example:
        >>> run_post_etl_hooks(domain="annuity_performance", period="202411")
        [INFO] Executing 1 post-ETL hooks for domain annuity_performance
        [INFO] Running hook: contract_status_sync
        [INFO] Contract status sync completed: inserted=1523, total=1523
    """
    matching_hooks = [hook for hook in POST_ETL_HOOKS if domain in hook.domains]

    if not matching_hooks:
        logger.debug("No post-ETL hooks registered for domain", domain=domain)
        return

    logger.info(
        "Executing post-ETL hooks",
        domain=domain,
        period=period,
        hook_count=len(matching_hooks),
    )

    for hook in matching_hooks:
        logger.info("Running post-ETL hook", hook_name=hook.name, domain=domain)

        try:
            hook.hook_fn(domain, period)
            logger.info(
                "Post-ETL hook completed",
                hook_name=hook.name,
                domain=domain,
            )
        except Exception as e:
            logger.error(
                "Post-ETL hook failed",
                hook_name=hook.name,
                domain=domain,
                error=str(e),
                exc_info=True,
            )
            # Continue with remaining hooks even if this one failed


def register_hook(hook: PostEtlHook) -> None:
    """Register a new post-ETL hook.

    Args:
        hook: PostEtlHook instance to register

    Raises:
        ValueError: If a hook with the same name already exists
    """
    existing_names = {h.name for h in POST_ETL_HOOKS}
    if hook.name in existing_names:
        raise ValueError(f"Hook already registered: {hook.name}")

    POST_ETL_HOOKS.append(hook)
    logger.info("Registered post-ETL hook", hook_name=hook.name, domains=hook.domains)
