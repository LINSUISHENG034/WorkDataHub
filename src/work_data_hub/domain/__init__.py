"""WorkDataHub domain layer (Story 1.6 - Clean Architecture boundaries).

The domain package hosts pure business logic such as the Story 1.5 pipeline
contracts (`work_data_hub.domain.pipelines.types` and `.core`). Domain modules
may depend on the Python standard library, pandas, or pydantic only; they must
never import from `work_data_hub.io` or `work_data_hub.orchestration`.

I/O and orchestration concerns inject their collaborators (for example, Dagster
jobs pass concrete reader/loader implementations plus Story 1.5 pipeline steps
into domain workflows) so that the dependency direction always flows inward.
"""
