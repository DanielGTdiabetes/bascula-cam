from __future__ import annotations

"""Voice synthesis helpers backed by Piper."""

import json
import logging
import os
import shlex
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional

_LOGGER = logging.getLogger("bascula.voice")


def _find_binary(candidates: list[str | None]) -> Optional[str]:
    for item in candidates:
        if not item:
            continue
        path = shutil.which(item)
        if path:
            return path
        candidate = Path(item)
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    return None


class VoiceService:
    """Minimal Piper wrapper used for spoken prompts."""

    def __init__(
        self,
        *,
        model_path: Optional[str] = None,
        binary: Optional[str] = None,
        sample_rate: int = 22050,
    ) -> None:
        self.sample_rate = int(sample_rate)
        bin_candidates = [
            binary,
            os.getenv("BASCULA_PIPER_BIN"),
            "piper",
            "/usr/bin/piper",
            "/usr/local/bin/piper",
        ]
        self.binary = _find_binary(bin_candidates)
        self.model_path = model_path or os.getenv(
            "BASCULA_PIPER_MODEL", "/opt/piper/models/es_ES-sharvard-medium.onnx"
        )
        if self.binary is None:
            _LOGGER.warning("Piper no disponible en PATH; voz deshabilitada")
        if not self._model_available():
            _LOGGER.warning("Modelo Piper no encontrado en %s", self.model_path)

        self._hear_command: Optional[list[str]] = None
        custom_cmd = os.getenv("BASCULA_HEAR_CMD") or os.getenv("BASCULA_LISTEN_CMD")
        if custom_cmd:
            parts: list[str]
            try:
                parts = shlex.split(custom_cmd)
            except Exception:
                parts = [custom_cmd]
            if parts:
                resolved = _find_binary([parts[0]]) or parts[0]
                parts[0] = resolved
                self._hear_command = parts
        else:
            hear_candidates = [
                "bascula-hear",
                "bascula-listen",
                "hear-bascula",
            ]
            resolved = _find_binary(hear_candidates)
            if resolved:
                self._hear_command = [resolved]
        self._lock = threading.Lock()
        self._listening = False
        self._listen_thread: Optional[threading.Thread] = None
        self._listen_proc: Optional[subprocess.Popen[str]] = None
        self._listen_stop: Optional[threading.Event] = None
        self._stub_warned = False

    # ------------------------------------------------------------------ helpers
    def _model_available(self) -> bool:
        if not self.model_path:
            return False
        try:
            return Path(self.model_path).exists()
        except Exception:
            return False

    def _can_speak(self) -> bool:
        return bool(self.binary and self._model_available())

    # ------------------------------------------------------------------ public API
    def say(self, text: str) -> None:
        """Speak *text* asynchronously using Piper + aplay."""

        message = (text or "").strip()
        if not message or not self._can_speak():
            return

        device = os.getenv("BASCULA_APLAY_DEVICE", "").strip()
        binary = self.binary
        model = self.model_path
        sample_rate = self.sample_rate

        def _worker() -> None:
            cmd = [binary, "--model", model, "--output-raw"]
            voice_proc = None
            player_proc = None
            try:
                voice_proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                if voice_proc.stdin is None or voice_proc.stdout is None:
                    raise RuntimeError("Canal Piper inválido")
                play_cmd = [
                    "aplay",
                    "-q",
                    "-f",
                    "S16_LE",
                    "-r",
                    str(sample_rate),
                ]
                if device:
                    play_cmd.extend(["-D", device])
                player_proc = subprocess.Popen(
                    play_cmd,
                    stdin=voice_proc.stdout,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                voice_proc.stdout.close()
                payload = json.dumps({"text": message}) + "\n"
                voice_proc.stdin.write(payload.encode("utf-8"))
                voice_proc.stdin.close()
                voice_proc.wait(timeout=30)
                if player_proc is not None:
                    player_proc.wait(timeout=30)
            except Exception:
                _LOGGER.debug("Fallo reproduciendo voz", exc_info=True)
            finally:
                for proc in (player_proc, voice_proc):
                    if proc and proc.poll() is None:
                        try:
                            proc.terminate()
                        except Exception:
                            pass

        threading.Thread(target=_worker, daemon=True).start()

    # Backwards compatibility -------------------------------------------------
    def speak(self, text: str) -> None:  # pragma: no cover - legacy alias
        self.say(text)

    # Listening API ----------------------------------------------------------
    def start_listening(
        self,
        on_text: Callable[[str], None],
        *,
        duration: Optional[int] = None,
        rate: Optional[int] = None,
        device: Optional[str] = None,
    ) -> bool:
        if not callable(on_text):
            return False

        with self._lock:
            if self._listening:
                return False
            stop_event = threading.Event()
            self._listening = True
            self._listen_stop = stop_event
            backend = list(self._hear_command) if self._hear_command else None

        def _runner() -> None:
            thread = threading.current_thread()
            if backend:
                self._run_backend_listener(
                    backend,
                    on_text,
                    stop_event,
                    thread,
                    duration=duration,
                    rate=rate,
                    device=device,
                )
            else:
                self._run_stub_listener(on_text, stop_event, thread)

        thread = threading.Thread(target=_runner, daemon=True)
        with self._lock:
            self._listen_thread = thread
        thread.start()
        return True

    def stop_listening(self) -> None:
        with self._lock:
            thread = self._listen_thread
            proc = self._listen_proc
            stop_event = self._listen_stop
            self._listening = False
        if stop_event is not None:
            stop_event.set()
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        with self._lock:
            if proc is not None and self._listen_proc is proc:
                self._listen_proc = None
            if thread is not None and self._listen_thread is thread:
                self._listen_thread = None
                self._listen_stop = None

    def is_listening(self) -> bool:
        with self._lock:
            return self._listening

    # Internal helpers -------------------------------------------------------
    def _run_backend_listener(
        self,
        command: list[str],
        on_text: Callable[[str], None],
        stop_event: threading.Event,
        thread: threading.Thread,
        *,
        duration: Optional[int],
        rate: Optional[int],
        device: Optional[str],
    ) -> None:
        env = os.environ.copy()
        if duration is not None:
            env.setdefault("BASCULA_LISTEN_DURATION", str(duration))
        if rate is not None:
            env.setdefault("BASCULA_LISTEN_RATE", str(rate))
        if device:
            env.setdefault("BASCULA_LISTEN_DEVICE", str(device))

        try:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                env=env,
            )
        except Exception:
            _LOGGER.debug("Fallo escuchando", exc_info=True)
            self._run_stub_listener(on_text, stop_event, thread)
            return

        with self._lock:
            self._listen_proc = proc

        try:
            timeout = 15.0
            if duration is not None:
                try:
                    timeout = max(15.0, float(duration) + 10.0)
                except Exception:
                    timeout = 15.0
            try:
                stdout, _ = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    proc.terminate()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=2)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                stdout = ""
            except Exception:
                _LOGGER.debug("Fallo escuchando", exc_info=True)
                stdout = ""
        finally:
            with self._lock:
                if self._listen_proc is proc:
                    self._listen_proc = None

        text = ""
        if stdout:
            lines = [line.strip() for line in stdout.splitlines() if line.strip()]
            if lines:
                text = lines[-1]
        self._finish_listening(thread)
        if not stop_event.is_set():
            try:
                on_text(text)
            except Exception:
                pass

    def _run_stub_listener(
        self,
        on_text: Callable[[str], None],
        stop_event: threading.Event,
        thread: threading.Thread,
    ) -> None:
        if not self._stub_warned:
            _LOGGER.info(
                "VoiceService en modo stub de escucha (backend no disponible)"
            )
            self._stub_warned = True
        # Simular una pequeña espera antes de devolver callback vacío
        should_emit = not stop_event.wait(0.5)
        self._finish_listening(thread)
        if should_emit and not stop_event.is_set():
            try:
                on_text("")
            except Exception:
                pass

    def _finish_listening(self, thread: Optional[threading.Thread]) -> None:
        with self._lock:
            if thread is None or self._listen_thread is thread:
                self._listen_thread = None
                self._listen_stop = None
                self._listening = False
