import time
from threading import Event

from bascula.config.settings import ScaleSettings
from bascula.services.scale import ScaleService


def test_scale_service_demo_mode(monkeypatch):
    monkeypatch.setenv("BASCULA_DEMO", "1")
    service = ScaleService(ScaleSettings())
    values = []
    event = Event()

    def callback(value, stable, unit):
        values.append((value, stable, unit))
        event.set()

    service.subscribe(callback)
    service.start()

    assert event.wait(3.0)
    service.tare()
    service.zero()
    service.set_decimals(1)
    mode = service.toggle_units()
    assert mode in {"g", "ml"}
    service.stop()

    assert values
