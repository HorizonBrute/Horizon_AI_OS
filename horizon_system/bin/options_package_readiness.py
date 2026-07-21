#!/usr/bin/env python3
"""options_package_readiness.py  -  is this repo ready to deploy as a Horizon AIOS Options Package?

Point this at an on-disk repo OR a git URL and it reports, rule by rule, whether the repo meets the
Options Package Readiness Standard (documentation/system/aios_options_package_readiness.md). It is the
executable form of that standard: every finding is keyed to a PKG-* rule ID in the doc.

    python options_package_readiness.py <path-or-git-url> [--json] [--strict]

STATIC ANALYSIS ONLY. This tool never executes the target installer. It parses the code and inspects
the tree. A PASS therefore means the package is *structurally* ready to test  -  the dev must still run a
real install in a sandbox to prove it actually works. This is deliberate: an installer's job includes
wiring itself into the AIOS update pass and can create scheduled tasks / cron jobs, none of which are
safe to trigger from a readiness check.

Cross-platform, standard-library only (Python 3.8+). Brain-readable OS-tier utility.

Exit codes: 0 = READY (or READY WITH WARNINGS, unless --strict), 1 = NOT READY (or warnings under
--strict), 2 = usage / target error.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# --------------------------------------------------------------------------- required registry fields
# Per aios_options_package_readiness.md (PKG-R2) and the LAPP reference installer.
REQUIRED_REGISTRY_FIELDS = [
    "name", "version", "clone_path", "upstream", "remotes",
    "role", "pull_only", "sync", "install_entrypoint", "payload",
]
REQUIRED_SUBCOMMANDS = ["install", "uninstall", "update", "status"]

# Scheduling primitives an installer might use to create recurring jobs (PKG-S1).
SCHEDULER_PATTERNS = {
    "windows-task-scheduler": [r"schtasks", r"Register-ScheduledTask", r"ScheduledTasks"],
    "cron": [r"crontab", r"/etc/cron", r"cron\.d"],
    "launchd": [r"launchctl", r"LaunchAgents", r"LaunchDaemons"],
    "systemd-timer": [r"systemctl", r"\.timer\b"],
}
# Removal primitives that a conforming uninstall should use to tear those jobs back down (PKG-S3).
SCHEDULER_REMOVAL = [
    r"schtasks[^\n]*/delete", r"Unregister-ScheduledTask",
    r"crontab[^\n]*-r", r"launchctl[^\n]*(unload|bootout)",
    r"systemctl[^\n]*disable",
]

LEVELS = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL", "INFO": "INFO"}


class Finding:
    __slots__ = ("rule", "level", "message")

    def __init__(self, rule: str, level: str, message: str):
        self.rule = rule
        self.level = level
        self.message = message

    def as_dict(self) -> dict:
        return {"rule": self.rule, "level": self.level, "message": self.message}


# --------------------------------------------------------------------------- target resolution
def looks_like_url(target: str) -> bool:
    return (
        target.startswith(("http://", "https://", "git@", "ssh://", "git://"))
        or target.endswith(".git")
    )


def resolve_target(target: str):
    """Return (repo_path, tempdir_or_None, source_label). Clones a URL to a temp dir."""
    if looks_like_url(target):
        if not shutil.which("git"):
            _fatal("target is a git URL but 'git' is not on PATH.")
        tmp = Path(tempfile.mkdtemp(prefix="opr_"))
        print(f"Cloning {target} (shallow) ...", file=sys.stderr)
        res = subprocess.run(
            ["git", "clone", "--depth", "1", target, str(tmp / "repo")],
            capture_output=True, text=True, check=False,
        )
        if res.returncode != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            _fatal(f"git clone failed: {res.stderr.strip()}")
        return tmp / "repo", tmp, target
    p = Path(target).expanduser().resolve()
    if not p.is_dir():
        _fatal(f"not a directory (and not a URL): {p}")
    return p, None, str(p)


def _fatal(msg: str):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


# --------------------------------------------------------------------------- installer discovery
def find_installer(repo: Path):
    """Return (installer_path, package_name, at_canonical_location)."""
    canonical = sorted((repo / "aios" / "install").glob("horizon_*_package.py")) \
        if (repo / "aios" / "install").is_dir() else []
    if canonical:
        return canonical[0], _name_from(canonical[0]), True
    anywhere = sorted(repo.rglob("horizon_*_package.py"))
    if anywhere:
        return anywhere[0], _name_from(anywhere[0]), False
    return None, None, False


def _name_from(installer: Path) -> str:
    m = re.match(r"horizon_(.+)_package\.py$", installer.name)
    return m.group(1) if m else "?"


# --------------------------------------------------------------------------- static analysis helpers
def stdlib_names() -> set:
    names = getattr(sys, "stdlib_module_names", None)
    if names:
        return set(names)
    # Fallback allowlist for < 3.10  -  the modules a stdlib-only installer would plausibly use.
    return {
        "__future__", "argparse", "json", "os", "sys", "re", "shutil", "subprocess",
        "pathlib", "datetime", "tempfile", "typing", "collections", "itertools",
        "functools", "textwrap", "glob", "hashlib", "io", "time", "platform",
        "urllib", "http", "socket", "logging", "dataclasses", "enum", "abc",
        "string", "math", "stat", "tarfile", "zipfile", "csv", "configparser",
    }


def local_module_names(installer: Path) -> set:
    """Sibling .py files / packages count as local imports, not third-party deps."""
    d = installer.parent
    names = {p.stem for p in d.glob("*.py")}
    names |= {p.name for p in d.iterdir() if p.is_dir() and (p / "__init__.py").exists()}
    return names


def top_level_imports(tree: ast.AST) -> set:
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import → local
            if node.module:
                mods.add(node.module.split(".")[0])
    return mods


def string_constants(tree: ast.AST) -> list:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
    return out


def defined_functions(tree: ast.AST) -> set:
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}


# --------------------------------------------------------------------------- cron sanity check
_CRON_FIELD_MAX = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]


def validate_cron(expr: str):
    """Lenient 5-field cron validator. Returns a list of problems (empty == looks valid)."""
    fields = expr.split()
    if len(fields) not in (5, 6):
        return [f"expected 5 (or 6) fields, got {len(fields)}"]
    problems = []
    for i, field in enumerate(fields[:5]):
        lo, hi = _CRON_FIELD_MAX[i]
        for token in field.split(","):
            base = token.split("/")[0]
            if base == "*" or base == "":
                continue
            for part in base.split("-"):
                if part == "":
                    continue
                if not part.isdigit():
                    problems.append(f"field {i + 1}: non-numeric '{part}'")
                    continue
                v = int(part)
                if not (lo <= v <= hi):
                    problems.append(f"field {i + 1}: {v} out of range {lo}-{hi}")
    return problems


def find_cron_expressions(strings: list) -> list:
    """Pick string literals that structurally look like a cron line (5-6 space-separated
    fields of digits/*/,-/)."""
    out = []
    pat = re.compile(r"^[\d*,/\-]+(?:\s+[\d*,/\-]+){4,5}$")
    for s in strings:
        s2 = s.strip()
        if pat.match(s2):
            out.append(s2)
    return out


# --------------------------------------------------------------------------- the checks
def run_checks(repo: Path) -> list:
    findings = []

    def add(rule, level, msg):
        findings.append(Finding(rule, level, msg))

    installer, name, canonical = find_installer(repo)

    # ---- PKG-A1: installer present at the canonical location
    if installer is None:
        add("PKG-A1", "FAIL",
            "No installer found. Expected aios/install/horizon_<name>_package.py. "
            "Without an installer this repo cannot deploy as an Options Package.")
        return findings  # nothing else is meaningful without an installer
    rel = installer.relative_to(repo).as_posix()
    if canonical:
        add("PKG-A1", "PASS", f"Installer found at canonical location: {rel}")
    else:
        add("PKG-A1", "WARN",
            f"Installer found at {rel}, not at aios/install/horizon_<name>_package.py. "
            "Move it to the canonical location.")

    # ---- parse it
    try:
        source = installer.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError) as exc:
        add("PKG-I0", "FAIL", f"Installer does not parse as Python: {exc}")
        return findings
    strings = string_constants(tree)
    funcs = defined_functions(tree)
    blob = source  # raw text for pattern scans the AST would miss (e.g. subprocess arg lists)

    # ---- PKG-N1: namespace
    if installer.name.startswith("horizon_aios_"):
        add("PKG-N1", "FAIL",
            f"Installer is named {installer.name}: the horizon_aios_* prefix is reserved for the OS "
            "core. Rename to horizon_<name>_package.py.")
    else:
        add("PKG-N1", "PASS", f"Namespace ok: {installer.name} (package '<{name}>').")
    pkg_name_literals = [s for s in strings if s.startswith("horizon_aios_")]
    if pkg_name_literals:
        add("PKG-N1", "WARN",
            f"Found horizon_aios_* literals in the installer ({pkg_name_literals[:3]}); make sure the "
            "package does not claim the OS-core namespace.")

    # ---- PKG-I1: the four subcommands
    has_subparsers = ("add_subparsers" in blob)
    present = [c for c in REQUIRED_SUBCOMMANDS if c in strings]
    missing = [c for c in REQUIRED_SUBCOMMANDS if c not in present]
    fn_evidence = [c for c in REQUIRED_SUBCOMMANDS if f"cmd_{c}" in funcs]
    if not has_subparsers:
        add("PKG-I1", "FAIL",
            "No argparse subcommands detected (no add_subparsers). Installer must expose "
            "install / uninstall / update / status.")
    elif missing:
        add("PKG-I1", "FAIL",
            f"Missing subcommand(s): {', '.join(missing)}. "
            f"Detected: {', '.join(present) or 'none'}. "
            f"(cmd_* handlers found for: {', '.join(fn_evidence) or 'none'}).")
    else:
        add("PKG-I1", "PASS",
            f"All four subcommands referenced: {', '.join(REQUIRED_SUBCOMMANDS)}.")

    # ---- PKG-I2: stdlib-only
    imports = top_level_imports(tree)
    allowed = stdlib_names() | local_module_names(installer)
    third_party = sorted(m for m in imports if m and m not in allowed)
    if third_party:
        add("PKG-I2", "FAIL",
            f"Non-stdlib imports: {', '.join(third_party)}. The installer must be standard-library "
            "only so it runs on any AIOS host without a dependency install.")
    else:
        add("PKG-I2", "PASS", "Installer imports are standard-library (or local) only.")

    # ---- PKG-I3: --horizon-root override (SHOULD)
    if "--horizon-root" in blob or "horizon_root" in blob:
        add("PKG-I3", "PASS", "Installer accepts a --horizon-root override.")
    else:
        add("PKG-I3", "WARN",
            "No --horizon-root override detected; installer should not hard-depend on env alone.")

    # ---- PKG-R1 / PKG-R2: registration
    registers = ("horizon_deployed_packages" in blob)
    if not registers:
        add("PKG-R1", "FAIL",
            "No reference to the deployed-packages registry (horizon_deployed_packages*.json). "
            "install must register the package so the AIOS sync can protect/update/inventory it.")
    else:
        add("PKG-R1", "PASS", "References the deployed-packages registry.")
        if "horizon_deployed_packages/v1" not in strings:
            add("PKG-R2", "WARN",
                "Registry schema id 'horizon_deployed_packages/v1' not found as a literal; confirm the "
                "written entry declares the schema.")
        missing_fields = [f for f in REQUIRED_REGISTRY_FIELDS if f not in strings]
        if missing_fields:
            add("PKG-R2", "WARN",
                f"Registry field key(s) not seen as literals: {', '.join(missing_fields)}. "
                "The entry should carry all of: " + ", ".join(REQUIRED_REGISTRY_FIELDS) + ".")
        else:
            add("PKG-R2", "PASS", "All required registry field keys present as literals.")

    # ---- PKG-D1: pull-only deployment clone
    pull_only = any(t in blob for t in ("pull_only", "set-url", "--push", "is_deployment", "deployment"))
    if pull_only:
        add("PKG-D1", "PASS", "Deployment / pull-only handling detected.")
    else:
        add("PKG-D1", "WARN",
            "No pull-only / deployment-clone handling detected. A deployment clone should be made "
            "push-disabled so it can only receive from upstream.")

    # ---- PKG-D2: update is upstream-authoritative
    if "update" in present:
        has_fetch = "fetch" in blob
        has_reset_hard = ("reset" in blob and "--hard" in blob)
        if has_fetch and has_reset_hard:
            add("PKG-D2", "PASS", "update looks upstream-authoritative (git fetch + reset --hard).")
        else:
            add("PKG-D2", "WARN",
                "update present but no clear 'git fetch' + 'git reset --hard <upstream>'. "
                "Deployment updates should overwrite local, not merge.")

    # ---- PKG-L1: machine-local file hygiene
    materializes_local = (".local." in blob)
    exclude_hygiene = any(t in blob for t in ("info/exclude", "info", "check-ignore")) and "exclude" in blob
    if materializes_local:
        if exclude_hygiene:
            add("PKG-L1", "PASS",
                "Materializes .local.* files and manages ignore via .git/info/exclude.")
        else:
            add("PKG-L1", "WARN",
                "Materializes .local.* files but no .git/info/exclude handling seen. Machine-local "
                "files must be ignored via .git/info/exclude, never the tracked .gitignore.")
    elif ".gitignore" in blob and "info/exclude" not in blob:
        add("PKG-L1", "WARN",
            "Writes to a tracked .gitignore; machine-local artifacts should use .git/info/exclude "
            "(the tracked .gitignore is overwritten by the official sync lane).")

    # ---- PKG-U1: uninstall reverses + deregisters
    if "uninstall" in present:
        deregisters = registers and ("uninstall" in blob) and (
            "payload" in strings or "packages" in blob or "cmd_uninstall" in funcs)
        if deregisters:
            add("PKG-U1", "PASS", "uninstall present and appears to reverse the deploy / deregister.")
        else:
            add("PKG-U1", "WARN",
                "uninstall present but no clear deregister / payload-driven reversal detected.")

    # ---- PKG-S1..S3: scheduled tasks / cron
    scheduler_hits = {}
    for kind, pats in SCHEDULER_PATTERNS.items():
        for pat in pats:
            if re.search(pat, blob):
                scheduler_hits.setdefault(kind, []).append(pat)
    if scheduler_hits:
        kinds = ", ".join(scheduler_hits)
        add("PKG-S1", "INFO",
            f"Installer appears to create scheduled jobs ({kinds}). STATIC CHECK  -  these are not "
            "triggered here; verify them after a real install.")
        # PKG-S2: cron syntax sanity
        crons = find_cron_expressions(strings)
        cron_relevant = "cron" in scheduler_hits
        if cron_relevant and crons:
            bad = []
            for expr in crons:
                probs = validate_cron(expr)
                if probs:
                    bad.append((expr, probs))
            if bad:
                for expr, probs in bad:
                    add("PKG-S2", "WARN", f"cron expression '{expr}': {'; '.join(probs)}")
            else:
                add("PKG-S2", "PASS",
                    f"cron expression(s) parse as valid: {', '.join(crons)}")
        elif cron_relevant:
            add("PKG-S2", "INFO",
                "cron scheduling referenced but no literal cron expression found to sanity-check "
                "(it may be built at runtime).")
        # PKG-S3: uninstall tears the jobs back down
        removes = any(re.search(pat, blob) for pat in SCHEDULER_REMOVAL)
        if removes:
            add("PKG-S3", "PASS", "A scheduled-job removal call is present (uninstall can tear down).")
        else:
            add("PKG-S3", "WARN",
                "Installer creates scheduled jobs but no removal call (schtasks /delete, crontab -r, "
                "Unregister-ScheduledTask, launchctl bootout, systemctl disable) was found. uninstall "
                "should remove what install scheduled.")
    else:
        add("PKG-S1", "INFO", "No scheduled-task / cron creation detected in the installer.")

    # ---- PKG-A2 / PKG-A3: anatomy
    if (repo / "core").is_dir():
        add("PKG-A2", "PASS", "core/ present (expected home of the standalone feature).")
    else:
        add("PKG-A2", "WARN",
            "No core/ directory. The standard expects the standalone feature under core/ "
            "(SHOULD, not MUST  -  a single-file package may differ).")
    if (repo / "docs").is_dir():
        add("PKG-A3", "PASS", "docs/ present.")
    else:
        add("PKG-A3", "WARN", "No docs/ directory (design notes / ADRs / examples expected there).")

    # ---- PKG-U2: preserves user data (human judgment)
    add("PKG-U2", "INFO",
        "PKG-U2 (uninstall preserves user-created data) is a human-judgment rule  -  confirm by reading "
        "cmd_uninstall.")

    return findings


# --------------------------------------------------------------------------- reporting
def verdict_of(findings: list) -> str:
    levels = {f.level for f in findings}
    if "FAIL" in levels:
        return "NOT READY"
    if "WARN" in levels:
        return "READY WITH WARNINGS"
    return "READY"


def print_report(source_label: str, installer_rel, name, findings: list, verdict: str):
    bar = "=" * 72
    print(bar)
    print("Horizon AIOS  -  Options Package Readiness (STATIC ANALYSIS ONLY)")
    print(bar)
    print(f"target    : {source_label}")
    print(f"installer : {installer_rel or '(none found)'}")
    print(f"package   : <{name or '?'}>")
    print()
    order = {"FAIL": 0, "WARN": 1, "INFO": 2, "PASS": 3}
    for f in sorted(findings, key=lambda x: (order.get(x.level, 9), x.rule)):
        print(f"  [{f.level:<4}] {f.rule:<8} {f.message}")
    counts = {lvl: sum(1 for f in findings if f.level == lvl) for lvl in ("PASS", "WARN", "FAIL", "INFO")}
    print()
    print(bar)
    print(f"VERDICT: {verdict}   "
          f"(pass={counts['PASS']} warn={counts['WARN']} fail={counts['FAIL']} info={counts['INFO']})")
    print(bar)
    print("Static only: no installer code was executed. A clean result means the package is "
          "STRUCTURALLY ready  -  now run a real install in a sandbox to confirm it works.")


def main():
    ap = argparse.ArgumentParser(
        description="Check whether a repo is ready to deploy as a Horizon AIOS Options Package "
                    "(static analysis; the installer is never executed).")
    ap.add_argument("target", help="path to an on-disk repo, or a git URL to shallow-clone.")
    ap.add_argument("--json", action="store_true", help="emit a JSON report instead of text.")
    ap.add_argument("--strict", action="store_true", help="exit non-zero on warnings, not just failures.")
    args = ap.parse_args()

    repo, tmp, source_label = resolve_target(args.target)
    try:
        installer, name, _ = find_installer(repo)
        installer_rel = installer.relative_to(repo).as_posix() if installer else None
        findings = run_checks(repo)
        verdict = verdict_of(findings)

        if args.json:
            print(json.dumps({
                "target": source_label,
                "installer": installer_rel,
                "package_name": name,
                "verdict": verdict,
                "findings": [f.as_dict() for f in findings],
                "counts": {lvl: sum(1 for f in findings if f.level == lvl)
                           for lvl in ("PASS", "WARN", "FAIL", "INFO")},
            }, indent=2))
        else:
            print_report(source_label, installer_rel, name, findings, verdict)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)

    has_fail = any(f.level == "FAIL" for f in findings)
    has_warn = any(f.level == "WARN" for f in findings)
    if has_fail or (args.strict and has_warn):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
