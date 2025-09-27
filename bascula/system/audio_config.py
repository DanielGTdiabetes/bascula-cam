"""System helpers for configuring ALSA defaults on Raspberry Pi."""
from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

log = logging.getLogger(__name__)

_CARD_RE = re.compile(
    r"^card\s+(?P<index>\d+):\s+(?P<raw>[^\s]+)\s+\[(?P<name>[^\]]+)\],\s+device\s+(?P<device>\d+):\s+(?P<desc>[^\[]*)",
    re.IGNORECASE,
)

_I2S_KEYWORDS = (
    "hifiberry",
    "max98357",
    "sndrpihifiberry",
    "i2s",
    "adau",
    "justboom",
    "fe-pi",
    "allo",
    "pimoroni",
)

_HDMI_KEYWORDS = ("vc4hdmi", "hdmi")


@dataclass(frozen=True)
class AudioCard:
    """Representation of an ALSA playback card."""

    index: int
    raw_id: str
    name: str
    description: str

    @property
    def device_string(self) -> str:
        return f"hw:{self.index},0"

    @property
    def pretty_name(self) -> str:
        base = self.name.strip() or self.raw_id
        desc = self.description.strip()
        return f"{base} – {desc}" if desc else base

    @property
    def fingerprint(self) -> str:
        return f"{self.raw_id} {self.name} {self.description}".lower()

    @property
    def is_i2s(self) -> bool:
        fp = self.fingerprint
        return (not self.is_hdmi) and any(keyword in fp for keyword in _I2S_KEYWORDS)

    @property
    def is_hdmi(self) -> bool:
        fp = self.fingerprint
        return any(keyword in fp for keyword in _HDMI_KEYWORDS)


@dataclass
class ConfigureReport:
    selected: Optional[AudioCard]
    asound_changed: bool
    asound_path: Path
    overlays_fixed: List[Path]
    alsactl_ok: bool


def parse_aplay_output(raw: str) -> List[AudioCard]:
    """Parse the output of ``aplay -l`` into :class:`AudioCard` objects."""

    cards: dict[int, AudioCard] = {}
    for line in raw.splitlines():
        match = _CARD_RE.match(line.strip())
        if not match:
            continue
        device_number = int(match.group("device"))
        index = int(match.group("index"))
        if device_number != 0:
            continue
        if index in cards:
            continue
        cards[index] = AudioCard(
            index=index,
            raw_id=match.group("raw"),
            name=match.group("name"),
            description=match.group("desc").strip(),
        )
    return [cards[key] for key in sorted(cards.keys())]


def list_cards(aplay_path: str = "aplay") -> List[AudioCard]:
    """Return available playback cards using ``aplay``."""

    try:
        result = subprocess_run([aplay_path, "-l"], capture_output=True, text=True, check=True)
    except FileNotFoundError:
        log.warning("aplay not found while listing audio cards")
        return []
    except Exception as exc:  # pragma: no cover - system dependent
        log.warning("Could not run aplay: %s", exc)
        return []
    return parse_aplay_output(result.stdout)


def detect_primary_card(cards: Sequence[AudioCard]) -> Optional[AudioCard]:
    """Pick the preferred playback card (I2S > non-HDMI > first)."""

    for card in cards:
        if card.is_i2s:
            return card
    for card in cards:
        if not card.is_hdmi:
            return card
    return cards[0] if cards else None


def ensure_asound_conf(card: AudioCard, path: Path) -> bool:
    """Ensure ``/etc/asound.conf`` points to the provided card."""

    desired = (
        "# Bascula audio defaults (auto-generated)\n"
        "pcm.!default {\n"
        "  type plug\n"
        f"  slave.pcm \"hw:{card.index},0\"\n"
        "}\n"
        "ctl.!default {\n"
        "  type hw\n"
        f"  card {card.index}\n"
        "}\n"
    )

    path = Path(path)
    current = None
    if path.exists():
        try:
            current = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            current = None
        except Exception as exc:  # pragma: no cover - filesystem dependent
            log.warning("Could not read %s: %s", path, exc)
            current = None
        else:
            if "\x00" in current or "pcm.!default" not in current:
                current = None

    if current is not None and current.strip() == desired.strip():
        log.info("/etc/asound.conf already points to card %s", card.index)
        return False

    if path.exists() and current is None:
        _backup_file(path)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(desired, encoding="utf-8")
    except Exception as exc:  # pragma: no cover - filesystem dependent
        log.error("Failed to write %s: %s", path, exc)
        return False

    log.info("Updated %s -> card %s", path, card.index)
    return True


def remove_conflicting_overlays(paths: Iterable[Path]) -> List[Path]:
    """Remove PWM overlays when I2S overlays are present."""

    modified: List[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:  # pragma: no cover - best effort
            continue
        lines = text.splitlines()
        has_i2s = any(
            line.strip().startswith("dtoverlay=")
            and any(keyword in line.lower() for keyword in ("hifiberry", "max98357", "i2s"))
            for line in lines
        )
        if not has_i2s:
            continue
        filtered = [
            line
            for line in lines
            if "dtoverlay=pwm-2chan" not in line.replace(" ", "")
        ]
        if filtered == lines:
            continue
        _backup_file(path)
        filtered_text = "\n".join(filtered).rstrip() + "\n"
        path.write_text(filtered_text, encoding="utf-8")
        modified.append(path)
        log.info("Removed pwm-2chan overlay from %s", path)
    return modified


def run_alsactl_init(card_index: int) -> bool:
    """Initialise ALSA mixer state for the selected card."""

    try:
        result = subprocess_run(
            ["alsactl", "init", str(card_index)], capture_output=True, text=True, check=True
        )
    except FileNotFoundError:
        log.warning("alsactl not available; skipping mixer initialisation")
        return False
    except Exception as exc:  # pragma: no cover - system dependent
        log.warning("alsactl init for card %s failed: %s", card_index, exc)
        return False

    output = (result.stdout or "").strip()
    if output:
        log.info("alsactl init output: %s", output)
    return True


def configure_system_audio(
    *,
    aplay_path: str = "aplay",
    asound_path: Path | str = "/etc/asound.conf",
    boot_config_paths: Optional[Sequence[Path | str]] = None,
    run_alsactl: bool = True,
) -> ConfigureReport:
    """Configure ALSA defaults for the detected I2S card."""

    cards = list_cards(aplay_path)
    if not cards:
        log.warning("No playback cards detected with %s", aplay_path)
        return ConfigureReport(None, False, Path(asound_path), [], False)

    selected = detect_primary_card(cards)
    if selected is None:
        log.warning("Could not determine a primary audio card")
        return ConfigureReport(None, False, Path(asound_path), [], False)

    log.info(
        "Detected audio cards: %s",
        ", ".join(f"{card.index}:{card.raw_id}" for card in cards),
    )
    log.info(
        "Using card %s (%s)",
        selected.index,
        selected.pretty_name,
    )

    asound_changed = ensure_asound_conf(selected, Path(asound_path))
    overlays_fixed: List[Path] = []
    if boot_config_paths:
        overlays_fixed = remove_conflicting_overlays(Path(p) for p in boot_config_paths)

    alsactl_ok = run_alsactl_init(selected.index) if run_alsactl else False

    return ConfigureReport(selected, asound_changed, Path(asound_path), overlays_fixed, alsactl_ok)


def _backup_file(path: Path) -> None:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = Path(f"{path}.bak-{timestamp}")
    try:
        shutil.copy2(path, backup_path)
        log.info("Created backup %s", backup_path)
    except Exception as exc:  # pragma: no cover - filesystem dependent
        log.debug("Could not create backup for %s: %s", path, exc)


def subprocess_run(*args, **kwargs):
    """Wrapper around :func:`subprocess.run` for ease of testing."""

    from subprocess import run

    return run(*args, **kwargs)


def _default_boot_paths() -> List[Path]:
    return [
        path
        for path in (Path("/boot/firmware/config.txt"), Path("/boot/config.txt"))
        if path.exists()
    ]


def _setup_logging() -> None:
    if not logging.getLogger().handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter("[audio] %(message)s")
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)


def _cli(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Configure ALSA defaults for Bascula")
    parser.add_argument("--aplay", default="aplay", help="Path to the aplay binary")
    parser.add_argument("--asound", default="/etc/asound.conf", help="Target asound.conf path")
    parser.add_argument(
        "--boot-config",
        action="append",
        default=[],
        help="Boot config file to sanitise (can be passed multiple times)",
    )
    parser.add_argument(
        "--skip-alsactl",
        action="store_true",
        help="Skip running alsactl init",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON summary to stdout",
    )
    args = parser.parse_args(argv)

    boot_paths = [Path(p) for p in args.boot_config] or _default_boot_paths()

    report = configure_system_audio(
        aplay_path=args.aplay,
        asound_path=Path(args.asound),
        boot_config_paths=boot_paths,
        run_alsactl=not args.skip_alsactl,
    )

    if args.json:
        payload = {
            "card_index": report.selected.index if report.selected else None,
            "card_id": report.selected.raw_id if report.selected else None,
            "card_name": report.selected.pretty_name if report.selected else None,
            "asound_changed": report.asound_changed,
            "asound_path": str(report.asound_path),
            "overlays_fixed": [str(path) for path in report.overlays_fixed],
            "alsactl_ok": report.alsactl_ok,
        }
        json.dump(payload, sys.stdout)
        sys.stdout.flush()

    return 0 if report.selected else 1


def main() -> int:  # pragma: no cover - CLI entry point
    _setup_logging()
    return _cli()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "AudioCard",
    "ConfigureReport",
    "configure_system_audio",
    "detect_primary_card",
    "ensure_asound_conf",
    "list_cards",
    "parse_aplay_output",
    "remove_conflicting_overlays",
    "run_alsactl_init",
]
