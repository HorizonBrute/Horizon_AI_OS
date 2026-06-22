#!/usr/bin/env python3
"""Measure Claude Code harness context overhead (CLAUDE.md / agents.md / @-imports) for a path."""

import argparse
import json
import os
import sys
from pathlib import Path

AUTO_LOAD_NAMES = ("CLAUDE.md", "CLAUDE.local.md", "agents.md")

# Only these filenames trigger harness @-import resolution.
# agents.md contains plain-text AI instructions that may reference @paths
# but the harness does NOT inline them — do not recurse into them.
_IMPORT_RESOLVING_NAMES = frozenset({"CLAUDE.md", "CLAUDE.local.md"})


def _read(path: Path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _resolve_imports(file_path: Path, content: str, seen: set) -> list:
    """Return list of (resolved_path, source_file) for @-imports in content, recursing."""
    results = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("@"):
            continue
        ref = stripped[1:].strip()
        if not ref:
            continue
        # Resolve relative to the file's directory; absolute paths used as-is.
        candidate = Path(ref) if os.path.isabs(ref) else (file_path.parent / ref)
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        content2 = _read(resolved)
        if content2 is None:
            continue
        seen.add(resolved)
        results.append((resolved, file_path))
        results.extend(_resolve_imports(resolved, content2, seen))
    return results


def collect(target_dir: Path) -> list:
    """
    Walk up from target_dir to the filesystem root collecting auto-loaded files,
    then include ~/.claude/. Returns list of dicts (ordered: ancestor-first).
    """
    # Build ancestor chain from root to target.
    # User config (~/.claude) is treated as level 1 (farthest / most global).
    resolved = target_dir.resolve()
    ancestors = list(reversed(resolved.parents)) + [resolved]
    search_dirs = [Path.home() / ".claude"] + ancestors

    seen_paths: set = set()
    rows = []
    level = 0

    for directory in search_dirs:
        level += 1
        for name in AUTO_LOAD_NAMES:
            candidate = directory / name
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if resolved in seen_paths:
                continue
            content = _read(resolved)
            if content is None:
                continue
            seen_paths.add(resolved)
            rows.append(_make_row(resolved, content, level, imported_by=None))
            # Only CLAUDE.md and CLAUDE.local.md trigger harness @-import inlining.
            # agents.md uses @-references as plain AI instructions; the harness
            # does NOT inline them, so do not recurse.
            if candidate.name in _IMPORT_RESOLVING_NAMES:
                for imp_path, src_file in _resolve_imports(resolved, content, seen_paths):
                    imp_content = _read(imp_path)
                    if imp_content is None:
                        continue
                    rows.append(_make_row(imp_path, imp_content, level, imported_by=src_file))

    return rows


def _make_row(path: Path, content: str, level: int, imported_by) -> dict:
    byte_count = len(content.encode("utf-8"))
    words = len(content.split())
    tokens = round(words * 1.33)
    return {
        "level": level,
        "path": str(path),
        "kb": round(byte_count / 1024, 1),
        "words": words,
        "tokens": tokens,
        "imported_by": str(imported_by) if imported_by else None,
    }


def _print_table(target: Path, rows: list):
    header_path = str(target)
    # Use ASCII dash if the terminal can't handle the box-drawing character.
    try:
        "─".encode(sys.stdout.encoding or "utf-8")
        sep = "─" * 77
    except (UnicodeEncodeError, LookupError):
        sep = "-" * 77

    print(f"Context overhead from: {header_path}")
    print(sep)
    print(f" {'Level':>5}  {'Source':<44} {'KB':>5}  {'Words':>6}  {'~Tokens':>7}")
    print(sep)

    for r in rows:
        label = r["path"]
        if r["imported_by"]:
            label += "  (@-import)"
        # Truncate long paths for display
        max_src = 44
        display = label if len(label) <= max_src else "..." + label[-(max_src - 3):]
        print(f" {r['level']:>5}  {display:<44} {r['kb']:>5.1f}  {r['words']:>6}  {r['tokens']:>7}")

    print(sep)
    total_kb     = round(sum(r["kb"] for r in rows), 1)
    total_words  = sum(r["words"] for r in rows)
    total_tokens = sum(r["tokens"] for r in rows)
    print(f" {'TOTAL':<50} {total_kb:>5.1f}  {total_words:>6}  {total_tokens:>7}")
    print(sep)


def main():
    parser = argparse.ArgumentParser(
        description="Measure Claude Code harness context overhead for a given path."
    )
    parser.add_argument(
        "path", nargs="?", default=None,
        help="File or directory to evaluate. Default: CWD."
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit compact JSON instead of the table."
    )
    args = parser.parse_args()

    raw = Path(args.path) if args.path else Path.cwd()
    target = raw.resolve()
    if target.is_file():
        target = target.parent

    if not target.is_dir():
        print(f"error: not a directory: {target}", file=sys.stderr)
        sys.exit(1)

    rows = collect(target)

    if args.json:
        out = {
            "path": str(target),
            "files": rows,
            "total_kb": round(sum(r["kb"] for r in rows), 1),
            "total_words": sum(r["words"] for r in rows),
            "total_tokens": sum(r["tokens"] for r in rows),
        }
        print(json.dumps(out))
    else:
        _print_table(target, rows)


if __name__ == "__main__":
    main()
