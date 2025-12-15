# TODO: EQC Live Integration Test (Story 6.2-P8 / AC11)

This note tracks the current blockers and the exact rerun steps for the **live EQC API integration test**.

## What’s pending

1) **EQC token is expired**
- Symptom: EQC API returns `403` with body `{"error":"TokenExpired"}`.
- Impact: `tests/integration/infrastructure/enrichment/test_eqc_full_data_acquisition_eqc_integration.py` fails early on token validation.

2) **Test database DSN points to a non-existent DB**
- Current `.wdh_env` contains `WDH_TEST_DATABASE_URI=postgresql://.../annuity`.
- Symptom: `psycopg2` error: `FATAL: database "annuity" does not exist`.
- Impact: live test skips/fails DB connect unless you change DSN to an existing database.

## Files involved

- Live test: `tests/integration/infrastructure/enrichment/test_eqc_full_data_acquisition_eqc_integration.py`
- Token refresh CLI (saves to `.wdh_env` by default): `python -m work_data_hub.cli auth refresh`

## Rerun instructions (PowerShell)

### 1) Refresh EQC token into `.wdh_env`

Run (in repo root):

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -m work_data_hub.cli auth refresh --env-file .wdh_env --timeout 300
```

### 2) Ensure a working Postgres DSN for the test

Pick one option:

- **Option A (recommended)**: use local dev DSN from `.wdh_env`:

```powershell
$env:WDH_TEST_DATABASE_URI = $env:WDH_DATABASE__URI
```

- **Option B**: create the `annuity` database on `192.168.0.200:5432` (if that’s intended), then keep `WDH_TEST_DATABASE_URI` as-is.

### 3) Load `.wdh_env` into the current shell

```powershell
$envFile = Join-Path (Get-Location) '.wdh_env'
Get-Content $envFile | ForEach-Object {
  $t = $_.Trim()
  if ($t -eq '' -or $t.StartsWith('#')) { return }
  if ($t -notmatch '^[A-Za-z_][A-Za-z0-9_]*=') { return }
  $key, $val = $t -split '=', 2
  $key = $key.Trim(); $val = $val.Trim()
  if (($val.StartsWith('\"') -and $val.EndsWith('\"')) -or ($val.StartsWith(\"'\") -and $val.EndsWith(\"'\"))) {
    $val = $val.Substring(1, $val.Length-2)
  }
  Set-Item -Path \"Env:$key\" -Value $val
}
```

### 4) Run the live test (explicit opt-in)

```powershell
Set-Item -Path Env:PYTHONPATH -Value 'src'
Set-Item -Path Env:RUN_EQC_INTEGRATION_TESTS -Value '1'
.\.venv\Scripts\python.exe -m pytest -q -rs -m eqc_integration `
  tests/integration/infrastructure/enrichment/test_eqc_full_data_acquisition_eqc_integration.py
```

## Quick diagnostics (optional)

### Token check (should NOT return TokenExpired)

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -c @'
import os, requests
base_url = os.environ.get("WDH_EQC_BASE_URL") or "https://eqc.pingan.com"
token = os.environ.get("WDH_EQC_TOKEN")
resp = requests.get(
  f"{base_url}/kg-api-hfd/api/search/searchAll",
  params={"keyword":"test","currentPage":1,"pageSize":1},
  headers={"token": token},
  timeout=10,
)
print("status:", resp.status_code)
print("body_prefix:", (resp.text or "")[:200].replace("\\n"," "))
'@
```

### DB check (must connect to an existing DB name)

```powershell
.\.venv\Scripts\python.exe -c @'
import os
import psycopg2
dsn = os.environ.get("WDH_TEST_DATABASE_URI") or os.environ.get("WDH_DATABASE__URI")
conn = psycopg2.connect(dsn, connect_timeout=5)
conn.close()
print("psycopg2 connect: OK")
'@
```

## Security note

If any DB DSN with credentials was printed to console/logs during debugging, rotate that password if it’s not a disposable local dev credential.

