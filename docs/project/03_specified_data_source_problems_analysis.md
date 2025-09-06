The new architecture is not only capable of addressing the specified data source problems but is fundamentally designed to eliminate the root causes of such issues.

Here is a detailed breakdown of how the new architecture effectively solves each of the identified problems:

---

### 1. Problem: Data source filenames may change and can only be identified by keywords.

- __Legacy System Flaw:__ The current system, as seen in `legacy/annuity_hub/main.py`, relies on a rigid and fragile file discovery mechanism. The line `matching_handlers = [item for item in handlers if item['keyword'] in file.name]` demonstrates that the core logic depends on a simple substring match between a hardcoded keyword and the filename. This approach is not resilient to changes in naming conventions and makes adding new data sources a code-level change.

- __New Architecture Solution:__ The proposed architecture addresses this through the __`DataSource Connector`__ and __`Workflow Orchestrator`__ (e.g., Dagster) components.

  - __Decoupled Configuration:__ Instead of hardcoding keywords in the application logic, the mapping between data sources, their identification patterns, and the corresponding processing logic will be defined in external configuration files (e.g., YAML).
  - __Flexible Identification:__ The `DataSource Connector` for file systems will be configured to use more robust identification methods, such as regular expressions or glob patterns, defined in the configuration. For example, a configuration entry could specify `pattern: "*受托业绩*.xlsx"` to reliably find the correct file.
  - __Centralized Orchestration:__ The Workflow Orchestrator will read this configuration and dynamically trigger the correct connector and subsequent processing steps.

- __Conclusion:__ This declarative, configuration-driven approach makes the system resilient to filename variations. Adding or modifying data source identification rules becomes a simple configuration update, requiring no changes to the core application code, thus improving maintainability and agility.

### 2. Problem: The same data source may be updated and stored in different versioned directories (e.g., V1, V2), requiring the latest version to be used.

- __Legacy System Flaw:__ The analysis of `legacy/annuity_hub/common_utils/common_utils.py` and `main.py` confirms that the existing file discovery function (`get_valid_files`) recursively scans a root directory and returns *all* matching files. It has no concept of versioning. This means if `V1` and `V2` directories exist, the system would incorrectly process data from both, leading to data duplication and corruption.

- __New Architecture Solution:__ The **`DataSource Connector`** is designed to handle this explicitly.
  - __Intelligent Version Discovery:__ The connector can be configured with a version-aware scanning strategy. For example, it can be instructed to scan a base path, identify all subdirectories matching a version pattern (e.g., `V\d+`), and select only the one with the highest version number.
  - __Data Lineage and Idempotency:__ The Workflow Orchestrator will track which specific file version has been processed. This prevents reprocessing of the same data and ensures that if a pipeline is re-run, it will correctly select the latest available version at that time.

- __Conclusion:__ By delegating version handling to a specialized, configurable component, the new architecture eliminates the risk of processing incorrect data versions. This logic is removed from the core application and becomes a managed, observable part of the data ingestion process.

### 3. Problem: The .xlsx document data source contains multiple fields, and data should only be considered invalid if core fields are missing.

- __Legacy System Flaw:__ The analysis of `legacy/annuity_hub/data_handler/data_cleaner.py` reveals a monolithic and fragile approach to data validation. Within each `_clean_method` of the numerous `Cleaner` classes, validation logic is implicitly and inconsistently applied. There is no centralized, explicit definition of what constitutes a "valid" record. For example, the `AnnuityPerformanceCleaner` performs a series of `map`, `fillna`, and `replace` operations, but it lacks a clear, final validation step to check for the presence of essential fields like `月度`, `计划代码`, or `company_id`. A failure in one of the upstream mapping steps could silently result in null values for critical fields being loaded into the database.

- __New Architecture Solution:__ This critical issue is addressed by the introduction of a dedicated **`Data Validation Engine`**, powered by a library like Pydantic.
  - __Explicit Data Contracts:__ For each `Domain Processing Service`, a Pydantic model will define the expected schema of the data, including data types, constraints, and which fields are required versus optional. This creates an explicit, machine-readable "data contract."
  - __Enforced at Boundaries:__ The Workflow Orchestrator will ensure that data is validated against these contracts as it enters and leaves each processing service. If a record is read from an Excel file and, after initial transformation, is missing a core field (e.g., `customer_name`), the Pydantic model will raise a validation error *before* it is passed to the next stage.
  - __Centralized and Reusable Rules:__ Validation rules are defined once in the Pydantic models and are reused wherever that data shape is expected. This eliminates the scattered, duplicated, and inconsistent validation logic of the legacy system.

- __Conclusion:__ The new architecture transforms data validation from an implicit, error-prone process into an explicit, robust, and centrally managed function. By enforcing data contracts at the boundaries of each service, it guarantees that records with missing core fields are identified and handled early, preventing data quality issues from propagating through the system and into the data warehouse.
