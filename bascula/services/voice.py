from __future__ import annotations
import subprocess, threading, shlex
from typing import Optional, Callable


class VoiceService:
    """Wrapper sencillo para ASR/TTS locales mediante scripts hear.sh y say.sh.

    - No bloquea la UI: usa hilos cortos por operación.
    - Tolerante a errores: si no existen los scripts, cae en no-op.
    """

    def __init__(self, hear_cmd: str = "hear.sh", say_cmd: str = "say.sh") -> None:
        self.hear_cmd = hear_cmd
        self.say_cmd = say_cmd
        self._listen_thread: Optional[threading.Thread] = None
        self._listening = False

    def is_listening(self) -> bool:
        return self._listening and self._listen_thread is not None and self._listen_thread.is_alive()

    def start_listening(self, on_text: Callable[[str], None]) -> bool:
        if self.is_listening():
            return False
        self._listening = True

        def _worker():
            text = ""
            try:
                proc = subprocess.Popen(self.hear_cmd if isinstance(self.hear_cmd, list) else shlex.split(self.hear_cmd),
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    out, _ = proc.communicate(timeout=15)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    out = ""
                text = (out or "").strip()
            except Exception:
                text = ""
            finally:
                self._listening = False
                try:
                    on_text(text)
                except Exception:
                    pass

        self._listen_thread = threading.Thread(target=_worker, daemon=True)
        self._listen_thread.start()
        return True

    def speak(self, text: str) -> None:
        def _worker():
            try:
                cmd = self.say_cmd if isinstance(self.say_cmd, list) else shlex.split(self.say_cmd)
                # Pasamos texto como argumento; adaptar si el script espera stdin
                subprocess.Popen(cmd + [text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

