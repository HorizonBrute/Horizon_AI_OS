#!/usr/bin/env python3
"""
horizon_aios_doc_integrity.py — Doc integrity verifier for Horizon AIOS.

Three verifiers:
  canon      — every $HORIZON_* path declared in agents.md exists on disk
  indexes    — skills_sbin, skills_bin, and documentation index tables match reality
  cross-ref  — every $HORIZON_* file reference in .md files resolves to a real path

Cross-ref findings are classified:
  FAIL  — path is missing and not gitignored (genuine gap, e.g. stale rename)
  WARN  — path is gitignored or a known runtime-generated file (expected absent
          from the working copy, will exist after bootstrap)

Usage:
  python horizon_aios_doc_integrity.py [--check] [--canon] [--indexes] [--refs]
  python horizon_aios_doc_integrity.py --handoff <path>

Exit 0 if no findings or only WARNs; exit 1 if any FAILs.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

_vars: Dict[str, Path] = {}

_ENV_NAMES = ["HORIZON_ROOT", "HORIZON_SYSTEM", "HORIZON_DOCS", "HORIZON_ETC", "HORIZON_BIN"]


def _load_env() -> None:
    missing = []
    for name in _ENV_NAMES:
        val = os.environ.get(name)
        if val:
            _vars[name] = Path(val)
        else:
            missing.append(f"${name}")
    if missing:
        sys.exit(f"ERROR — env vars not set: {', '.join(missing)}")


def _resolve(raw: str) -> Optional[Path]:
    """Resolve a $HORIZON_VAR/... string to an absolute Path."""
    m = re.match(r"\$([A-Z_]+)(.*)", raw)
    if not m:
        return None
    name, rest = m.group(1), m.group(2)
    base = _vars.get(name)
    if base is None:
        return None
    rest = rest.lstrip("/\\")
    return base / rest if rest else base


def _rel(path: Path) -> str:
    """Return a human-readable path relative to HORIZON_ROOT."""
    try:
        return str(path.relative_to(_vars["HORIZON_ROOT"])).replace("\\", "/")
    except (ValueError, KeyError):
        return str(path)


# ---------------------------------------------------------------------------
# Git check-ignore
# ---------------------------------------------------------------------------

def _gitignored_set(root: Path, resolved_paths: Set[Path]) -> Set[Path]:
    """Return the subset of resolved_paths that git considers ignored."""
    if not resolved_paths:
        return set()
    rel_strs: List[str] = []
    path_map: Dict[str, Path] = {}
    for p in resolved_paths:
        try:
            rel = str(p.relative_to(root))
            rel_strs.append(rel)
            path_map[rel] = p
        except ValueError:
            pass
    if not rel_strs:
        return set()
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "--stdin", "-z"],
            input="\0".join(rel_strs),
            capture_output=True,
            text=True,
            cwd=str(root),
        )
        # exit 0: at least one path ignored; exit 1: none ignored; 128: not a git repo
        if proc.returncode not in (0, 1):
            return set()
        ignored: Set[Path] = set()
        for token in proc.stdout.split("\0"):
            token = token.strip()
            if token and token in path_map:
                ignored.add(path_map[token])
        return ignored
    except (OSError, subprocess.SubprocessError):
        return set()


# ---------------------------------------------------------------------------
# Placeholder path detection
# (Filters out example/template paths that appear in documentation prose)
# ---------------------------------------------------------------------------

# Path segments that are obviously stand-in names in documentation examples
_PLACEHOLDER_SEGS = frozenset({
    "X", "Y", "Z", "foo", "bar", "baz",
    "MyProject", "my-project", "your-project", "YourProject",
})

# Substrings that indicate a path is a template pattern, not a real file
_PLACEHOLDER_SUBSTRINGS = ("YYYYMMDD", "YYYY-MM-DD", "HHMMSS")


def _is_placeholder(raw: str) -> bool:
    """Return True if raw looks like a documentation example path, not a real file."""
    for sub in _PLACEHOLDER_SUBSTRINGS:
        if sub in raw:
            return True
    parts = raw.replace("\\", "/").split("/")
    for part in parts:
        stem = part.split(".")[0]  # strip extension so "foo.md" matches "foo"
        if stem in _PLACEHOLDER_SEGS or part in _PLACEHOLDER_SEGS:
            return True
    return False


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

class Finding:
    __slots__ = ("level", "cat", "loc", "msg")

    def __init__(self, level: str, cat: str, loc: str, msg: str) -> None:
        self.level = level   # "FAIL" or "WARN"
        self.cat = cat       # "canon", "index", "cross-ref", "handoff"
        self.loc = loc       # file:line or short label
        self.msg = msg

    def __str__(self) -> str:
        return f"{self.level:<4}  {self.cat:<10}  {self.loc:<40}  {self.msg}"


# ---------------------------------------------------------------------------
# 1. Canon verifier
# ---------------------------------------------------------------------------

_BACKTICK_HORIZON_RE = re.compile(r"`(\$HORIZON[A-Z_]+/[^`]+)`")


def _verify_canon() -> List[Finding]:
    """Check every backtick-quoted $HORIZON_* path in agents.md exists on disk."""
    agents_md = _vars["HORIZON_ROOT"] / "agents.md"
    findings: List[Finding] = []

    if not agents_md.exists():
        return [Finding("FAIL", "canon", "agents.md", "file not found")]

    with agents_md.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            for m in _BACKTICK_HORIZON_RE.finditer(line):
                raw = m.group(1)
                resolved = _resolve(raw)
                if resolved is None:
                    findings.append(Finding(
                        "FAIL", "canon", f"agents.md:{lineno}",
                        f"{raw} — unresolvable env var",
                    ))
                elif not resolved.exists():
                    findings.append(Finding(
                        "FAIL", "canon", f"agents.md:{lineno}",
                        f"{raw} — file not found",
                    ))

    return findings


# ---------------------------------------------------------------------------
# 2. Index verifier
# ---------------------------------------------------------------------------

_SKIP_COL0 = {"Skill", "ID (path)", "Index", "Name", "Title", "Purpose", "---", ""}


def _parse_skills_index(index_path: Path) -> Dict[str, int]:
    """Return {skill_name: line_number} from a skills index.md table."""
    result: Dict[str, int] = {}
    with index_path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line.startswith("|") or line.startswith("|---"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3:
                continue
            col0 = parts[1].strip("`").strip()
            if col0 not in _SKIP_COL0 and not col0.startswith("-"):
                result[col0] = lineno
    return result


def _parse_docs_index(index_path: Path) -> Dict[str, int]:
    """Return {repo_relative_path: line_number} from documentation/documentation.index.md.

    New index format: Serial | Filename | Path (from doc root) | Description | Cross-Refs | Status | Type
    Path column (parts[3]) is relative to $HORIZON_DOCS; prepend 'horizon_system/documentation/' for full path.
    """
    result: Dict[str, int] = {}
    docs_prefix = "horizon_system/documentation/"
    with index_path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line.startswith("|") or line.startswith("|---"):
                continue
            parts = [p.strip() for p in line.split("|")]
            # Need at least 8 parts: empty | Serial | Filename | Path | Desc | XRef | Status | Type | empty
            if len(parts) < 8:
                continue
            type_col = parts[7].strip()
            path_col = parts[3].strip("`").strip()
            if type_col == "File" and path_col and path_col not in _SKIP_COL0:
                result[docs_prefix + path_col] = lineno
    return result


def _on_disk_skills(skills_dir: Path) -> Set[str]:
    """Return OS skill names (real dirs and intra-system symlinks with SKILL.md)."""
    result: Set[str] = set()
    if not skills_dir.is_dir():
        return result
    system = _vars["HORIZON_SYSTEM"]
    system_str = str(system).replace("\\", "/").lower()

    for entry in skills_dir.iterdir():
        if not (entry / "SKILL.md").exists():  # follows symlinks
            continue
        if entry.is_symlink():
            try:
                target_str = str(entry.resolve()).replace("\\", "/").lower()
                if target_str.startswith(system_str):
                    result.add(entry.name)
                # else: user-skill symlink outside $HORIZON_SYSTEM — skip
            except OSError:
                pass
        elif entry.is_dir():
            result.add(entry.name)

    return result


def _verify_skills_index(tier: str, index_path: Path, skills_dir: Path) -> List[Finding]:
    findings: List[Finding] = []

    if not index_path.exists():
        return [Finding("FAIL", "index", tier, f"index.md not found at {_rel(index_path)}")]

    sys_ = _vars["HORIZON_SYSTEM"]
    indexed = _parse_skills_index(index_path)
    on_disk = _on_disk_skills(skills_dir)

    # WARN: on disk but not in index
    for name in sorted(on_disk - set(indexed)):
        findings.append(Finding("WARN", "index", tier, f"{name} — on disk but missing from index"))

    # FAIL or WARN: in index but SKILL.md not found
    for name, lineno in indexed.items():
        skill_md = skills_dir / name / "SKILL.md"
        if not skill_md.exists():
            # Check if the skill's canonical home is in the other skills tier (cross-tier symlink
            # not yet registered — expected in dev working copy without a live install).
            other_tier = "skills_bin" if "sbin" in str(skills_dir) else "skills_sbin"
            other_skill_md = sys_ / other_tier / name / "SKILL.md"
            if other_skill_md.exists():
                findings.append(Finding(
                    "WARN", "index",
                    f"{_rel(index_path)}:{lineno}",
                    f"{name} — indexed in {tier} but symlink not registered"
                    f" (canonical home: {other_tier}/{name})",
                ))
            else:
                findings.append(Finding(
                    "FAIL", "index",
                    f"{_rel(index_path)}:{lineno}",
                    f"{name} — indexed but SKILL.md not found",
                ))

    return findings


def _verify_docs_index() -> List[Finding]:
    docs_index = _vars["HORIZON_DOCS"] / "documentation.index.md"
    findings: List[Finding] = []

    if not docs_index.exists():
        return [Finding("FAIL", "index", "docs/documentation.index.md", "file not found")]

    entries = _parse_docs_index(docs_index)
    horizon_root = _vars["HORIZON_ROOT"]

    for rel_path, lineno in entries.items():
        full = horizon_root / rel_path
        if not full.exists():
            findings.append(Finding(
                "FAIL", "index",
                f"{_rel(docs_index)}:{lineno}",
                f"{rel_path} — file not found",
            ))

    return findings


def _verify_indexes() -> List[Finding]:
    findings: List[Finding] = []
    sys_ = _vars["HORIZON_SYSTEM"]
    findings += _verify_skills_index(
        "skills_sbin",
        sys_ / "skills_sbin" / "index.md",
        sys_ / "skills_sbin",
    )
    findings += _verify_skills_index(
        "skills_bin",
        sys_ / "skills_bin" / "index.md",
        sys_ / "skills_bin",
    )
    findings += _verify_docs_index()
    return findings


# ---------------------------------------------------------------------------
# 3. Cross-reference verifier
# ---------------------------------------------------------------------------

# Match $HORIZON_* file path references (require a "." to filter bare directory refs)
_XREF_RE = re.compile(r"\$HORIZON[A-Z_]+/[\w./\-]+\.\w{1,12}")

_SKIP_DIRS = frozenset({"memory", "handoffs", "objectives", "brains", "__pycache__", ".git"})


def _iter_md_files(root: Path):
    for path in root.rglob("*.md"):
        parts_set = set(path.parts)
        if parts_set & _SKIP_DIRS:
            continue
        if path.is_file():
            yield path


def _verify_refs() -> List[Finding]:
    """Check every $HORIZON_* file reference in .md files under $HORIZON_SYSTEM."""
    sys_ = _vars["HORIZON_SYSTEM"]
    horizon_root = _vars["HORIZON_ROOT"]

    # Collect candidate refs: (raw, resolved, display, lineno)
    candidates: List[Tuple[str, Path, str, int]] = []

    for md_file in _iter_md_files(sys_):
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        display = _rel(md_file)
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in _XREF_RE.finditer(line):
                raw = m.group(0)
                if _is_placeholder(raw):
                    continue
                resolved = _resolve(raw)
                if resolved is None or resolved.exists():
                    continue
                candidates.append((raw, resolved, display, lineno))

    # Batch-classify by gitignore status
    unique_missing: Set[Path] = {r for _, r, _, _ in candidates}
    gitignored = _gitignored_set(horizon_root, unique_missing)

    findings: List[Finding] = []
    for raw, resolved, display, lineno in candidates:
        if resolved in gitignored:
            findings.append(Finding(
                "WARN", "cross-ref",
                f"{display}:{lineno}",
                f"{raw} — gitignored (absent from working copy, created at bootstrap)",
            ))
        else:
            findings.append(Finding(
                "FAIL", "cross-ref",
                f"{display}:{lineno}",
                f"{raw} — file not found",
            ))

    return findings


# ---------------------------------------------------------------------------
# 4. Handoff mode
# ---------------------------------------------------------------------------

def _verify_handoff(handoff_path: Path) -> List[Finding]:
    """Parse a handoff's Files Changed section and check each path exists."""
    findings: List[Finding] = []

    if not handoff_path.exists():
        return [Finding("FAIL", "handoff", str(handoff_path), "handoff file not found")]

    text = handoff_path.read_text(encoding="utf-8", errors="replace")
    in_section = False
    horizon_root = _vars["HORIZON_ROOT"]

    for lineno, line in enumerate(text.splitlines(), 1):
        if re.match(r"^#{1,4}\s+Files\s+Changed", line, re.IGNORECASE):
            in_section = True
            continue
        if in_section and re.match(r"^#{1,4}\s+", line):
            break

        if not in_section:
            continue

        # $HORIZON_* backtick-quoted paths
        for m in _BACKTICK_HORIZON_RE.finditer(line):
            raw = m.group(1)
            resolved = _resolve(raw)
            if resolved and not resolved.exists():
                findings.append(Finding(
                    "FAIL", "handoff", f"handoff:{lineno}", f"{raw} — not found",
                ))

        # Repo-relative paths (horizon_system/...)
        for m in re.finditer(r"`?(horizon[\w/.\-]+\.\w{1,10})`?", line):
            rel = m.group(1).strip("`")
            full = horizon_root / rel
            if not full.exists():
                findings.append(Finding(
                    "FAIL", "handoff", f"handoff:{lineno}", f"{rel} — not found",
                ))

    return findings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Horizon AIOS documentation integrity verifier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--check", action="store_true", help="Run all verifiers (default when no flag given)")
    ap.add_argument("--canon", action="store_true", help="Canon verifier only")
    ap.add_argument("--indexes", action="store_true", help="Index verifier only")
    ap.add_argument("--refs", action="store_true", help="Cross-reference verifier only")
    ap.add_argument("--handoff", metavar="PATH", help="Verify paths in a handoff document")
    args = ap.parse_args()

    _load_env()

    findings: List[Finding] = []
    run_all = not any([args.canon, args.indexes, args.refs, args.handoff])

    if run_all or args.check or args.canon:
        findings += _verify_canon()
    if run_all or args.check or args.indexes:
        findings += _verify_indexes()
    if run_all or args.check or args.refs:
        findings += _verify_refs()
    if args.handoff:
        findings += _verify_handoff(Path(args.handoff))

    if not findings:
        print("OK  — no issues found")
        sys.exit(0)

    for f in findings:
        print(f)

    fail_count = sum(1 for f in findings if f.level == "FAIL")
    warn_count = sum(1 for f in findings if f.level == "WARN")
    print()
    print(f"Summary: {fail_count} FAIL, {warn_count} WARN")
    sys.exit(1 if fail_count else 0)


if __name__ == "__main__":
    main()
