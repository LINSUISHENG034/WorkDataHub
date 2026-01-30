"""Integration tests for Customer Master Data Management (Customer MDM) system.

Story 7.6-10: Integration Testing & Documentation
Tests the complete Customer MDM pipeline:
- Contract Status Sync (Story 7.6-6)
- Monthly Snapshot Refresh (Story 7.6-7)
- Post-ETL Hook Chain (Stories 7.6-6, 7.6-7)
- BI Star Schema Views (Story 7.6-8)
- Trigger Functionality (Story 7.6-9)

Run via: pytest tests/integration/customer_mdm/ -v
Or with marker: pytest -m integration tests/integration/customer_mdm/
"""
