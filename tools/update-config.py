#!/usr/bin/env python3
"""Update Raspberry Pi config.txt with Bascula-Cam and X735 blocks."""

from __future__ import annotations

import argparse
import pathlib
from typing import List

BASCULA_BEGIN = "# --- Bascula-Cam (Pi 5): begin ---"
BASCULA_END = "# --- Bascula-Cam (Pi 5): end ---"
BASCULA_BLOCK = [
    BASCULA_BEGIN,
    "hdmi_force_hotplug=1",
    "hdmi_group=2",
    "hdmi_mode=87",
    "hdmi_cvt=1024 600 60 3 0 0 0",
    "dtoverlay=vc4-kms-v3d",
    "dtparam=audio=off",
    "dtoverlay=i2s-mmap",
    "dtoverlay=hifiberry-dac",
    "dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4",
    BASCULA_END,
]

X735_BEGIN = "# --- X735 v3: begin ---"
X735_END = "# --- X735 v3: end ---"
X735_BLOCK = [
    X735_BEGIN,
    "dtoverlay=gpio-shutdown,gpio_pin=17,active_low=1,gpio_pull=up",
    "dtoverlay=gpio-poweroff,gpiopin=4,active_low=1",
    X735_END,
]

LEGACY_BLOCKS = [
    ("# --- Bascula-Cam (Pi 5): Video + Audio I2S + PWM ---", "# --- Bascula-Cam (end) ---"),
    (BASCULA_BEGIN, BASCULA_END),
    (X735_BEGIN, X735_END),
]

ENSURE_LINES = [
    "enable_uart=1",
    "dtparam=i2c_arm=on",
    "dtoverlay=disable-bt",
]

REMOVE_LINES_EXACT = {
    "dtoverlay=max98357a",
    "dtoverlay=max98357a,audio=on",
}

REMOVE_PREFIXES = [
    "dtparam=audio=on",
]


def drop_block(lines: List[str], begin: str, end: str) -> List[str]:
    out: List[str] = []
    i = 0
    begin_strip = begin.strip()
    end_strip = end.strip()
    length = len(lines)
    while i < length:
        if lines[i].strip() == begin_strip:
            j = i + 1
            while j < length and lines[j].strip() != end_strip:
                j += 1
            if j < length:
                j += 1
            else:
                j = i + 1
            i = j
            continue
        out.append(lines[i])
        i += 1
    return out


def ensure_section(lines: List[str], section: str) -> List[str]:
    section_lower = section.strip().lower()
    if any(line.strip().lower() == section_lower for line in lines):
        return lines
    if lines and lines[-1].strip():
        lines.append("")
    lines.append(section)
    return lines


def insert_block_after_anchor(lines: List[str], block: List[str], anchor: str) -> List[str]:
    anchor_lower = anchor.strip().lower()
    anchor_index = None
    for idx, line in enumerate(lines):
        if line.strip().lower() == anchor_lower:
            anchor_index = idx
            break
    block_with_spacing = block[:]
    # ensure blank line between block and following content
    if block_with_spacing and block_with_spacing[-1].strip():
        block_with_spacing.append("")

    if anchor_index is None:
        lines = ensure_section(lines, anchor)
        anchor_index = next(
            idx for idx, line in enumerate(lines) if line.strip().lower() == anchor_lower
        )

    insert_at = anchor_index + 1
    # collapse multiple blank lines after anchor
    while insert_at < len(lines) and not lines[insert_at].strip():
        insert_at += 1
    # insert block and ensure a blank line before, unless directly after section header
    if insert_at == anchor_index + 1:
        block_to_insert = block_with_spacing
    else:
        block_to_insert = [""] + block_with_spacing

    return lines[:insert_at] + block_to_insert + lines[insert_at:]


def dedupe_line(lines: List[str], value: str) -> List[str]:
    target = value.strip()
    seen = False
    result: List[str] = []
    for line in lines:
        if line.strip() == target:
            if seen:
                continue
            seen = True
        result.append(line)
    return result


def normalize(lines: List[str]) -> List[str]:
    sanitized: List[str] = []
    for raw in lines:
        stripped = raw.strip()
        if stripped in REMOVE_LINES_EXACT:
            continue
        if any(stripped.startswith(prefix) for prefix in REMOVE_PREFIXES):
            continue
        sanitized.append(raw.rstrip())
    return sanitized




def collapse_blank_lines(lines: List[str]) -> List[str]:
    result: List[str] = []
    previous_blank = False
    for line in lines:
        if line.strip():
            result.append(line)
            previous_blank = False
        else:
            if not previous_blank:
                result.append("")
            previous_blank = True
    return result
def ensure_lines(lines: List[str]) -> List[str]:
    existing = {line.strip(): idx for idx, line in enumerate(lines)}
    for entry in ENSURE_LINES:
        if entry not in existing:
            lines.append(entry)
    return lines


def update_config(path: pathlib.Path) -> None:
    if path.exists():
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
    else:
        lines = []

    # drop legacy blocks first
    for begin, end in LEGACY_BLOCKS:
        lines = drop_block(lines, begin, end)

    lines = normalize(lines)

    lines = ensure_lines(lines)

    # remove global duplicates before inserting the block
    lines = [line for line in lines if line.strip() != "dtoverlay=vc4-kms-v3d"]

    lines = drop_block(lines, BASCULA_BEGIN, BASCULA_END)
    lines = insert_block_after_anchor(lines, BASCULA_BLOCK, "[all]")

    # remove any existing X735 block first
    lines = drop_block(lines, X735_BEGIN, X735_END)

    # place X735 block after Bascula block if possible
    try:
        bascula_end_index = next(
            idx for idx, line in enumerate(lines) if line.strip() == BASCULA_END.strip()
        )
        insertion_point = bascula_end_index + 1
        block_with_spacing = X735_BLOCK[:]
        if block_with_spacing and block_with_spacing[-1].strip():
            block_with_spacing.append("")
        lines = (
            lines[:insertion_point]
            + ([""] if lines[insertion_point:insertion_point + 1] and lines[insertion_point].strip() else [])
            + block_with_spacing
            + lines[insertion_point:]
        )
    except StopIteration:
        lines = insert_block_after_anchor(lines, X735_BLOCK, "[all]")

    lines = dedupe_line(lines, "dtoverlay=vc4-kms-v3d")
    lines = collapse_blank_lines(lines)

    final_text = "\n".join(lines).rstrip() + "\n"
    path.write_text(final_text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update Raspberry Pi config.txt")
    parser.add_argument("config", type=pathlib.Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    update_config(args.config)


if __name__ == "__main__":
    main()
