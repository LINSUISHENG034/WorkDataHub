# PA OTP Validation Checklist

This module depends on the corporate network/VPN in order to reach `otp.paic.com.cn`. Use the
following steps to verify the client end-to-end and to troubleshoot common failures.

## 1. Prepare the environment

1. Sync dependencies (installs `gmssl` and friends):
   ```bash
   uv sync
   ```
2. Confirm the PA OTP credentials are present either in the environment or in `.env`:
   ```bash
   rg "PA_UM_" .env
   ```
3. Make sure the host resolves correctly (requires VPN/intranet access):
   ```bash
   nslookup otp.paic.com.cn
   ```

## 2. Fetch an OTP once

```bash
uv run python -m work_data_hub.utils.patoken_client
```

Expected output (sample):

```
2025-09-20 10:12:34 INFO OTP 123456 (expires in 30s at 2025-09-20 10:13:04 CST)
```

If the command exits with an error, consult the troubleshooting section below.

## 3. Optional refresh loop

To reuse the session token while it is still valid:

```python
from work_data_hub.utils import PATokenClient, build_client_from_env

client = build_client_from_env()
result = client.fetch_once()
if result.will_expire_within(10):
    result = client.refresh(result)
print(result.otp)
```

## Troubleshooting

- `Failed to reach the PA OTP service: ... NameResolutionError` – DNS lookup failed. Reconnect
  to the corporate VPN or update local DNS so `otp.paic.com.cn` resolves.
- `Missing required environment variables` – populate `PA_UM_ACCOUNT`, `PA_UM_PASSWORD`, and
  `PA_OTP_PIN` in `.env` or the environment.
- Non-zero `ret` codes – the backend rejected the credentials/PIN. Re-enter the values and retry.

For deeper debugging, increase the log verbosity before running the CLI:

```bash
$env:WDH_LOG_LEVEL = "DEBUG"
uv run python -m work_data_hub.utils.patoken_client
```
