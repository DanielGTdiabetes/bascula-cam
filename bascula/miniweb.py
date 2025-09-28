"""FastAPI mini web service for configuration, recovery, OTA, and diagnostics.

This module provides the LAN mini web specified for the Raspberry Pi based scale.
It intentionally does *not* touch the Tk UI or the core scale logic – the service
exposes HTTP endpoints that can be consumed from other devices on the local
network.

Key features implemented here:

* Token and PIN based authentication with signed cookies.
* Configuration management (Wi-Fi, OpenAI, Nightscout, export/reload).
* OTA helpers (status, check, channel selection, updates, rollback).
* Recovery helpers (restarts, rollback, logs, diagnostics, factory reset).
* Simple HTML UI rendered via Jinja templates.

The implementation tries to be resilient in environments that do not provide the
exact tooling available on the production Raspberry Pi (for example when running
the unit tests on CI or during local development).  Commands that are not
available will return a helpful message instead of crashing the web service.
"""

from __future__ import annotations

import base64
import dataclasses
import datetime as dt
import ipaddress
import json
import logging
import os
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, BadTimeSignature, URLSafeTimedSerializer
import requests
import uvicorn
import yaml

from bascula import __version__

APP_NAME = "Báscula Miniweb"
APP_DESCRIPTION = "Mini web LAN para configuración, OTA y recuperación"

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

SESSION_COOKIE = "bascula_session"
SESSION_TTL_SECONDS = 30 * 60  # 30 minutos
SESSION_RENEW_THRESHOLD = 10 * 60  # renovar cuando queden 10 minutos

AUTH_STATE_PATH = Path("/var/lib/bascula/miniweb_auth.json")
CONFIG_YAML_PATH = Path("/etc/bascula/config.yaml")
SECRETS_ENV_PATH = Path("/etc/bascula/secrets.env")
OTA_LOG_PATH = Path("/var/log/bascula/ota.log")

DEFAULT_ROLLBACK_COMMIT = "cec388edb25b95fa3e52c639355d03370b791c01"


def _default_repo_root() -> Path:
    env = os.environ.get("MINIWEB_REPO")
    if env:
        repo = Path(env)
        if repo.exists():
            return repo

    # Prefer production path when available, otherwise fall back to the project root.
    prod = Path("/opt/bascula/current")
    if prod.exists():
        return prod

    return Path(__file__).resolve().parent.parent


REPO_ROOT = _default_repo_root()


TEMPLATE_DIR = Path(__file__).resolve().parent / "miniweb_templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


# ---------------------------------------------------------------------------
# Helper classes
# ---------------------------------------------------------------------------


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_text_file(path: Path, data: str, *, mode: int | None = None) -> None:
    _ensure_parent(path)
    path.write_text(data, encoding="utf-8")
    if mode is not None:
        try:
            path.chmod(mode)
        except PermissionError:  # pragma: no cover - best effort on dev machines
            log.debug("Cannot chmod %s", path)


def _read_json_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        log.warning("Failed to load JSON file %s", path)
        return {}


def _write_json_file(path: Path, payload: Dict[str, Any]) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _coerce_port(value: Any, default: int = 8080) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        port = default
    return port if 0 < port < 65536 else default


def _looks_like_ip(candidate: str) -> bool:
    try:
        ipaddress.ip_address(candidate)
        return True
    except ValueError:
        return False


def load_config_yaml() -> Dict[str, Any]:
    if not CONFIG_YAML_PATH.exists():
        return {}
    try:
        with CONFIG_YAML_PATH.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            return {}
        return data
    except Exception as exc:  # pragma: no cover - defensive
        log.error("Failed to read %s: %s", CONFIG_YAML_PATH, exc)
        return {}


def save_config_yaml(config: Dict[str, Any]) -> None:
    _ensure_parent(CONFIG_YAML_PATH)
    with CONFIG_YAML_PATH.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(config, fh, sort_keys=True)
    try:
        CONFIG_YAML_PATH.chmod(0o644)
    except PermissionError:  # pragma: no cover - best effort
        pass


def load_secrets_env() -> Dict[str, str]:
    if not SECRETS_ENV_PATH.exists():
        return {}
    secrets_data: Dict[str, str] = {}
    for line in SECRETS_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        secrets_data[key.strip()] = value.strip()
    return secrets_data


def save_secrets_env(data: Dict[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in sorted(data.items())]
    _write_text_file(SECRETS_ENV_PATH, "\n".join(lines) + "\n", mode=0o600)


def mask_secret(secret: Optional[str]) -> Optional[str]:
    if not secret:
        return secret
    if len(secret) <= 4:
        return "*" * len(secret)
    return secret[:2] + "***" + secret[-2:]


def _now() -> float:
    return time.time()


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------


class RateLimiter:
    """Persist per-IP login attempts to avoid brute force attacks."""

    def __init__(self, path: Path, limit: int = 5, window_seconds: int = 300, block_seconds: int = 600) -> None:
        self._limit = limit
        self._window = window_seconds
        self._block = block_seconds
        self._memory_state: Dict[str, Any] = {}
        self._memory_mode = False
        self._path = self._prepare_path(path)

    def _prepare_path(self, preferred: Path) -> Path:
        """Ensure the rate-limit state file lives in a writable location."""

        def _try_prepare(candidate: Path) -> bool:
            try:
                _ensure_parent(candidate)
                candidate.touch(exist_ok=True)
                return True
            except Exception as exc:  # pragma: no cover - permission errors on dev machines
                log.debug("RateLimiter cannot use %s: %s", candidate, exc)
                return False

        if _try_prepare(preferred):
            return preferred

        fallback = Path.home() / ".cache" / "bascula-miniweb" / preferred.name
        if _try_prepare(fallback):
            log.info("RateLimiter falling back to %s", fallback)
            return fallback

        log.warning(
            "RateLimiter operating in memory-only mode; unable to persist state to %s", preferred
        )
        self._memory_mode = True
        return preferred

    def _load_state(self) -> Dict[str, Any]:
        if self._memory_mode:
            return dict(self._memory_state)
        return _read_json_file(self._path)

    def _save_state(self, state: Dict[str, Any]) -> None:
        if self._memory_mode:
            self._memory_state = dict(state)
            return
        try:
            _write_json_file(self._path, state)
        except Exception as exc:  # pragma: no cover - defensive fallback
            log.warning(
                "RateLimiter switching to memory-only mode due to write failure on %s: %s",
                self._path,
                exc,
            )
            self._memory_mode = True
            self._memory_state = dict(state)

    def _prune(self, attempts: List[float]) -> List[float]:
        threshold = _now() - self._window
        return [stamp for stamp in attempts if stamp >= threshold]

    def check(self, ip: str) -> None:
        state = self._load_state()
        entry = state.get(ip, {}) if isinstance(state, dict) else {}
        blocked_until = entry.get("blocked_until")
        if isinstance(blocked_until, (int, float)) and blocked_until > _now():
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Intentos bloqueados temporalmente")

        attempts = entry.get("attempts", [])
        if isinstance(attempts, list):
            entry["attempts"] = self._prune([float(x) for x in attempts])
        else:
            entry["attempts"] = []
        state[ip] = entry
        self._save_state(state)

    def register(self, ip: str, success: bool) -> None:
        state = self._load_state()
        entry = state.get(ip, {}) if isinstance(state, dict) else {}
        attempts = entry.get("attempts", [])
        if not isinstance(attempts, list):
            attempts = []

        now = _now()
        attempts = self._prune([float(x) for x in attempts])
        if not success:
            attempts.append(now)
            if len(attempts) >= self._limit:
                entry["blocked_until"] = now + self._block
        else:
            attempts = []
            entry["blocked_until"] = None

        entry["attempts"] = attempts
        state[ip] = entry
        self._save_state(state)


@dataclasses.dataclass
class AuthContext:
    authenticated: bool
    via: str
    expires_at: Optional[dt.datetime] = None
    should_refresh: bool = False


class AuthManager:
    def __init__(self) -> None:
        token = os.environ.get("MINIWEB_TOKEN")
        self._token = token.strip() if token else None

        secret = os.environ.get("MINIWEB_SECRET") or self._token
        if not secret:
            secret = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
        self._secret = secret

        self._serializer = URLSafeTimedSerializer(self._secret, salt="bascula-miniweb-session")
        self._rate_limiter = RateLimiter(AUTH_STATE_PATH)

    # ------------------------------------------------------------------
    def _load_pin(self) -> Optional[str]:
        env_pin = os.environ.get("MINIWEB_PIN")
        if env_pin:
            return env_pin.strip()

        config = load_config_yaml()
        network = config.get("network") if isinstance(config, dict) else None
        if isinstance(network, dict):
            pin = network.get("pin") or network.get("miniweb_pin")
            if pin:
                return str(pin).strip()
        return None

    # ------------------------------------------------------------------
    def require_auth(self, request: Request) -> AuthContext:
        token_header = request.headers.get("X-API-Token")
        if self._token and token_header and secrets.compare_digest(token_header, self._token):
            return AuthContext(authenticated=True, via="token")

        cookie = request.cookies.get(SESSION_COOKIE)
        if not cookie:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida")

        try:
            data = self._serializer.loads(cookie, max_age=SESSION_TTL_SECONDS)
        except BadTimeSignature:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión expirada")
        except BadSignature:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión inválida")

        expires = dt.datetime.fromtimestamp(data.get("expires", 0), tz=dt.timezone.utc)
        now = _utcnow()
        if expires <= now:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión expirada")

        should_refresh = (expires - now).total_seconds() <= SESSION_RENEW_THRESHOLD
        return AuthContext(authenticated=True, via=str(data.get("via", "pin")), expires_at=expires, should_refresh=should_refresh)

    # ------------------------------------------------------------------
    def refresh_cookie(self, response: Response, via: str) -> None:
        payload = {
            "via": via,
            "issued": _utcnow().timestamp(),
            "expires": (_utcnow() + dt.timedelta(seconds=SESSION_TTL_SECONDS)).timestamp(),
        }
        cookie = self._serializer.dumps(payload)
        response.set_cookie(
            key=SESSION_COOKIE,
            value=cookie,
            httponly=True,
            samesite="lax",
            max_age=SESSION_TTL_SECONDS,
            secure=False,
        )

    # ------------------------------------------------------------------
    def clear_cookie(self, response: Response) -> None:
        response.delete_cookie(SESSION_COOKIE)

    # ------------------------------------------------------------------
    def login(self, request: Request, response: Response, pin: str) -> AuthContext:
        ip = self._peer_ip(request)
        self._rate_limiter.check(ip)

        stored_pin = self._load_pin()
        if not stored_pin:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="PIN no configurado")

        if not secrets.compare_digest(str(pin).strip(), str(stored_pin)):
            self._rate_limiter.register(ip, success=False)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="PIN incorrecto")

        self._rate_limiter.register(ip, success=True)
        ctx = AuthContext(authenticated=True, via="pin", expires_at=_utcnow() + dt.timedelta(seconds=SESSION_TTL_SECONDS))
        self.refresh_cookie(response, via="pin")
        return ctx

    # ------------------------------------------------------------------
    @staticmethod
    def _peer_ip(request: Request) -> str:
        client = request.client
        if client:
            return client.host
        return "unknown"

    # ------------------------------------------------------------------
    def auth_status(self, request: Request) -> AuthContext:
        try:
            ctx = self.require_auth(request)
        except HTTPException:
            return AuthContext(authenticated=False, via="none")
        return ctx


auth_manager = AuthManager()


def auth_dependency(request: Request, response: Response) -> AuthContext:
    ctx = auth_manager.require_auth(request)
    if ctx.should_refresh:
        auth_manager.refresh_cookie(response, via=ctx.via)
    return ctx


# ---------------------------------------------------------------------------
# Command helpers
# ---------------------------------------------------------------------------


class CommandError(RuntimeError):
    pass


def run_command(args: Iterable[str], *, check: bool = True, timeout: int = 30, env: Optional[Dict[str, str]] = None, cwd: Optional[Path] = None) -> subprocess.CompletedProcess[str]:
    log.debug("Running command: %s", " ".join(args))
    try:
        result = subprocess.run(
            list(args),
            check=check,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
            cwd=str(cwd) if cwd else None,
        )
    except FileNotFoundError as exc:
        raise CommandError(f"Comando no disponible: {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise CommandError(exc.stderr.strip() or exc.stdout.strip() or "Error de comando") from exc
    except subprocess.TimeoutExpired as exc:
        raise CommandError(f"Comando expirado tras {timeout}s") from exc
    return result


def run_repo_git(args: Iterable[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    git_args = ["git", "-C", str(REPO_ROOT)] + list(args)
    return run_command(git_args, check=check)


def append_ota_log(message: str) -> None:
    timestamp = _utcnow().strftime("%Y-%m-%d %H:%M:%S %Z")
    entry = f"[{timestamp}] {message}\n"
    try:
        _ensure_parent(OTA_LOG_PATH)
        with OTA_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(entry)
    except Exception:  # pragma: no cover - logging best effort
        log.debug("Unable to append to OTA log")


# ---------------------------------------------------------------------------
# Mini web application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(title=APP_NAME, description=APP_DESCRIPTION, version=__version__)

    # ------------------------------------------------------------------
    @app.get("/health")
    async def health() -> Dict[str, bool]:
        return {"ok": True}

    # ------------------------------------------------------------------
    @app.get("/info")
    async def info(request: Request) -> Dict[str, Any]:
        hide = os.environ.get("MINIWEB_HIDE_INFO") == "1"
        if hide:
            auth_manager.require_auth(request)

        host = socket.gethostname()
        host_env = os.environ.get("UVICORN_HOST", "0.0.0.0")
        port_env = os.environ.get("UVICORN_PORT", "8080")
        return {
            "app": APP_NAME,
            "description": APP_DESCRIPTION,
            "version": __version__,
            "hostname": host,
            "listen": {"host": host_env, "port": port_env},
        }

    # ------------------------------------------------------------------
    @app.get("/config", response_class=HTMLResponse)
    async def config_page(request: Request) -> HTMLResponse:
        status_ctx = auth_manager.auth_status(request)
        return templates.TemplateResponse("config.html", {"request": request, "auth": status_ctx})

    # Routers -----------------------------------------------------------
    auth_router = APIRouter(prefix="/auth", tags=["auth"])
    config_router = APIRouter(prefix="/config", tags=["config"])
    ota_router = APIRouter(prefix="/ota", tags=["ota"], dependencies=[Depends(auth_dependency)])
    recovery_router = APIRouter(prefix="/recovery", tags=["recovery"], dependencies=[Depends(auth_dependency)])

    # ------------------------------------------------------------------
    @auth_router.post("/login")
    async def auth_login(payload: Dict[str, Any], request: Request, response: Response) -> Dict[str, Any]:
        pin = str(payload.get("pin", ""))
        ctx = auth_manager.login(request, response, pin)
        return {"authenticated": ctx.authenticated, "via": ctx.via, "expires_at": ctx.expires_at.isoformat() if ctx.expires_at else None}

    # ------------------------------------------------------------------
    @auth_router.post("/logout")
    async def auth_logout(response: Response) -> Dict[str, bool]:
        auth_manager.clear_cookie(response)
        return {"ok": True}

    # ------------------------------------------------------------------
    @auth_router.get("/status")
    async def auth_status_endpoint(request: Request, response: Response) -> Dict[str, Any]:
        ctx = auth_manager.auth_status(request)
        if ctx.authenticated and ctx.should_refresh:
            auth_manager.refresh_cookie(response, via=ctx.via)
        return {"authenticated": ctx.authenticated, "via": ctx.via, "expires_at": ctx.expires_at.isoformat() if ctx.expires_at else None}

    app.include_router(auth_router)

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    @config_router.get("/export", dependencies=[Depends(auth_dependency)])
    async def config_export() -> Dict[str, Any]:
        config = load_config_yaml()
        secrets_data = load_secrets_env()
        secrets_masked = {key: mask_secret(value) for key, value in secrets_data.items()}
        return {"config": config, "secrets": secrets_masked}

    @config_router.post("/reload", dependencies=[Depends(auth_dependency)])
    async def config_reload() -> Dict[str, Any]:
        return {"accepted": True}

    # Wi-Fi -------------------------------------------------------------
    wifi_router = APIRouter(prefix="/wifi", tags=["wifi"], dependencies=[Depends(auth_dependency)])

    @wifi_router.get("/status")
    async def wifi_status() -> Dict[str, Any]:
        status_payload: Dict[str, Any] = {"ssid": None, "ip": None, "signal": None}

        try:
            ssid = run_command(["iwgetid", "-r"]).stdout.strip()
            status_payload["ssid"] = ssid or None
        except CommandError as exc:
            status_payload["ssid_error"] = str(exc)

        try:
            ip_output = run_command(["hostname", "-I"]).stdout.strip()
            ips = [token for token in ip_output.split() if _looks_like_ip(token)]
            status_payload["ip"] = ips[0] if ips else None
        except CommandError as exc:
            status_payload["ip_error"] = str(exc)

        try:
            signal = _current_signal_strength()
            if signal is not None:
                status_payload["signal"] = signal
        except CommandError as exc:
            status_payload["signal_error"] = str(exc)

        return status_payload

    def _current_signal_strength() -> Optional[int]:
        try:
            result = run_command(["nmcli", "-t", "-f", "IN-USE,SIGNAL", "dev", "wifi"])
        except CommandError as exc:
            raise exc

        for line in result.stdout.splitlines():
            parts = line.split(":")
            if not parts:
                continue
            if parts[0] == "*" and len(parts) > 1:
                try:
                    return int(parts[1])
                except ValueError:
                    return None
        return None

    @wifi_router.get("/scan")
    async def wifi_scan() -> Dict[str, Any]:
        try:
            result = run_command(["nmcli", "-t", "-f", "SSID,SIGNAL", "dev", "wifi"])
            entries = []
            for line in result.stdout.splitlines():
                if not line:
                    continue
                ssid, _, signal = line.partition(":")
                entries.append({"ssid": ssid, "signal": int(signal) if signal.isdigit() else None})
            return {"networks": entries, "method": "nmcli"}
        except CommandError as exc:
            return {"networks": [], "method": "nmcli", "error": str(exc)}

    @wifi_router.post("/connect")
    async def wifi_connect(payload: Dict[str, Any]) -> Dict[str, Any]:
        ssid = str(payload.get("ssid", "")).strip()
        psk = str(payload.get("psk", "")).strip()
        if not ssid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SSID requerido")

        try:
            run_command(["nmcli", "dev", "wifi", "connect", ssid, "password", psk, "ifname", "wlan0"])
            return {"ok": True, "method": "nmcli", "note": "Conexión solicitada"}
        except CommandError as exc:
            return {"ok": False, "method": "nmcli", "note": str(exc)}

    config_router.include_router(wifi_router)

    # OpenAI ------------------------------------------------------------
    @config_router.get("/openai", dependencies=[Depends(auth_dependency)])
    async def config_openai_get() -> Dict[str, Any]:
        secrets_data = load_secrets_env()
        return {"api_key": mask_secret(secrets_data.get("OPENAI_API_KEY"))}

    @config_router.post("/openai", dependencies=[Depends(auth_dependency)])
    async def config_openai_set(payload: Dict[str, Any]) -> Dict[str, Any]:
        api_key = str(payload.get("api_key", "")).strip()
        secrets_data = load_secrets_env()
        if api_key:
            secrets_data["OPENAI_API_KEY"] = api_key
        else:
            secrets_data.pop("OPENAI_API_KEY", None)
        save_secrets_env(secrets_data)
        return {"ok": True}

    @config_router.post("/openai/test", dependencies=[Depends(auth_dependency)])
    async def config_openai_test() -> Dict[str, Any]:
        try:
            response = requests.head("https://api.openai.com/v1/models", timeout=3)
            ok = response.status_code in {200, 401}
        except requests.RequestException as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": ok, "status": response.status_code}

    # Nightscout --------------------------------------------------------
    @config_router.get("/nightscout", dependencies=[Depends(auth_dependency)])
    async def config_nightscout_get() -> Dict[str, Any]:
        config = load_config_yaml()
        secrets_data = load_secrets_env()
        nightscout = config.get("nightscout") if isinstance(config, dict) else {}
        url = None
        if isinstance(nightscout, dict):
            url = nightscout.get("url")
        return {"url": url, "token": mask_secret(secrets_data.get("NIGHTSCOUT_TOKEN"))}

    @config_router.post("/nightscout", dependencies=[Depends(auth_dependency)])
    async def config_nightscout_set(payload: Dict[str, Any]) -> Dict[str, Any]:
        url = str(payload.get("url", "")).strip() or None
        token = str(payload.get("token", "")).strip() or None

        config = load_config_yaml()
        nightscout = config.setdefault("nightscout", {}) if isinstance(config, dict) else {}
        if url:
            nightscout["url"] = url
        else:
            nightscout.pop("url", None)
        config["nightscout"] = nightscout
        save_config_yaml(config)

        secrets_data = load_secrets_env()
        if token:
            secrets_data["NIGHTSCOUT_TOKEN"] = token
        else:
            secrets_data.pop("NIGHTSCOUT_TOKEN", None)
        save_secrets_env(secrets_data)
        return {"ok": True}

    @config_router.post("/nightscout/test", dependencies=[Depends(auth_dependency)])
    async def config_nightscout_test(payload: Dict[str, Any]) -> Dict[str, Any]:
        url = str(payload.get("url") or "").strip()
        token = str(payload.get("token") or "").strip()
        if not url:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL requerida")
        headers = {}
        if token:
            headers["API-SECRET"] = token
        try:
            response = requests.get(url.rstrip("/") + "/api/v1/status", timeout=3, headers=headers)
            ok = response.ok
        except requests.RequestException as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": ok, "status": response.status_code}

    app.include_router(config_router)

    # ------------------------------------------------------------------
    # OTA helpers
    # ------------------------------------------------------------------

    def _ota_remote_branch() -> Tuple[str, str]:
        remote = os.environ.get("OTA_REMOTE") or os.environ.get("MINIWEB_OTA_REMOTE")
        branch = os.environ.get("OTA_BRANCH") or os.environ.get("MINIWEB_OTA_BRANCH")

        config = load_config_yaml()
        ota_conf = config.get("ota") if isinstance(config, dict) else {}
        if isinstance(ota_conf, dict):
            remote = remote or ota_conf.get("remote")
            branch = branch or ota_conf.get("branch")

        return remote or "origin", branch or "main"

    def _ensure_clean_worktree(force: bool = False) -> None:
        result = run_repo_git(["status", "--porcelain"])
        if result.stdout.strip() and not force:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cambios locales detectados; use force para continuar")

    def _restart_service(service: str) -> str:
        try:
            run_command(["sudo", "systemctl", "restart", service], check=True)
            return "ok"
        except CommandError as exc:
            return f"no se pudo reiniciar {service}: {exc}"

    @ota_router.get("/status")
    async def ota_status() -> Dict[str, Any]:
        remote, branch = _ota_remote_branch()
        status_payload: Dict[str, Any] = {"remote": remote, "branch": branch}

        head = run_repo_git(["rev-parse", "--short", "HEAD"]).stdout.strip()
        status_payload["head"] = head

        dirty = run_repo_git(["status", "--porcelain"]).stdout.strip()
        status_payload["dirty"] = bool(dirty)

        try:
            run_repo_git(["fetch", remote, branch], check=True)
        except CommandError as exc:
            status_payload["fetch_error"] = str(exc)
            return status_payload

        ahead_behind = run_repo_git(["rev-list", "--left-right", "--count", f"HEAD...{remote}/{branch}"]).stdout.strip()
        ahead, behind = (int(token) for token in ahead_behind.split()) if ahead_behind else (0, 0)
        status_payload["ahead"] = ahead
        status_payload["behind"] = behind

        latest_remote = run_repo_git(["rev-parse", "--short", f"{remote}/{branch}"]).stdout.strip()
        status_payload["latest_remote"] = latest_remote
        return status_payload

    @ota_router.post("/check")
    async def ota_check() -> Dict[str, Any]:
        remote, branch = _ota_remote_branch()
        run_repo_git(["fetch", "--all", "--prune"])
        log_output = run_repo_git([
            "log",
            "--pretty=format:%h %ad %s",
            "--date=short",
            f"HEAD..{remote}/{branch}",
            "-n",
            "50",
        ]).stdout.splitlines()
        ahead_behind = run_repo_git(["rev-list", "--left-right", "--count", f"HEAD...{remote}/{branch}"]).stdout.strip()
        ahead, behind = (int(token) for token in ahead_behind.split()) if ahead_behind else (0, 0)
        latest_remote = run_repo_git(["rev-parse", "--short", f"{remote}/{branch}"]).stdout.strip()
        return {"remote": remote, "branch": branch, "behind": behind, "ahead": ahead, "latest_remote": latest_remote, "pending": log_output}

    @ota_router.get("/channels")
    async def ota_channels() -> Dict[str, Any]:
        result = run_repo_git(["branch", "-r"])
        branches = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if "->" in line:
                continue
            if not line:
                continue
            if "/" in line:
                remote, name = line.split("/", 1)
                branches.append({"remote": remote, "branch": name})
        return {"channels": branches}

    @ota_router.post("/set-channel")
    async def ota_set_channel(payload: Dict[str, Any]) -> Dict[str, Any]:
        branch = str(payload.get("branch", "")).strip()
        if not branch:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rama requerida")

        remote, _ = _ota_remote_branch()
        config = load_config_yaml()
        ota_section = config.setdefault("ota", {}) if isinstance(config, dict) else {}
        ota_section["branch"] = branch
        ota_section["remote"] = remote
        config["ota"] = ota_section
        save_config_yaml(config)
        return {"remote": remote, "branch": branch}

    def _apply_reset(target: str, remote: str, branch: str) -> Dict[str, Any]:
        append_ota_log(f"Reset a {target}")
        run_repo_git(["fetch", "--all", "--prune"])
        run_repo_git(["reset", "--hard", target])
        note = _restart_service("bascula-app")
        return {"ok": True, "to": target, "branch": branch, "note": note}

    def _confirm(payload: Dict[str, Any]) -> None:
        confirm = payload.get("confirm")
        if confirm != "QUIERO CONTINUAR":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confirmación requerida")

    @ota_router.post("/update")
    async def ota_update(payload: Dict[str, Any]) -> Dict[str, Any]:
        _confirm(payload)
        remote, branch = _ota_remote_branch()
        _ensure_clean_worktree(force=payload.get("force") is True)
        target = f"{remote}/{branch}"
        response = _apply_reset(target, remote, branch)
        response["note"] = response.get("note", "") + " (la app puede reiniciarse)"
        return response

    @ota_router.post("/update-to")
    async def ota_update_to(payload: Dict[str, Any]) -> Dict[str, Any]:
        _confirm(payload)
        ref = str(payload.get("ref", "")).strip()
        if not ref:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Referencia requerida")
        remote, branch = _ota_remote_branch()
        _ensure_clean_worktree(force=payload.get("force") is True)
        response = _apply_reset(ref, remote, branch)
        return response

    @ota_router.post("/rollback")
    async def ota_rollback(payload: Dict[str, Any]) -> Dict[str, Any]:
        _confirm(payload)
        remote, branch = _ota_remote_branch()
        _ensure_clean_worktree(force=payload.get("force") is True)
        response = _apply_reset(DEFAULT_ROLLBACK_COMMIT, remote, branch)
        return response

    app.include_router(ota_router)

    # ------------------------------------------------------------------
    # Recovery helpers
    # ------------------------------------------------------------------

    def _restart_payload(service: str) -> Dict[str, Any]:
        note = _restart_service(service)
        return {"ok": note == "ok", "note": note}

    @recovery_router.post("/rollback")
    async def recovery_rollback(payload: Dict[str, Any]) -> Dict[str, Any]:
        return await ota_rollback(payload)

    @recovery_router.post("/restart")
    async def recovery_restart(payload: Dict[str, Any]) -> Dict[str, Any]:
        _confirm(payload)
        return _restart_payload("bascula-app")

    @recovery_router.post("/restart-miniweb")
    async def recovery_restart_miniweb(payload: Dict[str, Any]) -> Dict[str, Any]:
        _confirm(payload)
        return _restart_payload("bascula-miniweb")

    @recovery_router.post("/reset-wifi")
    async def recovery_reset_wifi(payload: Dict[str, Any]) -> Dict[str, Any]:
        _confirm(payload)
        try:
            run_command(["nmcli", "device", "disconnect", "wlan0"])
            run_command(["nmcli", "connection", "delete", "wlan0"], check=False)
            return {"ok": True, "note": "Wi-Fi reiniciado"}
        except CommandError as exc:
            return {"ok": False, "note": str(exc)}

    @recovery_router.post("/factory")
    async def recovery_factory(payload: Dict[str, Any]) -> Dict[str, Any]:
        _confirm(payload)
        if SECRETS_ENV_PATH.exists():
            try:
                SECRETS_ENV_PATH.unlink()
            except Exception as exc:  # pragma: no cover - best effort
                return {"ok": False, "note": f"No se pudo borrar secrets: {exc}"}
        note = _restart_service("bascula-miniweb")
        return {"ok": True, "note": note}

    @recovery_router.get("/logs")
    async def recovery_logs() -> Dict[str, Any]:
        logs_payload: Dict[str, str] = {}
        for service in ("bascula-app", "bascula-miniweb"):
            try:
                result = run_command(["journalctl", "-u", service, "-n", "200", "--no-pager"], check=True)
                logs_payload[service] = result.stdout
            except CommandError as exc:
                logs_payload[service] = f"No disponible: {exc}"
        return logs_payload

    @recovery_router.get("/diagnostics")
    async def recovery_diagnostics() -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "time": _utcnow().isoformat(),
        }
        try:
            payload["git_head"] = run_repo_git(["rev-parse", "--short", "HEAD"]).stdout.strip()
        except CommandError as exc:
            payload["git_head_error"] = str(exc)

        try:
            ss_result = run_command(["ss", "-lntp"])
            payload["ports"] = ss_result.stdout
        except CommandError as exc:
            payload["ports_error"] = str(exc)

        try:
            ip_result = run_command(["hostname", "-I"])
            payload["ips"] = ip_result.stdout.strip()
        except CommandError as exc:
            payload["ips_error"] = str(exc)

        try:
            uptime_result = run_command(["uptime", "-p"])
            payload["uptime"] = uptime_result.stdout.strip()
        except CommandError as exc:
            payload["uptime_error"] = str(exc)

        try:
            df_result = run_command(["df", "-h", "/"])
            payload["disk"] = df_result.stdout
        except CommandError as exc:
            payload["disk_error"] = str(exc)

        return payload

    app.include_router(recovery_router)

    return app


app = create_app()


# ---------------------------------------------------------------------------
# Backwards compatible threaded server used by other parts of the project
# ---------------------------------------------------------------------------


class MiniwebServer:
    """Run the FastAPI mini web in a background uvicorn thread."""

    def __init__(self, app_path: str = "bascula.miniweb:app") -> None:
        self._app_path = app_path
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._server: Optional[uvicorn.Server] = None
        self._stopped_event: Optional[threading.Event] = None
        self._startup_error: Optional[BaseException] = None

    # ------------------------------------------------------------------
    def start(self) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return True

            host = os.environ.get("UVICORN_HOST", "0.0.0.0")
            port = _coerce_port(os.environ.get("UVICORN_PORT"), 8080)
            config = uvicorn.Config(self._app_path, host=host, port=port, log_level="info")

            server = uvicorn.Server(config)
            server.install_signal_handlers = False

            self._server = server
            self._stopped_event = threading.Event()
            self._startup_error = None

            thread = threading.Thread(target=self._run, name="MiniwebServer", daemon=True)
            self._thread = thread
            thread.start()

        self._wait_for_start(timeout=5.0)
        return self._startup_error is None

    # ------------------------------------------------------------------
    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            server = self._server
            thread = self._thread
            event = self._stopped_event

        if thread is None:
            return

        if server is not None:
            server.should_exit = True

        if event is not None:
            event.wait(timeout=timeout)

        thread.join(timeout=timeout)

        with self._lock:
            self._thread = None
            self._server = None
            self._stopped_event = None
            self._startup_error = None

    # ------------------------------------------------------------------
    def wait(self, timeout: Optional[float] = None) -> bool:
        event = self._stopped_event
        if event is None:
            return True
        return event.wait(timeout=timeout)

    # ------------------------------------------------------------------
    @property
    def is_running(self) -> bool:
        thread = self._thread
        return bool(thread and thread.is_alive())

    # ------------------------------------------------------------------
    def _run(self) -> None:
        server = self._server
        try:
            if server is None:
                return
            server.run()
        except OSError as exc:
            self._startup_error = exc
            log.error("Miniweb failed to bind: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive logging
            self._startup_error = exc
            log.exception("Miniweb crashed: %s", exc)
        finally:
            event = self._stopped_event
            if event is not None:
                event.set()

    # ------------------------------------------------------------------
    def _wait_for_start(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._startup_error is not None:
                return
            server = self._server
            if server and server.started.is_set():
                return
            thread = self._thread
            if thread and not thread.is_alive():
                return
            time.sleep(0.05)


def main() -> None:
    server = MiniwebServer()
    if not server.start():
        return
    try:
        server.wait()
    except KeyboardInterrupt:  # pragma: no cover - manual shutdown
        pass
    finally:
        server.stop()


__all__ = [
    "APP_DESCRIPTION",
    "APP_NAME",
    "app",
    "create_app",
    "MiniwebServer",
    "main",
]

