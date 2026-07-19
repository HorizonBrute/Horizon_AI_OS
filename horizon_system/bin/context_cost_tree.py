#!/usr/bin/env python3
"""Map Claude Code harness context overhead across the WHOLE AIOS tree.

Brute-force companion to context_cost.py: instead of measuring one path's
upward load, this walks DOWN from $HORIZON_ROOT (default; overridable), finds
every harness auto-load file in the tree (CLAUDE.md / CLAUDE.local.md /
agents.md) plus everything they @-import, de-duplicates, attributes each file
to the directory it physically lives in, and renders the result as an ASCII
tree annotated with per-directory and subtree context cost.

Measurement + @-import resolution are REUSED from context_cost.py (the single
source of truth for tokenization and import semantics) — only the downward tree
walk and rendering are new here.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context_cost import (  # noqa: E402  (reuse the measurement core)
    AUTO_LOAD_NAMES,
    _IMPORT_RESOLVING_NAMES,
    _make_row,
    _read,
    _resolve_imports,
)

# Directories that never carry meaningful harness context and only add noise.
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".idea", ".vscode",
}


def _resolve_root(arg):
    """Target root: explicit arg > $HORIZON_ROOT > error."""
    if arg:
        root = Path(arg)
    elif os.environ.get("HORIZON_ROOT"):
        root = Path(os.environ["HORIZON_ROOT"])
    else:
        print("error: no path given and $HORIZON_ROOT is not set — source your "
              "AIOS profile or pass a path.", file=sys.stderr)
        sys.exit(1)
    root = root.resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        sys.exit(1)
    return root


def scan(root):
    """Return (per_dir, files, external) where per_dir maps a directory Path to
    its accumulated {kb, words, tokens} for auto-load files physically in it,
    files is the list of measured rows, and external is the aggregate for
    auto-load files that resolved OUTSIDE the tree (e.g. ~/.claude imports)."""
    seen = set()
    rows = []
    for dirpath, dirs, filenames in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in filenames:
            if name not in AUTO_LOAD_NAMES:
                continue
            path = (Path(dirpath) / name).resolve()
            if path in seen:
                continue
            content = _read(path)
            if content is None:
                continue
            seen.add(path)
            rows.append(_make_row(path, content, 0, imported_by=None))
            # Only CLAUDE.md / CLAUDE.local.md trigger harness @-import inlining.
            if name in _IMPORT_RESOLVING_NAMES:
                for imp_path, src in _resolve_imports(path, content, seen):
                    imp_content = _read(imp_path)
                    if imp_content is None:
                        continue
                    rows.append(_make_row(imp_path, imp_content, 0, imported_by=src))

    per_dir = {}
    external = {"kb": 0.0, "words": 0, "tokens": 0, "files": 0}
    for r in rows:
        parent = Path(r["path"]).parent
        try:
            parent.relative_to(root)
            inside = True
        except ValueError:
            inside = False
        if inside:
            acc = per_dir.setdefault(parent, {"kb": 0.0, "words": 0, "tokens": 0, "files": 0})
        else:
            acc = external
        acc["kb"] += r["kb"]
        acc["words"] += r["words"]
        acc["tokens"] += r["tokens"]
        acc["files"] += 1
    return per_dir, rows, external


def _subtree_tokens(directory, per_dir):
    """Tokens for this dir plus every descendant dir with weight."""
    total = 0
    for d, acc in per_dir.items():
        if d == directory or _is_ancestor(directory, d):
            total += acc["tokens"]
    return total


def _is_ancestor(anc, desc):
    try:
        desc.relative_to(anc)
        return desc != anc
    except ValueError:
        return False


def _weighted_dirs(root, per_dir):
    """Set of dirs to render: every weighted dir plus all ancestors up to root."""
    keep = {root}
    for d in per_dir:
        keep.add(d)
        cur = d
        while cur != root and root in cur.parents:
            keep.add(cur)
            cur = cur.parent
    return keep


def render_tree(root, per_dir, external):
    lines = []
    total_tokens = sum(a["tokens"] for a in per_dir.values())
    total_kb = round(sum(a["kb"] for a in per_dir.values()), 1)
    total_files = sum(a["files"] for a in per_dir.values())
    keep = _weighted_dirs(root, per_dir)

    def label(directory, name):
        acc = per_dir.get(directory)
        sub = _subtree_tokens(directory, per_dir)
        if acc:
            return (f"{name}  —  {acc['tokens']:,} tok "
                    f"({acc['kb']:.1f} KB, {acc['files']} file"
                    f"{'s' if acc['files'] != 1 else ''})"
                    + (f"   [subtree: {sub:,} tok]" if sub != acc["tokens"] else ""))
        return f"{name}/   [subtree: {sub:,} tok]"

    lines.append(label(root, root.name or str(root)))

    def walk(directory, prefix):
        children = sorted(
            (d for d in keep if d.parent == directory and d != directory),
            key=lambda p: p.name.lower(),
        )
        for i, child in enumerate(children):
            last = i == len(children) - 1
            connector = "└── " if last else "├── "
            lines.append(prefix + connector + label(child, child.name))
            walk(child, prefix + ("    " if last else "│   "))

    walk(root, "")

    lines.append("")
    lines.append(f"Grand total (inside {root.name or root}): "
                 f"{total_files} auto-load file(s) — {total_kb:.1f} KB — "
                 f"~{total_tokens:,} tokens")
    if external["files"]:
        lines.append(f"External (imported from outside the tree, e.g. ~/.claude): "
                     f"{external['files']} file(s) — ~{external['tokens']:,} tokens")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Map harness context overhead across the whole AIOS tree.")
    parser.add_argument("path", nargs="?", default=None,
                        help="Root to scan. Default: $HORIZON_ROOT.")
    parser.add_argument("--json", action="store_true",
                        help="Emit JSON instead of the ASCII tree.")
    args = parser.parse_args()

    root = _resolve_root(args.path)
    per_dir, rows, external = scan(root)

    if args.json:
        out = {
            "root": str(root),
            "directories": [
                {"dir": str(d), **acc} for d, acc in sorted(per_dir.items(),
                                                            key=lambda kv: str(kv[0]))
            ],
            "external": external,
            "total_files": sum(a["files"] for a in per_dir.values()),
            "total_kb": round(sum(a["kb"] for a in per_dir.values()), 1),
            "total_tokens": sum(a["tokens"] for a in per_dir.values()),
        }
        print(json.dumps(out))
    else:
        print(render_tree(root, per_dir, external))


if __name__ == "__main__":
    main()
