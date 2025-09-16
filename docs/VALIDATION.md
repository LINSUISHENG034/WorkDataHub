```bash
PS E:\Projects\WorkDataHub> uv run ruff check src/ --fix              
E501 Line too long (142 > 100)
  --> src\work_data_hub\auth\eqc_auth_handler.py:66:101
   |
65 | …
66 | …0.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
   |                                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
67 | …
68 | …
   |

E501 Line too long (101 > 100)
   --> src\work_data_hub\auth\eqc_auth_opencv.py:214:101
    |
212 |             arr = np.frombuffer(bg_bytes, dtype=np.uint8)
213 |             img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
214 |             return SliderImages(bg_bytes=bg_bytes, full_bytes=full_bytes, bg_width=int(img.shape[1]))
    |                                                                 
                                    ^
215 |         elif await bg.count() > 0:
216 |             # bg 存在但 full 不可见：先返回仅 bg，由上游选择边缘投影算法
    |

E501 Line too long (101 > 100)
   --> src\work_data_hub\domain\company_enrichment\lookup_queue.py:158:101
    |
156 |                 else:
157 |                     # Fallback: attempt to map columns positionally if provided by DB
158 |                     # id, name, normalized_name, status, attempts, last_error, created_at, updated_at
    |                                                                 
                                    ^
159 |                     try:
160 |                         request = LookupRequest(
    |

E501 Line too long (101 > 100)
   --> src\work_data_hub\domain\company_enrichment\service.py:589:101 
    |
588 |                         logger.debug(
589 |                             f"Processing lookup request {getattr(request, 'id', None)}: '{req_name}'"
    |                                                                 
                                    ^
590 |                         )
    |

E501 Line too long (116 > 100)
  --> src\work_data_hub\domain\reference_backfill\service.py:73:90    
   |
71 |                 # BUSINESS RULE: From row with max 期末资产规模  
72 |                 # 主拓代码 <- 该行的 机构代码； 主拓机构 <- 该行 的 机构名称
73 |                 "主拓代码": (str(max_row.get("机构代码")).strip() if max_row and max_row.get("机构代码") else None),
   |                                                                  
                                   ^^^^^^^^^^^^^^^^
74 |                 "主拓机构": (str(max_row.get("机构名称")).strip() if max_row and max_row.get("机构名称") else None),
   |

E501 Line too long (116 > 100)
  --> src\work_data_hub\domain\reference_backfill\service.py:74:90    
   |
72 |                 # 主拓代码 <- 该行的 机构代码； 主拓机构 <- 该行 的 机构名称
73 |                 "主拓代码": (str(max_row.get("机构代码")).strip() if max_row and max_row.get("机构代码") else None),
74 |                 "主拓机构": (str(max_row.get("机构名称")).strip() if max_row and max_row.get("机构名称") else None),
   |                                                                  
                                   ^^^^^^^^^^^^^^^^
75 |
76 |                 # BUSINESS RULE: Format as YYMM_新建 from 月度 (first non-null)
   |

E501 Line too long (114 > 100)
   --> src\work_data_hub\orchestration\jobs.py:294:101
    |
293 |         for match_type, count in plan['mapping_breakdown'].items():
294 |             priority = {"plan": 1, "account": 2, "hardcode": 3, "name": 4, "account_name": 5}.get(match_type, "?")
    |                                                                 
                                    ^^^^^^^^^^^^^^
295 |             print(f"    {match_type} (priority {priority}): {count:,} mappings")
    |

E501 Line too long (126 > 100)
   --> src\work_data_hub\orchestration\jobs.py:310:100
    |
308 |         try:
309 |             with psycopg2.connect(conn_string) as conn:
310 |                 print(f"🔌 Connected to PostgreSQL: {settings.database_host}:{settings.database_port}/{settings.database_db}")        
    |                                                                 
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^        
311 |
312 |                 # Verify target table exists
    |

E501 Line too long (106 > 100)
   --> src\work_data_hub\orchestration\jobs.py:326:101
    |
324 |                 if not table_exists:
325 |                     print("❌ Target table enterprise.company_mapping does not exist")
326 |                     print("Please run the DDL script first: scripts/create_table/ddl/company_mapping.sql")
    |                                                                 
                                    ^^^^^^
327 |                     return
    |

E402 Module level import not at top of file
  --> src\work_data_hub\scripts\migrate_company_mappings.py:31:1      
   |
29 | sys.path.insert(0, str(project_root))
30 |
31 | from src.work_data_hub.config.settings import get_settings       
   | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^       
32 | from src.work_data_hub.domain.company_enrichment.service import validate_mapping_consistency
33 | from src.work_data_hub.io.loader.company_mapping_loader import ( 
   |

E402 Module level import not at top of file
  --> src\work_data_hub\scripts\migrate_company_mappings.py:32:1      
   |
31 | from src.work_data_hub.config.settings import get_settings       
32 | from src.work_data_hub.domain.company_enrichment.service import validate_mapping_consistency
   | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
33 | from src.work_data_hub.io.loader.company_mapping_loader import ( 
34 |     CompanyMappingLoaderError,
   |

E402 Module level import not at top of file
  --> src\work_data_hub\scripts\migrate_company_mappings.py:33:1      
   |
31 |   from src.work_data_hub.config.settings import get_settings     
32 |   from src.work_data_hub.domain.company_enrichment.service import validate_mapping_consistency
33 | / from src.work_data_hub.io.loader.company_mapping_loader import (
34 | |     CompanyMappingLoaderError,
35 | |     extract_legacy_mappings,
36 | |     generate_load_plan,
37 | |     load_company_mappings,
38 | | )
   | |_^
39 |
40 |   # Configure logging
   |

E501 Line too long (114 > 100)
   --> src\work_data_hub\scripts\migrate_company_mappings.py:137:101  
    |
136 |         for match_type, count in plan['mapping_breakdown'].items():
137 |             priority = {"plan": 1, "account": 2, "hardcode": 3, "name": 4, "account_name": 5}.get(match_type, "?")
    |                                                                 
                                    ^^^^^^^^^^^^^^
138 |             logger.info(f"    {match_type} (priority {priority}): {count:,} mappings")
    |

E501 Line too long (129 > 100)
   --> src\work_data_hub\scripts\migrate_company_mappings.py:156:101  
    |
154 |         try:
155 |             with psycopg2.connect(conn_string) as conn:
156 |                 logger.info(f"Connected to PostgreSQL: {settings.database_host}:{settings.database_port}/{settings.database_db}")     
    |                                                                 
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^     
157 |
158 |                 # Verify target table exists
    |

E501 Line too long (113 > 100)
   --> src\work_data_hub\scripts\migrate_company_mappings.py:172:101  
    |
170 |                 if not table_exists:
171 |                     logger.error(f"Target table {args.schema}.{args.table} does not exist")
172 |                     logger.error("Please run the DDL script first: scripts/create_table/ddl/company_mapping.sql")
    |                                                                 
                                    ^^^^^^^^^^^^^
173 |                     sys.exit(1)
    |

F841 Local variable `conn_string` is assigned to but never used       
   --> src\work_data_hub\scripts\migrate_company_mappings.py:217:9    
    |
216 |         # Check PostgreSQL configuration
217 |         conn_string = settings.get_database_connection_string() 
    |         ^^^^^^^^^^^
218 |         logger.debug(f"PostgreSQL config: {settings.database_host}:{settings.database_port}")
    |
help: Remove assignment to unused variable `conn_string`

F401 `legacy.annuity_hub.database_operations.mysql_ops.MySqlDBManager` imported but unused; consider using `importlib.util.find_spec` to test for availability
   --> src\work_data_hub\scripts\migrate_company_mappings.py:222:74   
    |
220 |         # Check legacy MySQL access
221 |         try:
222 |             from legacy.annuity_hub.database_operations.mysql_ops import MySqlDBManager
    |                                                                 
         ^^^^^^^^^^^^^^
223 |             logger.debug("Legacy MySqlDBManager is available")  
224 |         except ImportError:
    |
help: Remove unused import: `legacy.annuity_hub.database_operations.mysql_ops.MySqlDBManager`

Found 17 errors.
No fixes available (1 hidden fix can be enabled with the `--unsafe-fixes` option).
PS E:\Projects\WorkDataHub> 
```

```bash
PS E:\Projects\WorkDataHub> uv run ruff check src/ --fix              
E501 Line too long (142 > 100)
  --> src\work_data_hub\auth\eqc_auth_handler.py:66:101
   |
65 | …
66 | …0.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
   |                                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
67 | …
68 | …
   |

E501 Line too long (101 > 100)
   --> src\work_data_hub\auth\eqc_auth_opencv.py:214:101
    |
212 |             arr = np.frombuffer(bg_bytes, dtype=np.uint8)
213 |             img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
214 |             return SliderImages(bg_bytes=bg_bytes, full_bytes=full_bytes, bg_width=int(img.shape[1]))
    |                                                                 
                                    ^
215 |         elif await bg.count() > 0:
216 |             # bg 存在但 full 不可见：先返回仅 bg，由上游选择边缘投影算法
    |

E501 Line too long (101 > 100)
   --> src\work_data_hub\domain\company_enrichment\lookup_queue.py:158:101
    |
156 |                 else:
157 |                     # Fallback: attempt to map columns positionally if provided by DB
158 |                     # id, name, normalized_name, status, attempts, last_error, created_at, updated_at
    |                                                                 
                                    ^
159 |                     try:
160 |                         request = LookupRequest(
    |

E501 Line too long (101 > 100)
   --> src\work_data_hub\domain\company_enrichment\service.py:589:101 
    |
588 |                         logger.debug(
589 |                             f"Processing lookup request {getattr(request, 'id', None)}: '{req_name}'"
    |                                                                 
                                    ^
590 |                         )
    |

E501 Line too long (116 > 100)
  --> src\work_data_hub\domain\reference_backfill\service.py:73:90    
   |
71 |                 # BUSINESS RULE: From row with max 期末资产规模  
72 |                 # 主拓代码 <- 该行的 机构代码； 主拓机构 <- 该行 的 机构名称
73 |                 "主拓代码": (str(max_row.get("机构代码")).strip() if max_row and max_row.get("机构代码") else None),
   |                                                                  
                                   ^^^^^^^^^^^^^^^^
74 |                 "主拓机构": (str(max_row.get("机构名称")).strip() if max_row and max_row.get("机构名称") else None),
   |

E501 Line too long (116 > 100)
  --> src\work_data_hub\domain\reference_backfill\service.py:74:90    
   |
72 |                 # 主拓代码 <- 该行的 机构代码； 主拓机构 <- 该行 的 机构名称
73 |                 "主拓代码": (str(max_row.get("机构代码")).strip() if max_row and max_row.get("机构代码") else None),
74 |                 "主拓机构": (str(max_row.get("机构名称")).strip() if max_row and max_row.get("机构名称") else None),
   |                                                                  
                                   ^^^^^^^^^^^^^^^^
75 |
76 |                 # BUSINESS RULE: Format as YYMM_新建 from 月度 (first non-null)
   |

E501 Line too long (114 > 100)
   --> src\work_data_hub\orchestration\jobs.py:294:101
    |
293 |         for match_type, count in plan['mapping_breakdown'].items():
294 |             priority = {"plan": 1, "account": 2, "hardcode": 3, "name": 4, "account_name": 5}.get(match_type, "?")
    |                                                                 
                                    ^^^^^^^^^^^^^^
295 |             print(f"    {match_type} (priority {priority}): {count:,} mappings")
    |

E501 Line too long (126 > 100)
   --> src\work_data_hub\orchestration\jobs.py:310:100
    |
308 |         try:
309 |             with psycopg2.connect(conn_string) as conn:
310 |                 print(f"🔌 Connected to PostgreSQL: {settings.database_host}:{settings.database_port}/{settings.database_db}")        
    |                                                                 
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^        
311 |
312 |                 # Verify target table exists
    |

E501 Line too long (106 > 100)
   --> src\work_data_hub\orchestration\jobs.py:326:101
    |
324 |                 if not table_exists:
325 |                     print("❌ Target table enterprise.company_mapping does not exist")
326 |                     print("Please run the DDL script first: scripts/create_table/ddl/company_mapping.sql")
    |                                                                 
                                    ^^^^^^
327 |                     return
    |

E402 Module level import not at top of file
  --> src\work_data_hub\scripts\migrate_company_mappings.py:31:1      
   |
29 | sys.path.insert(0, str(project_root))
30 |
31 | from src.work_data_hub.config.settings import get_settings       
   | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^       
32 | from src.work_data_hub.domain.company_enrichment.service import validate_mapping_consistency
33 | from src.work_data_hub.io.loader.company_mapping_loader import ( 
   |

E402 Module level import not at top of file
  --> src\work_data_hub\scripts\migrate_company_mappings.py:32:1      
   |
31 | from src.work_data_hub.config.settings import get_settings       
32 | from src.work_data_hub.domain.company_enrichment.service import validate_mapping_consistency
   | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
33 | from src.work_data_hub.io.loader.company_mapping_loader import ( 
34 |     CompanyMappingLoaderError,
   |

E402 Module level import not at top of file
  --> src\work_data_hub\scripts\migrate_company_mappings.py:33:1      
   |
31 |   from src.work_data_hub.config.settings import get_settings     
32 |   from src.work_data_hub.domain.company_enrichment.service import validate_mapping_consistency
33 | / from src.work_data_hub.io.loader.company_mapping_loader import (
34 | |     CompanyMappingLoaderError,
35 | |     extract_legacy_mappings,
36 | |     generate_load_plan,
37 | |     load_company_mappings,
38 | | )
   | |_^
39 |
40 |   # Configure logging
   |

E501 Line too long (114 > 100)
   --> src\work_data_hub\scripts\migrate_company_mappings.py:137:101  
    |
136 |         for match_type, count in plan['mapping_breakdown'].items():
137 |             priority = {"plan": 1, "account": 2, "hardcode": 3, "name": 4, "account_name": 5}.get(match_type, "?")
    |                                                                 
                                    ^^^^^^^^^^^^^^
138 |             logger.info(f"    {match_type} (priority {priority}): {count:,} mappings")
    |

E501 Line too long (129 > 100)
   --> src\work_data_hub\scripts\migrate_company_mappings.py:156:101  
    |
154 |         try:
155 |             with psycopg2.connect(conn_string) as conn:
156 |                 logger.info(f"Connected to PostgreSQL: {settings.database_host}:{settings.database_port}/{settings.database_db}")     
    |                                                                 
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^     
157 |
158 |                 # Verify target table exists
    |

E501 Line too long (113 > 100)
   --> src\work_data_hub\scripts\migrate_company_mappings.py:172:101  
    |
170 |                 if not table_exists:
171 |                     logger.error(f"Target table {args.schema}.{args.table} does not exist")
172 |                     logger.error("Please run the DDL script first: scripts/create_table/ddl/company_mapping.sql")
    |                                                                 
                                    ^^^^^^^^^^^^^
173 |                     sys.exit(1)
    |

F841 Local variable `conn_string` is assigned to but never used       
   --> src\work_data_hub\scripts\migrate_company_mappings.py:217:9    
    |
216 |         # Check PostgreSQL configuration
217 |         conn_string = settings.get_database_connection_string() 
    |         ^^^^^^^^^^^
218 |         logger.debug(f"PostgreSQL config: {settings.database_host}:{settings.database_port}")
    |
help: Remove assignment to unused variable `conn_string`

F401 `legacy.annuity_hub.database_operations.mysql_ops.MySqlDBManager` imported but unused; consider using `importlib.util.find_spec` to test for availability
   --> src\work_data_hub\scripts\migrate_company_mappings.py:222:74   
    |
220 |         # Check legacy MySQL access
221 |         try:
222 |             from legacy.annuity_hub.database_operations.mysql_ops import MySqlDBManager
    |                                                                 
         ^^^^^^^^^^^^^^
223 |             logger.debug("Legacy MySqlDBManager is available")  
224 |         except ImportError:
    |
help: Remove unused import: `legacy.annuity_hub.database_operations.mysql_ops.MySqlDBManager`

Found 17 errors.
No fixes available (1 hidden fix can be enabled with the `--unsafe-fixes` option).
PS E:\Projects\WorkDataHub> uv run mypy src/                          
src\work_data_hub\auth\eqc_auth_handler.py:13: error: Skipping analyzing "playwright_stealth": module is installed, but missing library stubs or py.typed marker  [import-untyped]
src\work_data_hub\auth\eqc_auth_handler.py:13: note: See https://mypy.readthedocs.io/en/stable/running_mypy.html#missing-imports
src\work_data_hub\auth\eqc_auth_opencv.py:36: error: Skipping analyzing "playwright_stealth": module is installed, but missing library stubs or py.typed marker  [import-untyped]
src\work_data_hub\domain\company_enrichment\service.py: error: Source file found twice under different module names: "work_data_hub.domain.company_enrichment.service" and "src.work_data_hub.domain.company_enrichment.service"
Found 3 errors in 3 files (errors prevented further checking)
PS E:\Projects\WorkDataHub> 
```

```
PS E:\Projects\WorkDataHub> uv run pytest -v -k "enrichment_service or lookup_queue"
======================== test session starts ========================
platform win32 -- Python 3.10.11, pytest-8.4.2, pluggy-1.6.0 -- E:\Projects\WorkDataHub\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: E:\Projects\WorkDataHub
configfile: pyproject.toml
plugins: anyio-4.10.0, asyncio-1.2.0, cov-7.0.0
asyncio: mode=strict, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 636 items / 1 error / 577 deselected / 59 selected         

============================== ERRORS ===============================
_______ ERROR collecting tests/auth/test_eqc_auth_handler.py ________
ImportError while importing test module 'E:\Projects\WorkDataHub\tests\auth\test_eqc_auth_handler.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Users\LINSUISHENG034\AppData\Local\Programs\Python\Python310\lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
tests\auth\test_eqc_auth_handler.py:9: in <module>
    from src.work_data_hub.auth.models import (
E   ModuleNotFoundError: No module named 'src.work_data_hub.auth.models'
========================= warnings summary ========================== 
.venv\lib\site-packages\pydantic\_internal\_config.py:323
  E:\Projects\WorkDataHub\.venv\lib\site-packages\pydantic\_internal\_config.py:323: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.11/migration/
    warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning)

tests\e2e\test_company_mapping_migration.py:255
  E:\Projects\WorkDataHub\tests\e2e\test_company_mapping_migration.py:255: PytestUnknownMarkWarning: Unknown pytest.mark.performance - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html       
    @pytest.mark.performance

tests\e2e\test_company_mapping_migration.py:397
  E:\Projects\WorkDataHub\tests\e2e\test_company_mapping_migration.py:397: PytestUnknownMarkWarning: Unknown pytest.mark.integration - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html       
    @pytest.mark.integration

tests\e2e\test_company_mapping_migration.py:460
  E:\Projects\WorkDataHub\tests\e2e\test_company_mapping_migration.py:460: PytestUnknownMarkWarning: Unknown pytest.mark.e2e - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.e2e

tests\io\connectors\test_eqc_client.py:586
  E:\Projects\WorkDataHub\tests\io\connectors\test_eqc_client.py:586: PytestUnknownMarkWarning: Unknown pytest.mark.eqc_integration - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html        
    @pytest.mark.eqc_integration

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
====================== short test summary info ====================== 
ERROR tests/auth/test_eqc_auth_handler.py
!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!! 
=========== 577 deselected, 5 warnings, 1 error in 2.27s ============ 
PS E:\Projects\WorkDataHub> 
```