import math
import time

from bascula.services import scale


def test_dummy_mode_reports_weight_and_stability(monkeypatch):
    updates = []
    fake_values = iter([0.0, 10.0, 10.0, 10.0, 10.0, 10.0])

    def fake_read(self):
        return next(fake_values, 10.0)

    monkeypatch.setattr(scale._DummyScale, "read", fake_read, raising=False)  # type: ignore[attr-defined]

    service = scale.ScaleService(port="__dummy__", decimals=1)
    try:
        assert service.simulated is True

        service.subscribe(lambda weight, stable: updates.append((weight, stable)))

        limit = time.time() + 2.0
        while time.time() < limit and len(updates) < 5:
            time.sleep(0.05)

        assert updates, "no simulated readings captured"
        weights = [w for w, _ in updates]
        assert any(math.isclose(w, 10.0, rel_tol=0.05) for w in weights)
        assert any(stable for _, stable in updates)
        assert service.net_weight >= 0.0
    finally:
        service.stop()
