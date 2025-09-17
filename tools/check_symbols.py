from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

missing: list[str] = []
try:
    from bascula.ui.scaling import auto_apply_scaling  # noqa: F401
except Exception:
    missing.append("bascula.ui.scaling.auto_apply_scaling")

if missing:
    print("[err] Símbolos ausentes:", ", ".join(missing))
    sys.exit(1)

print("[ok] Símbolos UI verificados")
