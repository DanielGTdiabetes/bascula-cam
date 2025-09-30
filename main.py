"""Legacy entry point for running the Báscula Tk application."""

import os, sys, logging

if os.environ.get("BASCULA_UI_AUDIT") == "1":
    _log = logging.getLogger("boot.audit")
    _log.setLevel(logging.DEBUG)
    if not _log.handlers:
        import sys as _s

        h = logging.StreamHandler(_s.stdout)
        h.setFormatter(logging.Formatter("AUDIT %(message)s"))
        _log.addHandler(h)
    _log.propagate = False
    _log.debug(f"PYTHON={sys.executable}")
    _log.debug(f"sys.path[0]={sys.path[0]}")
    try:
        import bascula.ui.app_shell as _sh
        import bascula.ui.views.timer as _tm

        _log.debug(f"app_shell={_sh.__file__}")
        _log.debug(f"timer={_tm.__file__}")
    except Exception as e:  # pragma: no cover - defensive logging
        _log.debug(f"import error: {e}")

from bascula.ui.app import BasculaApp as BasculaAppTk


def main() -> None:
    app = BasculaAppTk()
    app.run()


if __name__ == "__main__":  # pragma: no cover
    main()
