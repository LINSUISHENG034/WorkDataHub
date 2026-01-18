"""Customer Master Data Management (Customer MDM) service layer.

Story 7.6: Customer Master Data Management Epic
Provides services for customer domain data synchronization and management.
"""

from work_data_hub.customer_mdm.contract_sync import sync_contract_status

__all__ = ["sync_contract_status"]
