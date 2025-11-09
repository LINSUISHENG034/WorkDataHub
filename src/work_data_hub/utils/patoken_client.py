"""Client utilities for retrieving OTP tokens from the PAIC OTP service."""

from __future__ import annotations

import inspect
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from gmssl import func, sm2

LOGGER = logging.getLogger(__name__)

CONFIG_URL = "https://otp.paic.com.cn/api/rest/v1/pacas/config"
AUTH_URL = "https://otp.paic.com.cn/api/rest/v1/pacas/authenticate"
AUTH_PIN_URL = "https://otp.paic.com.cn/api/rest/newPortal/v1/authUserPin"
AUTO_REFRESH_URL = "https://otp.paic.com.cn/api/rest/newPortal/v1/autoRefresh"
MANUAL_REFRESH_URL = "https://otp.paic.com.cn/api/rest/newPortal/v1/manualRefresh"
DEFAULT_TIMEOUT = 15


if sys.version_info >= (3, 10):

    def dataclass_slotted(_cls: Optional[type] = None, **kwargs: Any):
        def wrap(cls: type) -> type:
            return dataclass(cls, slots=True, **kwargs)

        return wrap(_cls) if _cls is not None else wrap

else:  # pragma: no cover - Python < 3.10 compatibility

    def dataclass_slotted(_cls: Optional[type] = None, **kwargs: Any):
        def wrap(cls: type) -> type:
            return dataclass(cls, **kwargs)

        return wrap(_cls) if _cls is not None else wrap


class PATokenError(RuntimeError):
    """Top-level exception for PA token failures."""


class APIRequestError(PATokenError):
    """Wraps transport-level or non-zero ret code responses."""


@dataclass_slotted()
class SM2Config:
    pin_x: str
    pin_y: str
    key_x: str
    key_y: str
    pwd_split: str


@dataclass_slotted()
class OTPResult:
    otp: str
    token: str
    session_id: str
    expires_in: int
    fetched_at: datetime

    @property
    def expires_at(self) -> datetime:
        return self.fetched_at + timedelta(seconds=self.expires_in)

    def will_expire_within(self, seconds: int) -> bool:
        return (self.expires_at - datetime.now(timezone.utc)).total_seconds() <= seconds


def load_env_file(path: str | Path = ".env") -> None:
    """Load simple KEY=VALUE pairs from a .env file if present."""

    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


class PATokenClient:
    """High-level client that mimics the Chrome extensions' OTP retrieval flow."""

    def __init__(
        self,
        account: str,
        password: str,
        pin: str,
        *,
        login_type: str = "um",
        session: Optional[requests.Session] = None,
    ) -> None:
        self.account = account
        self.password = password
        self.pin = pin
        self.login_type = login_type
        self.session = session or requests.Session()

    def fetch_once(self) -> OTPResult:
        """Request a fresh OTP and return the result with metadata."""

        sm2_config = self._fetch_sm2_config()
        timestamp = str(int(time.time() * 1000))
        password_payload = f"{self.password}{sm2_config.pwd_split}{timestamp}"
        encrypted_password = self._encrypt(
            sm2_config.key_x, sm2_config.key_y, password_payload
        )
        session_id = self._authenticate(encrypted_password, timestamp)
        token = self._authenticate_pin(sm2_config, session_id)
        otp_payload = self._request_otp(
            session_id, token, AUTO_REFRESH_URL, with_auth=True
        )
        expires_in = int(otp_payload.get("countDown") or 0)
        return OTPResult(
            otp=otp_payload["otp"],
            token=token,
            session_id=session_id,
            expires_in=expires_in,
            fetched_at=datetime.now(timezone.utc),
        )

    def refresh(self, result: OTPResult, *, manual: bool = False) -> OTPResult:
        """Refresh the OTP using the cached token."""

        url = MANUAL_REFRESH_URL if manual else AUTO_REFRESH_URL
        otp_payload = self._request_otp(
            result.session_id, result.token, url, with_auth=not manual
        )
        expires_in = int(otp_payload.get("countDown") or 0)
        return OTPResult(
            otp=otp_payload["otp"],
            token=result.token,
            session_id=result.session_id,
            expires_in=expires_in,
            fetched_at=datetime.now(timezone.utc),
        )

    def _fetch_sm2_config(self) -> SM2Config:
        payload = self._request_json("GET", CONFIG_URL)
        data = payload.get("data") or {}
        return SM2Config(
            pin_x=data["pinX"],
            pin_y=data["pinY"],
            key_x=data["keyX"],
            key_y=data["keyY"],
            pwd_split=data.get("pwdSplit") or "d9a4xc40",
        )

    def _authenticate(self, encrypted_password: str, timestamp: str) -> str:
        body = {
            "userId": self.account,
            "password": encrypted_password,
            "loginType": self.login_type,
            "timestamp": timestamp,
        }
        headers = {"content-type": "application/json;charset=UTF-8"}
        payload = self._request_json("POST", AUTH_URL, json=body, headers=headers)
        session_id = (payload.get("data") or {}).get("sessionId")
        if not session_id:
            raise PATokenError("Missing sessionId in authenticate response")
        return session_id

    def _authenticate_pin(self, sm2_config: SM2Config, session_id: str) -> str:
        encrypted_pin = self._encrypt(sm2_config.pin_x, sm2_config.pin_y, self.pin)
        headers = {
            "content-type": "application/json;charset=UTF-8",
            "X-Authorization": session_id,
        }
        payload = self._request_json(
            "POST",
            AUTH_PIN_URL,
            json={"pinPwd": encrypted_pin},
            headers=headers,
        )
        token = payload.get("data")
        if not token:
            raise PATokenError("Missing token in authUserPin response")
        return token

    def _request_otp(
        self,
        session_id: str,
        token: str,
        url: str,
        *,
        with_auth: bool,
    ) -> Dict[str, Any]:
        headers = {
            "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
        }
        if with_auth:
            headers["X-Authorization"] = session_id
        payload = self._request_json(
            "POST", url, data={"token": token}, headers=headers
        )
        outer = payload.get("data") or {}
        if isinstance(outer, dict) and "data" in outer:
            outer = outer["data"]
        otp = outer.get("otp")
        if not otp:
            raise PATokenError("OTP value missing in refresh response")
        return outer

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = DEFAULT_TIMEOUT,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        try:
            response = self.session.request(
                method, url, headers=headers, timeout=timeout, **kwargs
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            hint = ""
            if isinstance(exc, requests.exceptions.ConnectionError):
                root = exc.__cause__
                if root and "NameResolutionError" in repr(root):
                    hint = (
                        " — DNS lookup failed. Confirm VPN/intranet connectivity "
                        "and that otp.paic.com.cn is reachable."
                    )
            raise APIRequestError(f"Request to {url} failed: {exc}{hint}") from exc
        try:
            payload: Dict[str, Any] = response.json()
        except ValueError as exc:
            raise APIRequestError(f"Invalid JSON from {url}") from exc

        ret_code = payload.get("ret")
        if ret_code not in (None, 0, "0", 200, "200"):
            message = (
                payload.get("retRlt")
                or payload.get("message")
                or payload.get("msg")
                or "Unknown error"
            )
            raise APIRequestError(f"API {url} returned ret={ret_code}: {message}")
        return payload

    def _encrypt(self, key_x: str, key_y: str, plaintext: str) -> str:
        public_key = (key_x + key_y).lower()
        crypt = sm2.CryptSM2(public_key=public_key, private_key=None)
        random_hex = func.random_hex(crypt.para_len)
        encrypt_params = inspect.signature(crypt.encrypt).parameters
        if len(encrypt_params) >= 3:
            cipher_bytes = crypt.encrypt(plaintext.encode("utf-8"), random_hex)
        else:
            cipher_bytes = crypt.encrypt(plaintext.encode("utf-8"))
        return cipher_bytes.hex().upper()


def build_client_from_env() -> PATokenClient:
    load_env_file()
    account = os.getenv("PA_UM_ACCOUNT")
    password = os.getenv("PA_UM_PASSWORD")
    pin = os.getenv("PA_OTP_PIN")
    missing = [
        name
        for name, value in (
            ("PA_UM_ACCOUNT", account),
            ("PA_UM_PASSWORD", password),
            ("PA_OTP_PIN", pin),
        )
        if not value
    ]
    if missing:
        joined = ", ".join(missing)
        raise PATokenError(f"Missing required environment variables: {joined}")
    return PATokenClient(account=account, password=password, pin=pin)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    try:
        client = build_client_from_env()
        result = client.fetch_once()
    except APIRequestError as exc:
        LOGGER.error(
            "Failed to reach the PA OTP service: %s",
            exc,
        )
        sys.exit(1)
    except PATokenError as exc:
        LOGGER.error("Failed to fetch OTP: %s", exc)
        sys.exit(1)
    except Exception:  # pragma: no cover - defensive guard for unexpected issues
        LOGGER.exception("Unexpected error while fetching OTP")
        sys.exit(1)
    LOGGER.info(
        "OTP %s (expires in %ss at %s)",
        result.otp,
        result.expires_in,
        result.expires_at.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
    )


if __name__ == "__main__":
    main()
