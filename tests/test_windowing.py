import pytest

from bascula.ui import windowing


class DummyTk:
    def __init__(self):
        self.geometry_value = None
        self.attributes_called = {}
        self.state_value = None
        self.bound = {}
        self.after_scheduled = False
        self._override = False

    def winfo_screenwidth(self):
        return 1024

    def winfo_screenheight(self):
        return 600

    def geometry(self, value):
        self.geometry_value = value

    def attributes(self, key, value=None):
        if value is None:
            return self.attributes_called.get(key)
        self.attributes_called[key] = value

    def state(self, value):
        self.state_value = value

    def bind(self, sequence, func):
        self.bound[sequence] = func

    def overrideredirect(self, value=None):
        if value is None:
            return self._override
        self._override = value

    def after(self, _delay, func):
        self.after_scheduled = True
        func()


class DummyTopLevel(DummyTk):
    pass


def test_apply_kiosk_window_prefs_linux_no_zoom(monkeypatch):
    monkeypatch.delenv("BASCULA_KIOSK_STRICT", raising=False)
    monkeypatch.delenv("BASCULA_KIOSK_HARD", raising=False)
    monkeypatch.setattr(windowing.sys, "platform", "linux", raising=False)
    root = DummyTk()
    try:
        windowing.apply_kiosk_window_prefs(root)
    except Exception as exc:  # pragma: no cover - should not happen
        pytest.fail(f"apply_kiosk_window_prefs raised unexpectedly: {exc}")
    assert root.geometry_value == "1024x600+0+0"
    assert root.attributes_called["-fullscreen"] is True
    assert root.attributes_called["-topmost"] is True
    assert root.state_value is None


def test_apply_kiosk_window_prefs_windows_zoom(monkeypatch):
    monkeypatch.delenv("BASCULA_KIOSK_STRICT", raising=False)
    monkeypatch.setattr(windowing.sys, "platform", "win32", raising=False)
    root = DummyTk()
    windowing.apply_kiosk_window_prefs(root)
    assert root.state_value == "zoomed"


def test_apply_kiosk_window_prefs_strict(monkeypatch):
    monkeypatch.setenv("BASCULA_KIOSK_STRICT", "1")
    monkeypatch.setattr(windowing.sys, "platform", "linux", raising=False)
    root = DummyTk()
    windowing.apply_kiosk_window_prefs(root)
    assert root._override is True
    assert root.after_scheduled is True
    monkeypatch.delenv("BASCULA_KIOSK_STRICT", raising=False)


def test_apply_kiosk_to_toplevel(monkeypatch):
    monkeypatch.setenv("BASCULA_KIOSK_HARD", "1")
    monkeypatch.setattr(windowing.sys, "platform", "linux", raising=False)
    win = DummyTopLevel()
    windowing.apply_kiosk_to_toplevel(win)
    assert win.attributes_called["-topmost"] is True
    assert win._override is True
    monkeypatch.delenv("BASCULA_KIOSK_HARD", raising=False)


def test_apply_kiosk_does_not_crash_on_linux():
    import sys

    tkinter = pytest.importorskip("tkinter")

    from bascula.ui.windowing import apply_kiosk_window_prefs

    sys_platform = sys.platform
    sys.platform = "linux"
    try:
        try:
            root = tkinter.Tk()
        except tkinter.TclError as exc:  # pragma: no cover - depends on environment
            pytest.skip(f"tkinter not available: {exc}")

        try:
            apply_kiosk_window_prefs(root)
        finally:
            root.destroy()
    finally:
        sys.platform = sys_platform
