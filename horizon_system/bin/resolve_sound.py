#!/usr/bin/env python3
"""
Resolve an AIOS event name to a sound file path.

Usage:
    python resolve_sound.py <event> [--harness NAME] [--cwd PATH]

Prints the absolute path to the sound file, or nothing if unmapped.
Exit 0 in both cases — a missing sound is not an error.

Resolution order:
    1. aios_sounds.conf at nearest ancestor of cwd (up to $HORIZON_ROOT)
    2. $HORIZON_SYSTEM/harness_configs/<harness>/sounds.map  (if --harness given)
    3. $HORIZON_SYSTEM/sounds/sounds.map

Hook usage:
    sound=$(python "$HORIZON_BIN/resolve_sound.py" task_complete --harness claude_code)
    [ -n "$sound" ] && bash "$HORIZON_SYSTEM/sounds/play_sound.sh" "$sound"
"""

import argparse
import os
import sys
from pathlib import Path

HORIZON_BIN    = Path(__file__).resolve().parent          # horizon_system/bin/
HORIZON_SYSTEM = HORIZON_BIN.parent                       # horizon_system/
HORIZON_ROOT   = HORIZON_SYSTEM.parent                    # repo root
SOUNDS_DIR     = HORIZON_SYSTEM / "sounds"
DEFAULT_MAP    = SOUNDS_DIR / "sounds.map"
OVERRIDE_FILE = "aios_sounds.conf"


def _parse(path: Path) -> dict:
    out = {}
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip()
                if k and v:
                    out[k] = v
    except OSError:
        pass
    return out


def _abs(sound_val: str, config_dir: Path) -> str | None:
    """Return absolute path for a sound value, or None if file not found."""
    p = Path(sound_val)
    if p.is_absolute():
        return str(p) if p.exists() else None
    for candidate in (SOUNDS_DIR / sound_val, config_dir / sound_val):
        if candidate.exists():
            return str(candidate)
    return None


def _find_override(cwd: Path) -> Path | None:
    current = cwd.resolve()
    root = HORIZON_ROOT.resolve()
    while True:
        candidate = current / OVERRIDE_FILE
        if candidate.exists():
            return candidate
        if current == root or current.parent == current:
            return None
        current = current.parent


def main():
    p = argparse.ArgumentParser(description="Resolve AIOS event to sound file")
    p.add_argument("event")
    p.add_argument("--harness", metavar="NAME")
    p.add_argument("--cwd", default=os.getcwd())
    args = p.parse_args()

    cwd = Path(args.cwd)

    sources = []

    override = _find_override(cwd)
    if override:
        sources.append((override, override.parent))

    if args.harness:
        hmap = HORIZON_SYSTEM / "harness_configs" / args.harness / "sounds.map"
        sources.append((hmap, SOUNDS_DIR))

    sources.append((DEFAULT_MAP, SOUNDS_DIR))

    for map_path, base_dir in sources:
        mapping = _parse(map_path)
        if args.event in mapping:
            result = _abs(mapping[args.event], base_dir)
            if result:
                print(result)
                return


if __name__ == "__main__":
    main()
