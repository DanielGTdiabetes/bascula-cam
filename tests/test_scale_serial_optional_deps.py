import time


def test_serial_scale_simulation_when_pyserial_missing(monkeypatch):
    from bascula.core import scale_serial

    monkeypatch.setattr(scale_serial, "serial", None, raising=False)
    monkeypatch.setattr(scale_serial, "SerialException", Exception, raising=False)

    started: list[bool] = []

    def fake_run(self):
        started.append(self._simulate)
        self._stop_event.wait(0.01)

    monkeypatch.setattr(scale_serial.SerialScale, "_run", fake_run, raising=False)

    scale = scale_serial.SerialScale(device="/dev/null", baudrate=9600)
    scale.start()
    time.sleep(0.01)
    scale.stop()

    assert scale.is_simulated
    assert started == [True]


def test_parse_weight_line_without_yaml(monkeypatch):
    from bascula.core import scale_serial

    monkeypatch.setattr(scale_serial, "yaml", None, raising=False)

    assert scale_serial._load_scale_config() == {}

    grams, stable = scale_serial.parse_weight_line("5 g")
    assert grams == 5.0
    assert stable is None
