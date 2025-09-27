from bascula.config.settings import Settings


def test_settings_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("BASCULA_SETTINGS_DIR", str(tmp_path))
    settings = Settings.load()
    settings.general.sound_enabled = False
    settings.scale.calibration_factor = 2.5
    settings.network.miniweb_pin = "9999"
    settings.diabetes.ns_url = "https://example.com"
    settings.save()

    loaded = Settings.load()
    assert loaded.general.sound_enabled is False
    assert loaded.scale.calibration_factor == 2.5
    assert loaded.network.miniweb_pin == "9999"
    assert loaded.diabetes.ns_url == "https://example.com"
