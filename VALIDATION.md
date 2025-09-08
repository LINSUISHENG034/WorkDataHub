```bash
PS E:\Projects\WorkDataHub> uv run ruff check src/ --fix                                    
All checks passed!                                                                          
PS E:\Projects\WorkDataHub> uv run mypy src/
src\work_data_hub\config\settings.py:93: error: Missing named argument "database_uri" for "Settings"  [call-arg]
src\work_data_hub\io\connectors\file_connector.py:267: error: Need type annotation for "by_domain" (hint: "by_domain: dict[<type>, <type>] = ...")  [var-annotated]
src\work_data_hub\io\readers\excel_reader.py:96: error: No overload variant of "read_excel" matches argument types "str", "dict[str, str | int | list[int] | None]"  [call-overload]
src\work_data_hub\io\readers\excel_reader.py:96: note: Possible overload variants:
src\work_data_hub\io\readers\excel_reader.py:96: note:     def [IntStrT: (int, str)] read_excel(io: str | PathLike[str] | ReadBuffer[bytes] | ExcelFile | Any | Any | Any | Any, sheet_name: list[IntStrT], *, header: int | Sequence[int] | None = ..., names: MutableSequence[Any] | ndarray[Any, Any] | tuple[Any, ...] | range | None = ..., index_col: int | Sequence[int] | str | None = ..., usecols: str | SequenceNotStr[Hashable] | range | ExtensionArray | ndarray[Any, Any] | Index[Any] | Series[Any] | Callable[[Any], bool] | None = ..., dtype: str | ExtensionDtype | str | dtype[generic[Any]] | type[str] | type[complex] | type[bool] | type[object] | Mapping[str, str | ExtensionDtype | str | dtype[generic[Any]] | type[str] | type[complex] | type[bool] | type[object]] | None = ..., engine: Literal['xlrd', 'openpyxl', 'odf', 'pyxlsb', 'calamine'] | None = ..., converters: Mapping[int | str, Callable[[object], object]] | None = ..., true_values: Iterable[Hashable] | None = ..., false_values: Iterable[Hashable] | None = ..., skiprows: int | Sequence[int] | Callable[[object], bool] | None = ..., nrows: int | None = ..., na_values: Sequence[str] | dict[str | int, Sequence[str]] | None = ..., keep_default_na: bool = ..., na_filter: bool = ..., verbose: bool = ..., parse_dates: bool | Sequence[int] | Sequence[Sequence[str] | Sequence[int]] | dict[str, Sequence[int] | list[str]] = ..., date_format: dict[Hashable, str] | str | None = ..., thousands: str | None = ..., decimal: str = ..., comment: str | None = ..., skipfooter: int = ..., storage_options: dict[str, Any] | None = ..., dtype_backend: Literal['pyarrow', 'numpy_nullable'] | Literal[_NoDefault.no_default] = ..., engine_kwargs: dict[str, Any] | None = ...) -> dict[IntStrT, DataFrame]
src\work_data_hub\io\readers\excel_reader.py:96: note:     def read_excel(io: str | PathLike[str] | ReadBuffer[bytes] | ExcelFile | Any | Any | Any | Any, sheet_name: None, *, header: int | Sequence[int] | None = ..., names: MutableSequence[Any] | ndarray[Any, Any] | tuple[Any, ...] | range | None = ..., index_col: int | Sequence[int] | str | None = ..., usecols: str | SequenceNotStr[Hashable] | range | ExtensionArray | ndarray[Any, Any] | Index[Any] | Series[Any] | Callable[[Any], bool] | None = ..., dtype: str | ExtensionDtype | str | dtype[generic[Any]] | type[str] | type[complex] | type[bool] | type[object] | Mapping[str, str | ExtensionDtype | str | dtype[generic[Any]] | type[str] | type[complex] | type[bool] | type[object]] | None = ..., engine: Literal['xlrd', 'openpyxl', 'odf', 'pyxlsb', 'calamine'] | None = ..., converters: Mapping[int | str, Callable[[object], object]] | None = ..., true_values: Iterable[Hashable] | None = ..., false_values: Iterable[Hashable] | None = ..., skiprows: int | Sequence[int] | Callable[[object], bool] | None = ..., nrows: int | None = ..., na_values: Sequence[str] | dict[str | int, Sequence[str]] | None = ..., keep_default_na: bool = ..., na_filter: bool = ..., verbose: bool = ..., parse_dates: bool | Sequence[int] | Sequence[Sequence[str] | Sequence[int]] | dict[str, Sequence[int] | list[str]] = ..., date_format: dict[Hashable, str] | str | None = ..., thousands: str | None = ..., decimal: str = ..., comment: str | None = ..., skipfooter: int = ..., storage_options: dict[str, Any] | None = ..., dtype_backend: Literal['pyarrow', 'numpy_nullable'] | Literal[_NoDefault.no_default] = ..., engine_kwargs: dict[str, Any] | None = ...) -> dict[str, DataFrame]
src\work_data_hub\io\readers\excel_reader.py:96: note:     def read_excel(io: str | PathLike[str] | ReadBuffer[bytes] | ExcelFile | Any | Any | Any | Any, sheet_name: list[int | str], *, header: int | Sequence[int] | None = ..., names: MutableSequence[Any] | ndarray[Any, Any] | tuple[Any, ...] | range | None = ..., index_col: int | Sequence[int] | str | None = ..., usecols: str | SequenceNotStr[Hashable] | range | ExtensionArray | ndarray[Any, Any] | Index[Any] | Series[Any] | Callable[[Any], bool] | None = ..., dtype: str | ExtensionDtype | str | dtype[generic[Any]] | type[str] | type[complex] | type[bool] | type[object] | Mapping[str, str | ExtensionDtype | str | dtype[generic[Any]] | type[str] | type[complex] | type[bool] | type[object]] | None = ..., engine: Literal['xlrd', 'openpyxl', 'odf', 'pyxlsb', 'calamine'] | None = ..., converters: Mapping[int | str, Callable[[object], object]] | None = ..., true_values: Iterable[Hashable] | None = ..., false_values: Iterable[Hashable] | None = ..., skiprows: int | Sequence[int] | Callable[[object], bool] | None = ..., nrows: int | None = ..., na_values: Sequence[str] | dict[str | int, Sequence[str]] | None = ..., keep_default_na: bool = ..., na_filter: bool = ..., verbose: bool = ..., parse_dates: bool | Sequence[int] | Sequence[Sequence[str] | Sequence[int]] | dict[str, Sequence[int] | list[str]] = ..., date_format: dict[Hashable, str] | str | None = ..., thousands: str | None = ..., decimal: str = ..., comment: str | None = ..., skipfooter: int = ..., storage_options: dict[str, Any] | None = ..., dtype_backend: Literal['pyarrow', 'numpy_nullable'] | Literal[_NoDefault.no_default] = ..., engine_kwargs: dict[str, Any] | None = ...) -> dict[int | str, DataFrame]
src\work_data_hub\io\readers\excel_reader.py:96: note:     def read_excel(io: str | PathLike[str] | ReadBuffer[bytes] | ExcelFile | Any | Any | Any | Any, sheet_name: int | str = ..., *, header: int | Sequence[int] | None = ..., names: MutableSequence[Any] | ndarray[Any, Any] | tuple[Any, ...] | range | None = ..., index_col: int | Sequence[int] | str | None = ..., usecols: str | SequenceNotStr[Hashable] | range | ExtensionArray | ndarray[Any, Any] | Index[Any] | Series[Any] | Callable[[Any], bool] | None = ..., dtype: str | ExtensionDtype | str | dtype[generic[Any]] | type[str] | type[complex] | type[bool] | type[object] | Mapping[str, str | ExtensionDtype | str | dtype[generic[Any]] | type[str] | type[complex] | type[bool] | type[object]] | None = ..., engine: Literal['xlrd', 'openpyxl', 'odf', 'pyxlsb', 'calamine'] | None = ..., converters: Mapping[int | str, Callable[[object], object]] | None = ..., true_values: Iterable[Hashable] | None = ..., false_values: Iterable[Hashable] | None = ..., skiprows: int | Sequence[int] | Callable[[object], bool] | None = ..., nrows: int | None = ..., na_values: Sequence[str] | dict[str | int, Sequence[str]] | None = ..., keep_default_na: bool = ..., na_filter: bool = ..., verbose: bool = ..., parse_dates: bool | Sequence[int] | Sequence[Sequence[str] | Sequence[int]] | dict[str, Sequence[int] | list[str]] = ..., date_format: dict[Hashable, str] | str | None = ..., thousands: str | None = ..., decimal: str = ..., comment: str | None = ..., skipfooter: int = ..., storage_options: dict[str, Any] | None = ..., dtype_backend: Literal['pyarrow', 'numpy_nullable'] | Literal[_NoDefault.no_default] = ..., engine_kwargs: dict[str, Any] | None = ...) -> DataFrame
src\work_data_hub\io\readers\excel_reader.py:151: error: Incompatible return value type (got
 "list[int | str]", expected "list[str]")  [return-value]
src\work_data_hub\io\readers\excel_reader.py:193: error: Need type annotation for "cleaned_row" (hint: "cleaned_row: dict[<type>, <type>] = ...")  [var-annotated]
src\work_data_hub\io\readers\excel_reader.py:209: error: Incompatible return value type (got
 "list[dict[Hashable, Any]]", expected "list[dict[str, Any]]")  [return-value]
Found 6 errors in 3 files (checked 21 source files)
PS E:\Projects\WorkDataHub> uv run pytest -v -k "(mapping_loader or data_sources_schema) and not postgres"
=================================== test session starts ===================================
platform win32 -- Python 3.10.11, pytest-8.4.2, pluggy-1.6.0 -- E:\Projects\WorkDataHub\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: E:\Projects\WorkDataHub
configfile: pyproject.toml
plugins: anyio-4.10.0, cov-6.2.1
collected 201 items / 162 deselected / 39 selected                                         

tests/config/test_data_sources_schema.py::TestDomainConfig::test_valid_domain_config PASSED [  2%]
tests/config/test_data_sources_schema.py::TestDomainConfig::test_minimal_domain_config PASSED [  5%]
tests/config/test_data_sources_schema.py::TestDomainConfig::test_domain_config_missing_required_fields PASSED [  7%]
tests/config/test_data_sources_schema.py::TestDomainConfig::test_domain_config_invalid_select_value PASSED [ 10%]
tests/config/test_data_sources_schema.py::TestDomainConfig::test_domain_config_empty_pk_list
 PASSED [ 12%]
tests/config/test_data_sources_schema.py::TestDomainConfig::test_domain_config_sheet_types PASSED [ 15%]
tests/config/test_data_sources_schema.py::TestDiscoveryConfig::test_valid_discovery_config PASSED [ 17%]
tests/config/test_data_sources_schema.py::TestDiscoveryConfig::test_minimal_discovery_config
 PASSED [ 20%]
tests/config/test_data_sources_schema.py::TestDataSourcesConfig::test_valid_data_sources_config PASSED [ 23%]
tests/config/test_data_sources_schema.py::TestDataSourcesConfig::test_data_sources_config_without_discovery PASSED [ 25%]
tests/config/test_data_sources_schema.py::TestDataSourcesConfig::test_data_sources_config_empty_domains PASSED [ 28%]
tests/config/test_data_sources_schema.py::TestDataSourcesConfig::test_data_sources_config_missing_domains PASSED [ 30%]
tests/config/test_data_sources_schema.py::TestValidateDataSourcesConfig::test_validate_current_data_sources_succeeds PASSED [ 33%]
tests/config/test_data_sources_schema.py::TestValidateDataSourcesConfig::test_validate_data_sources_with_custom_path PASSED [ 35%]
tests/config/test_data_sources_schema.py::TestValidateDataSourcesConfig::test_validate_data_sources_file_not_found PASSED [ 38%]
tests/config/test_data_sources_schema.py::TestValidateDataSourcesConfig::test_validate_data_sources_invalid_yaml PASSED [ 41%]
tests/config/test_data_sources_schema.py::TestValidateDataSourcesConfig::test_validate_data_sources_missing_required_fields PASSED [ 43%]
tests/config/test_data_sources_schema.py::TestValidateDataSourcesConfig::test_validate_data_sources_invalid_domain_structure PASSED [ 46%]
tests/config/test_data_sources_schema.py::TestGetDomainConfig::test_get_existing_domain_config PASSED [ 48%]
tests/config/test_data_sources_schema.py::TestGetDomainConfig::test_get_domain_config_not_found PASSED [ 51%]
tests/config/test_data_sources_schema.py::TestGetDomainConfig::test_get_domain_config_invalid_file PASSED [ 53%]
tests/config/test_data_sources_schema.py::TestIntegration::test_end_to_end_validation_workflow PASSED [ 56%]
tests/config/test_data_sources_schema.py::TestIntegration::test_real_data_sources_yml_validation PASSED [ 58%]
tests/config/test_mapping_loader.py::TestLoadYamlMapping::test_load_yaml_mapping_happy_path PASSED [ 61%]
tests/config/test_mapping_loader.py::TestLoadYamlMapping::test_load_yaml_mapping_with_integer_values PASSED [ 64%]
tests/config/test_mapping_loader.py::TestLoadYamlMapping::test_load_yaml_mapping_file_not_found PASSED [ 66%]
tests/config/test_mapping_loader.py::TestLoadYamlMapping::test_load_yaml_mapping_invalid_yaml PASSED [ 69%]
tests/config/test_mapping_loader.py::TestLoadYamlMapping::test_load_yaml_mapping_not_dictionary PASSED [ 71%]
tests/config/test_mapping_loader.py::TestLoadYamlMapping::test_load_yaml_mapping_invalid_key_types PASSED [ 74%]
tests/config/test_mapping_loader.py::TestLoadYamlMapping::test_load_yaml_mapping_invalid_value_types PASSED [ 76%]
tests/config/test_mapping_loader.py::TestLoadYamlMapping::test_load_yaml_mapping_empty_file PASSED [ 79%]
tests/config/test_mapping_loader.py::TestLoadYamlMapping::test_load_yaml_mapping_chinese_characters_preserved PASSED [ 82%]
tests/config/test_mapping_loader.py::TestSpecificLoaderFunctions::test_load_company_branch_happy_path PASSED [ 84%]
tests/config/test_mapping_loader.py::TestSpecificLoaderFunctions::test_load_default_portfolio_code_happy_path PASSED [ 87%]
tests/config/test_mapping_loader.py::TestSpecificLoaderFunctions::test_load_company_id_overrides_plan_happy_path PASSED [ 89%]
tests/config/test_mapping_loader.py::TestSpecificLoaderFunctions::test_load_business_type_code_happy_path PASSED [ 92%]
tests/config/test_mapping_loader.py::TestSpecificLoaderFunctions::test_specific_loaders_file_not_found_error PASSED [ 94%]
tests/config/test_mapping_loader.py::TestIntegration::test_all_mappings_load_successfully PASSED [ 97%]
tests/config/test_mapping_loader.py::TestIntegration::test_chinese_characters_preserved_across_all_mappings PASSED [100%]

==================================== warnings summary ===================================== 
.venv\lib\site-packages\pydantic\_internal\_config.py:323
  E:\Projects\WorkDataHub\.venv\lib\site-packages\pydantic\_internal\_config.py:323: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.11/migration/
    warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
====================== 39 passed, 162 deselected, 1 warning in 1.52s ====================== 
PS E:\Projects\WorkDataHub> 
```