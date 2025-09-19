import sys
import types

import bascula.main as entry


class DummyHeadless:
    def run(self):
        return True


def test_main_falls_back_to_headless(monkeypatch):
    monkeypatch.setenv("DISPLAY", "")

    def fake_tk():
        raise entry.tk.TclError("no display")

    monkeypatch.setattr(entry.tk, "Tk", fake_tk)

    dummy_module = types.SimpleNamespace(HeadlessBascula=DummyHeadless)
    monkeypatch.setitem(sys.modules, "bascula.services.headless_main", dummy_module)

    result = entry.main()

    assert result == 0
