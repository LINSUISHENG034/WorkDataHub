"""
Infrastructure Layer

This layer provides reusable infrastructure services and utilities that support
domain logic without containing business rules themselves.

Architecture Decision: AD-010 - Infrastructure Layer & Pipeline Composition

Components:
- cleansing: Data cleansing registry and rules (migrated in Story 5.2)
- enrichment: Company ID resolution and enrichment services (Story 5.4)
- validation: Validation error handling and reporting utilities (Story 5.5)
- transforms: Standard pipeline transformation steps (Story 5.6)
- settings: Infrastructure configuration and loaders (Story 5.3)

Usage:
    from work_data_hub.infrastructure.enrichment import CompanyIdResolver
    from work_data_hub.infrastructure.transforms import Pipeline, MappingStep
"""

# Will be populated as components are added in subsequent stories
__all__: list[str] = []
