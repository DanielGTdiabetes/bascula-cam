from __future__ import annotations

from types import SimpleNamespace

from bascula.system.audio_config import (
    AudioCard,
    configure_system_audio,
    detect_primary_card,
    ensure_asound_conf,
    parse_aplay_output,
    remove_conflicting_overlays,
)


APLAY_SAMPLE = """\
**** List of PLAYBACK Hardware Devices ****
card 0: sndrpihifiberry [snd_rpi_hifiberry_dac], device 0: HiFiBerry DAC HiFi pcm5102a-hifi-0 []
  Subdevices: 1/1
card 1: vc4hdmi0 [vc4-hdmi-0], device 0: MAI PCM i2s-hifi-0 []
  Subdevices: 0/1
"""


def test_parse_aplay_output_and_detection() -> None:
    cards = parse_aplay_output(APLAY_SAMPLE)
    assert len(cards) == 2
    assert cards[0].is_i2s
    assert not cards[1].is_i2s
    assert detect_primary_card(cards) == cards[0]


def test_ensure_asound_conf_writes_and_backups(tmp_path) -> None:
    card = AudioCard(index=0, raw_id="sndrpihifiberry", name="HifiBerry", description="DAC")
    path = tmp_path / "asound.conf"

    # first write
    changed = ensure_asound_conf(card, path)
    assert changed
    content = path.read_text(encoding="utf-8")
    assert "hw:0,0" in content

    # same content -> no change
    assert not ensure_asound_conf(card, path)

    # corrupted file triggers backup and rewrite
    path.write_bytes(b"\x00broken")
    changed = ensure_asound_conf(card, path)
    assert changed
    backups = list(tmp_path.glob("asound.conf.bak-*"))
    assert backups, "expected backup file when repairing corrupt config"


def test_remove_conflicting_overlays(tmp_path) -> None:
    config = tmp_path / "config.txt"
    config.write_text(
        "\n".join(
            [
                "dtoverlay=i2s-mmap",
                "dtoverlay=hifiberry-dac",
                "dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    modified = remove_conflicting_overlays([config])
    assert config in modified
    text = config.read_text(encoding="utf-8")
    assert "pwm-2chan" not in text
    backups = list(tmp_path.glob("config.txt.bak-*"))
    assert backups


def test_configure_system_audio(monkeypatch, tmp_path) -> None:
    asound_path = tmp_path / "asound.conf"
    boot_config = tmp_path / "config.txt"
    boot_config.write_text("dtoverlay=hifiberry-dac\ndtoverlay=pwm-2chan\n", encoding="utf-8")

    def fake_run(cmd, capture_output=True, text=True, check=True):
        if cmd[:2] == ["aplay", "-l"]:
            return SimpleNamespace(stdout=APLAY_SAMPLE, stderr="", returncode=0)
        if cmd[:2] == ["alsactl", "init"]:
            assert cmd[2] == "0"
            return SimpleNamespace(stdout="init ok", stderr="", returncode=0)
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr("bascula.system.audio_config.subprocess_run", fake_run)

    report = configure_system_audio(
        aplay_path="aplay",
        asound_path=asound_path,
        boot_config_paths=[boot_config],
        run_alsactl=True,
    )

    assert report.selected is not None
    assert report.selected.index == 0
    assert report.asound_changed
    assert report.alsactl_ok
    assert boot_config in report.overlays_fixed
    assert "hw:0,0" in asound_path.read_text(encoding="utf-8")
    assert "pwm-2chan" not in boot_config.read_text(encoding="utf-8")
