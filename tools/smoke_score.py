#!/usr/bin/env python3
"""Evaluate lightweight smoke tests and produce a JSON score."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass
class SmokeResult:
    passed: bool
    detail: Any
    skipped: bool = False


def _choose_port(candidates: List[int]) -> Optional[int]:
    for port in candidates:
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    return None


def _run_tk_smoke() -> Tuple[SmokeResult, SmokeResult, SmokeResult]:
    skipped = False
    try:
        tk = importlib.import_module("tkinter")  # type: ignore
    except Exception:
        return (
            SmokeResult(False, False, skipped=True),
            SmokeResult(False, False, skipped=True),
            SmokeResult(False, False, skipped=True),
        )

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception as exc:  # pragma: no cover - environment specific
        if isinstance(exc, getattr(tk, "TclError", Exception)):
            skipped = True
        return (
            SmokeResult(False, False, skipped=skipped),
            SmokeResult(False, False, skipped=skipped),
            SmokeResult(False, False, skipped=skipped),
        )

    tk_passed = True

    value_label_passed = False
    try:
        module = importlib.import_module("bascula.ui.lightweight_widgets")
        ValueLabel = getattr(module, "ValueLabel")
        widget = ValueLabel(root, text="X", padx=8, pady=4)
        root.update_idletasks()
        widget.destroy()
        value_label_passed = True
    except Exception:
        value_label_passed = False

    mascot_passed = False
    MascotCls = None
    try:
        mascot_module = importlib.import_module("bascula.ui.mascot")
        MascotCls = getattr(mascot_module, "MascotCanvas", None)
    except Exception:
        MascotCls = None
    if MascotCls is None:
        try:
            placeholder_module = importlib.import_module("bascula.ui.mascot_placeholder")
            MascotCls = getattr(placeholder_module, "MascotPlaceholder", None)
        except Exception:
            MascotCls = None
    if MascotCls is not None:
        try:
            widget = MascotCls(root, width=160, height=120)
            root.update_idletasks()
            widget.destroy()
            mascot_passed = True
        except Exception:
            mascot_passed = False

    if root is not None:
        with contextlib.suppress(Exception):
            root.destroy()

    return (
        SmokeResult(tk_passed, tk_passed),
        SmokeResult(value_label_passed, value_label_passed, skipped=False if tk_passed else skipped),
        SmokeResult(mascot_passed, mascot_passed, skipped=False if tk_passed else skipped),
    )


def _run_miniweb_smoke() -> SmokeResult:
    detail: Dict[str, Any] = {"import": False, "health": False, "port": None}
    try:
        uvicorn = importlib.import_module("uvicorn")
        miniweb = importlib.import_module("bascula.services.miniweb")
        detail["import"] = True
    except Exception as exc:
        detail["error"] = repr(exc)
        return SmokeResult(False, detail)

    if getattr(uvicorn, "Server", None) is None:
        detail["error"] = "uvicorn_missing"
        return SmokeResult(False, detail)

    port = _choose_port([8080, 8078])
    if port is None:
        detail["error"] = "no_port"
        return SmokeResult(False, detail, skipped=True)

    detail["port"] = port

    class _DummyUI:
        def get_status_snapshot(self) -> Dict[str, Any]:
            return {"ok": True}

        def get_settings_snapshot(self) -> Dict[str, Any]:
            return {"ok": True}

        def update_settings_from_dict(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
            return True, ""

    service = None
    try:
        MiniWebService = getattr(miniweb, "MiniWebService")
        service = MiniWebService(_DummyUI(), host="127.0.0.1", port=port)
        started = service.start()
        if not started:
            detail["error"] = "start_failed"
            return SmokeResult(False, detail)

        deadline = time.monotonic() + 5.0
        url = f"http://127.0.0.1:{port}/health"
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=0.8) as response:
                    if response.status == 200:
                        detail["health"] = True
                        break
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
                time.sleep(0.2)
        passed = bool(detail["health"])
        if not passed:
            detail["error"] = "health_timeout"
        return SmokeResult(passed, detail)
    except Exception as exc:
        detail["error"] = repr(exc)
        return SmokeResult(False, detail)
    finally:
        if service is not None:
            with contextlib.suppress(Exception):
                service.stop()
            time.sleep(0.2)


def _run_yaml_smoke() -> SmokeResult:
    try:
        yaml = importlib.import_module("yaml")
        yaml.safe_load(io.StringIO("{}"))
        return SmokeResult(True, True)
    except Exception as exc:
        return SmokeResult(False, {"error": repr(exc)})


def _run_scale_smoke() -> SmokeResult:
    detail: Dict[str, Any] = {"ok": False, "weight": 0.0, "stable": False}
    try:
        module = importlib.import_module("bascula.core.scale")
    except Exception as exc:
        detail["error"] = repr(exc)
        return SmokeResult(False, detail)

    service = None
    passed = False
    try:
        module.random.seed(0)
        ScaleService = getattr(module, "ScaleService")
        service = ScaleService(port="/tmp/bascula-sim")
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline:
            value = float(service.read_weight())
            stable = bool(getattr(service, "stable", False))
            detail["weight"] = value
            detail["stable"] = stable
            if value > 0.0 and stable:
                passed = True
                break
            time.sleep(0.2)
        detail["ok"] = passed
        if not passed:
            detail["error"] = "unstable"
        return SmokeResult(passed, detail)
    except Exception as exc:
        detail["error"] = repr(exc)
        return SmokeResult(False, detail)
    finally:
        if service is not None:
            with contextlib.suppress(Exception):
                service.shutdown()


def main() -> None:
    details: Dict[str, Any] = {}
    skipped: set[str] = set()
    score = 0

    tk_result, valuelabel_result, mascot_result = _run_tk_smoke()
    details["tk"] = bool(tk_result.detail)
    details["valuelabel"] = bool(valuelabel_result.detail)
    details["mascot"] = bool(mascot_result.detail)

    if tk_result.skipped:
        skipped.update({"tk", "valuelabel", "mascot"})
    else:
        if tk_result.passed:
            score += 30
        if valuelabel_result.passed:
            score += 20
        if mascot_result.passed:
            score += 10

    miniweb_result = _run_miniweb_smoke()
    details["miniweb"] = miniweb_result.detail
    if miniweb_result.skipped:
        skipped.add("miniweb")
    elif miniweb_result.passed and isinstance(miniweb_result.detail, dict) and miniweb_result.detail.get("health"):
        score += 15

    yaml_result = _run_yaml_smoke()
    details["yaml"] = yaml_result.detail
    if yaml_result.passed:
        score += 15

    scale_result = _run_scale_smoke()
    details["scale_sim"] = scale_result.detail
    if scale_result.passed:
        score += 10

    details["skipped"] = sorted(skipped)

    payload = {"score": score, "details": details}
    json.dump(payload, sys.stdout)


if __name__ == "__main__":
    main()
