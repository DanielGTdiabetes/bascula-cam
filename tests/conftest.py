import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:  # pragma: no cover - optional dependency shim
    import serial  # type: ignore
except Exception:  # pragma: no cover - tests inject stub
    serial_stub = types.ModuleType("serial")

    class SerialException(Exception):
        """Fallback exception to mimic pyserial.SerialException."""

    class Serial:  # noqa: D401 - compat with pyserial
        """Minimal Serial stub raising when used."""

        def __init__(self, *args, **kwargs):
            raise SerialException("pyserial no disponible en entorno de tests")

        def close(self):
            pass

        def write(self, _data):
            raise SerialException("pyserial no disponible en entorno de tests")

        def readline(self):
            return b""

        def reset_input_buffer(self):
            pass

        def reset_output_buffer(self):
            pass

        def flush(self):
            pass

    serial_stub.Serial = Serial
    serial_stub.SerialException = SerialException
    sys.modules["serial"] = serial_stub

try:  # pragma: no cover - optional dependency shim
    import yaml  # type: ignore
except Exception:  # pragma: no cover - tests inject stub
    yaml_stub = types.ModuleType("yaml")

    def safe_load(stream):
        data = stream.read() if hasattr(stream, "read") else stream
        if not data:
            return {}
        try:
            return json.loads(data)
        except Exception:
            return {}

    yaml_stub.safe_load = safe_load
    sys.modules["yaml"] = yaml_stub

collect_ignore = ["scripts/test_serial.py"]
collect_ignore_glob = ["scripts/test_*.py"]
