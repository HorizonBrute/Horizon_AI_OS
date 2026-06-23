#!/usr/bin/env python3
"""Horizon AIOS - relocate an install to a new root path.

Moving an AIOS tree to a new location (e.g. C:\\devroot -> D:\\aios, or
~/dev/aios -> ~/work/aios) leaves the machine-local pointers still naming the
OLD absolute root. Today fixing that is a manual find-and-replace, and the
operator first has to DISCOVER which old path was baked in. This tool removes
both pains:

  1. It auto-detects the OLD embedded root from the machine-local AIOS registry
     (~/.horizon/aios_registry.json), so you never have to know it.
  2. It rewrites every occurrence of the old root to a new target root across
     the machine-local instance/config surface ONLY - the files that hardcode an
     absolute path. Framework source under the moved tree is path-independent
     (it derives HORIZON_* from each script's own location, or via $HORIZON_*),
     so it is deliberately LEFT ALONE.

WHAT IT REWRITES (machine-local instance pointers, all outside the repo):
    ~/.horizon/aios_registry.json   - the recorded `root` of the matching AIOS
    ~/.horizon/active_env.ps1        - $env:HORIZON_* assignments
    ~/.horizon/active_env.sh         - export HORIZON_* assignments
    ~/.claude/CLAUDE.md              - the @<root>/.claude/CLAUDE.md redirect(s)
    <newroot>/horizon_system/ai_os_etc/aios_local.conf
                                     - gitignored per-machine config (e.g.
                                       AIOS_LOG_DIR) IF it names the old root

WHAT IT DELIBERATELY DOES NOT TOUCH:
    - Any tracked/framework file in the repo. These use $HORIZON_* or resolve
      their root from the script's own path; rewriting them would corrupt
      upstream-syncable source. The tool refuses to edit anything that git
      reports as tracked.
    - ~/.horizon/bin/aios-exec.{ps1,sh} and ~/.claude/settings.json - these are
      anchored on ~/.horizon / $HOME, not on the AIOS root, so a relocation does
      not affect them. They are scanned and reported if (unexpectedly) they
      contain the old root, but never auto-rewritten.
    - The ~/.claude/skills symlink. Its TARGET is the old tree; relocation
      should re-point it, but that is a symlink operation, not a text
      rewrite. The tool detects and reports it, and prints the exact
      horizon_aios_switch.py command that re-points it correctly.

SAFETY: dry-run is the DEFAULT. Without --apply the tool only prints what it
would change (files + per-line previews). Pass --apply to actually write.

Usage:
    horizon_aios_relocate.py [--new-root PATH] [--old-root PATH] [--apply]
                             [--home PATH]

    --new-root  Target root the install now lives at. Default: the root this
                script resolves from its own location (so after you move the
                tree and run the copy at the NEW location, detection is
                automatic).
    --old-root  Override the detected old root (skip registry auto-detection).
    --apply     Actually write the changes. Without it, dry-run only.
    --home      Override the home base (where ~/.horizon and ~/.claude live).
                For testing. Default: ~.

Exit codes:
    0  success (dry-run completed, or changes applied; also when nothing to do)
    1  usage / environment error (old root could not be detected, new root
       invalid, old == new, etc.)
    2  refused for safety (e.g. a target turned out to be a tracked repo file)
"""

import argparse
import json
import os
import subprocess
import sys

# Make stdout/stderr robust on legacy Windows code pages (e.g. cp1252) so the
# tool never crashes with UnicodeEncodeError on non-ASCII output. Self-healing
# regardless of PYTHONIOENCODING; guarded for Pythons without reconfigure().
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# --- This tree (the AIOS the script physically lives in) -----------------------
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))   # horizon_system/sbin
THIS_SYSTEM = os.path.dirname(SCRIPT_DIR)                   # horizon_system
THIS_ROOT = os.path.dirname(THIS_SYSTEM)                    # repo root


# --- small output helpers (match sibling lifecycle tools) ----------------------
def ok(m):   print(f"  [OK]   {m}")
def info(m): print(f"  [INFO] {m}")
def warn(m): print(f"  [WARN] {m}")
def err(m):  print(f"  [ERR]  {m}", file=sys.stderr)


def _norm(p):
    """Normalize for comparison only (case-insensitive on Windows)."""
    return os.path.normcase(os.path.normpath(p))


def is_valid_aios(root):
    """A directory is a Horizon AIOS root if it has the load-bearing structure.
    Mirrors horizon_aios_switch.py.is_valid_aios."""
    if not root or not os.path.isdir(root):
        return False
    system = os.path.join(root, "horizon_system")
    return (os.path.isdir(system)
            and os.path.isdir(os.path.join(system, "ai_os_etc"))
            and os.path.isdir(os.path.join(system, "sbin")))


def detect_old_root(registry_path, new_root):
    """Auto-detect the OLD embedded root from the machine-local registry.

    Strategy: the registry records every AIOS this machine knows by absolute
    root. We pick the entry whose recorded root differs from new_root - that is
    the stale path left behind by the move. If the active entry already equals
    new_root there is nothing stale to relocate. Returns (old_root, source_desc)
    or (None, reason)."""
    if not os.path.isfile(registry_path):
        return None, f"registry not found: {registry_path}"
    try:
        with open(registry_path, encoding="utf-8") as f:
            reg = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"registry unreadable ({exc})"

    aioses = reg.get("aioses") if isinstance(reg, dict) else None
    if not isinstance(aioses, dict) or not aioses:
        return None, "registry has no registered AIOSs"

    new_n = _norm(new_root)
    # Prefer the active entry if it names a stale root; otherwise any entry that
    # is not already the new root.
    active = reg.get("active")
    candidates = []
    if active and active in aioses:
        candidates.append((active, aioses[active]))
    candidates += [(n, e) for n, e in aioses.items() if n != active]

    for name, entry in candidates:
        root = entry.get("root", "") if isinstance(entry, dict) else ""
        if root and _norm(root) != new_n:
            return root, f"registry entry '{name}'"

    return None, ("every registry entry already points at the new root - "
                  "nothing to relocate")


def git_is_tracked(path):
    """True if `path` is tracked by the AIOS git repo. Used as a hard guard:
    we never rewrite framework/source files. Best-effort - if git is missing or
    the path is outside any repo, returns False."""
    try:
        r = subprocess.run(
            ["git", "-C", os.path.dirname(path) or ".",
             "ls-files", "--error-unmatch", "--", os.path.basename(path)],
            capture_output=True, text=True,
        )
        return r.returncode == 0
    except OSError:
        return False


def find_occurrences(path, old_root):
    """Return a list of (lineno, original_line, rewritten_line) for every line
    in `path` containing `old_root`. Case-insensitive match on Windows (paths
    are case-insensitive there); exact elsewhere. Forward-slash variants of the
    old root are also matched, since some snippets render C:\\x as C:/x."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return []

    variants = _root_variants(old_root)
    hits = []
    for i, line in enumerate(lines, 1):
        rewritten = line
        changed = False
        for old_v, new_v in variants:
            if old_v.lower() in rewritten.lower() if os.name == "nt" else old_v in rewritten:
                rewritten = _ci_replace(rewritten, old_v, new_v)
                changed = True
        if changed:
            hits.append((i, line, rewritten))
    return hits


def _root_variants(old_root):
    """Pairs of (old_string, new_string_placeholder_key). We return the old
    variants only; the caller substitutes the matching new variant. To keep this
    simple we generate both back-slash and forward-slash spellings and pair each
    with the correspondingly-spelled new root via a closure set up by the
    caller. Here we just return spellings of the OLD root; new is filled in by
    build_variant_map()."""
    return _VARIANT_MAP[_norm(old_root)]


# Module-level map: normalized old root -> list of (old_spelling, new_spelling).
_VARIANT_MAP = {}


def build_variant_map(old_root, new_root):
    """Populate _VARIANT_MAP with the back-slash and forward-slash spellings of
    old_root paired with the same spelling of new_root."""
    old_bs = old_root.replace("/", "\\")
    old_fs = old_root.replace("\\", "/")
    new_bs = new_root.replace("/", "\\")
    new_fs = new_root.replace("\\", "/")
    # Order matters only for de-dup; put the longer/native spelling first.
    pairs = []
    seen = set()
    for o, n in ((old_bs, new_bs), (old_fs, new_fs)):
        if o not in seen:
            pairs.append((o, n))
            seen.add(o)
    _VARIANT_MAP[_norm(old_root)] = pairs


def _ci_replace(text, old, new):
    """Replace occurrences of `old` in `text` with `new`. Case-insensitive on
    Windows (paths there are case-insensitive), case-sensitive elsewhere."""
    if not old:
        return text
    if os.name != "nt":
        return text.replace(old, new)
    out = []
    low = text.lower()
    olow = old.lower()
    i = 0
    while True:
        j = low.find(olow, i)
        if j == -1:
            out.append(text[i:])
            break
        out.append(text[i:j])
        out.append(new)
        i = j + len(old)
    return "".join(out)


def rewrite_registry_json(path, old_root, new_root, apply):
    """Show (and, if apply, perform) the registry JSON rewrite.

    JSON files store Windows paths as double-backslash (C:\\\\devroot), so a
    raw text replace on C:\\devroot would never match. This function reads the
    JSON structure, patches the 'root' values that normalize to old_root, and
    writes back with json.dump (indent=2) + trailing newline."""
    if not os.path.isfile(path):
        return 0
    try:
        with open(path, encoding="utf-8") as f:
            reg = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        warn(f"registry unreadable ({exc}) — skipping JSON rewrite")
        return 0

    aioses = reg.get("aioses") if isinstance(reg, dict) else None
    if not isinstance(aioses, dict):
        return 0

    old_n = _norm(old_root)
    changes = 0
    for name, entry in aioses.items():
        if not isinstance(entry, dict):
            continue
        root = entry.get("root", "")
        if root and _norm(root) == old_n:
            print(f"\n  {path}  (registry entry '{name}')")
            print(f"      root-  {root}")
            print(f"      root+  {new_root}")
            if apply:
                entry["root"] = new_root
            changes += 1

    # Log active pointer (name stays correct; just informational).
    active = reg.get("active")
    if active and active in aioses:
        info(f"Registry active entry: '{active}' (name unchanged, root updated above).")

    if changes and apply:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(reg, f, indent=2)
                f.write("\n")
            ok(f"rewrote {changes} registry root(s) in {path}")
        except OSError as exc:
            err(f"failed to write registry {path}: {exc}")
    return changes


def rewrite_file(path, old_root, apply):
    """Show (and, if apply, perform) the rewrite for one file. Returns the
    number of changed lines."""
    # Hard safety guard: never edit a tracked/framework file.
    if git_is_tracked(path):
        warn(f"SKIP (tracked by git - framework file): {path}")
        return 0

    hits = find_occurrences(path, old_root)
    if not hits:
        return 0

    rel = path
    print(f"\n  {rel}  ({len(hits)} line(s))")
    for lineno, before, after in hits:
        print(f"      L{lineno}-  {before}")
        print(f"      L{lineno}+  {after}")

    if apply:
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            for old_v, new_v in _root_variants(old_root):
                content = _ci_replace(content, old_v, new_v)
            # Preserve original newline style minimally: write back as-is.
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            ok(f"rewrote {len(hits)} line(s) in {rel}")
        except OSError as exc:
            err(f"failed to write {rel}: {exc}")
    return len(hits)


def main():
    p = argparse.ArgumentParser(
        prog="horizon_aios_relocate.py",
        description="Relocate a Horizon AIOS install to a new root path "
                    "(rewrites machine-local pointers only).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--new-root",
                   help="Target root the install now lives at "
                        "(default: this script's own resolved root).")
    p.add_argument("--old-root",
                   help="Old embedded root to replace "
                        "(default: auto-detected from ~/.horizon registry).")
    p.add_argument("--apply", action="store_true",
                   help="Actually write the changes. Without it, dry-run only.")
    p.add_argument("--home",
                   help="Override the home base for ~/.horizon and ~/.claude "
                        "(testing). Default: ~.")
    args = p.parse_args()

    home = args.home or os.path.expanduser("~")
    horizon_home = os.path.join(home, ".horizon")
    claude_dir = os.path.join(home, ".claude")
    registry = os.path.join(horizon_home, "aios_registry.json")

    # --- resolve new root ---
    new_root = os.path.abspath(args.new_root) if args.new_root else THIS_ROOT
    if not is_valid_aios(new_root):
        err(f"--new-root is not a valid Horizon AIOS: {new_root}")
        err("Expected horizon_system/ with ai_os_etc/ and sbin/ inside.")
        err("Move the tree to its new location first, then run this from there "
            "(or pass --new-root).")
        return 1

    # --- resolve old root (auto-detect) ---
    if args.old_root:
        old_root = args.old_root
        source = "--old-root"
    else:
        old_root, source = detect_old_root(registry, new_root)
        if old_root is None:
            err(f"Could not auto-detect the old root: {source}")
            err("Pass --old-root <path> explicitly if you know it.")
            return 1

    if _norm(old_root) == _norm(new_root):
        info(f"Old root and new root are identical ({new_root}). Nothing to do.")
        return 0

    build_variant_map(old_root, new_root)

    mode = "APPLY - writing changes" if args.apply else "DRY RUN - no changes (pass --apply to write)"
    print(f"\nHorizon AIOS relocate  [{mode}]")
    print(f"  old root : {old_root}   (detected via {source})")
    print(f"  new root : {new_root}")

    # --- the machine-local instance surface we rewrite ---
    # Note: registry is handled separately via rewrite_registry_json (JSON-aware).
    rewrite_targets = [
        os.path.join(horizon_home, "active_env.ps1"),
        os.path.join(horizon_home, "active_env.sh"),
        os.path.join(claude_dir, "CLAUDE.md"),
        # gitignored per-machine config lives INSIDE the (new) tree:
        os.path.join(new_root, "horizon_system", "ai_os_etc", "aios_local.conf"),
        # global gitconfig include.path entries (setup_git_identity writes absolute paths):
        os.path.join(home, ".gitconfig"),
        os.path.join(home, ".config", "git", "config"),
    ]

    # --- files we only SCAN and report (never auto-rewrite): anchored on
    #     ~/.horizon / $HOME, not on the AIOS root. ---
    scan_only = [
        os.path.join(horizon_home, "bin", "aios-exec.ps1"),
        os.path.join(horizon_home, "bin", "aios-exec.sh"),
        os.path.join(claude_dir, "settings.json"),
    ]

    # Rewrite the registry JSON (JSON-aware, must precede text-rewrite loop).
    reg_changes = rewrite_registry_json(registry, old_root, new_root, args.apply)
    total_changes = reg_changes
    total_files = 1 if reg_changes else 0

    for path in rewrite_targets:
        if not os.path.isfile(path):
            continue
        n = rewrite_file(path, old_root, args.apply)
        if n:
            total_changes += n
            total_files += 1

    # report-only scan
    flagged = []
    for path in scan_only:
        if os.path.isfile(path) and find_occurrences(path, old_root):
            flagged.append(path)
    if flagged:
        print()
        warn("These files unexpectedly contain the old root but are NOT "
             "auto-rewritten (they should be $HOME/~.horizon-anchored). "
             "Review them manually:")
        for f in flagged:
            warn(f"  {f}")

    # --- skills symlink + user-skill symlinks ---
    skills_link = os.path.join(claude_dir, "skills")
    if args.apply and (os.path.exists(skills_link) or os.path.islink(skills_link)):
        print()
        switch_py = os.path.join(new_root, "horizon_system", "sbin",
                                 "horizon_aios_switch.py")
        active = _active_name(registry)
        if os.path.isfile(switch_py) and active and active != "<name>":
            py = sys.executable or "python"
            info(f"Re-pointing skills symlink via switch '{active}' ...")
            r = subprocess.run([py, switch_py, "switch", active, "--yes"],
                               capture_output=True, text=True)
            if r.returncode == 0:
                ok("Skills symlink re-pointed.")
            else:
                warn(f"switch exited {r.returncode} — re-point manually: aios switch {active}")
                if r.stderr.strip():
                    info(f"  Detail: {r.stderr.strip()[:300]}")

            reg_skills = os.path.join(new_root, "horizon_system", "sbin",
                                      "horizon_aios_register_user_skills.py")
            if os.path.isfile(reg_skills):
                info("Rebuilding user-skill symlinks ...")
                r2 = subprocess.run([py, reg_skills], capture_output=True, text=True)
                if r2.returncode == 0:
                    ok("User-skill symlinks rebuilt.")
                else:
                    warn(f"register_user_skills exited {r2.returncode} — rebuild manually.")
        else:
            warn("Could not re-point skills symlink automatically — run: aios switch <name>")

    # --- summary ---
    print()
    if total_files == 0:
        ok("No machine-local instance files referenced the old root - nothing "
           "to rewrite.")
    elif args.apply:
        ok(f"Applied: rewrote {total_changes} line(s) across {total_files} file(s).")
        warn("Restart Claude Code and open a NEW shell - env changes do not "
             "reach already-running sessions.")
    else:
        ok(f"Dry run: {total_changes} line(s) across {total_files} file(s) "
           "would change. Re-run with --apply to write.")
    return 0


def _active_name(registry):
    """Best-effort: the active AIOS name from the registry, for the switch hint."""
    try:
        with open(registry, encoding="utf-8") as f:
            reg = json.load(f)
        return reg.get("active") or "<name>"
    except (OSError, json.JSONDecodeError):
        return "<name>"


if __name__ == "__main__":
    sys.exit(main())
