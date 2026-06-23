#!/usr/bin/env python3
"""Resolve the Agent Teams in effect for a given path.

Given a path (default: cwd), walk the scope cascade up to the Horizon AIOS root
and report every Agent Team definition source and the teams it defines:

  - the shipped, tracked `$HORIZON_ROOT/agent_teams.md`, plus
  - every machine-local `local.agent_teams.md` override from the path up to the
    OS root (and the root `.claude/` scope), least- to most-specific.

Only these definition files are read — never a file merely named `agent_teams.md`
elsewhere (e.g. the user-facing doc under `documentation/`). Most-specific scope
wins on a same-named team; new names are unioned in.

Role flags (inline `(`#group`, if needed)` tokens and `**Loop:**`-style annotations)
are parsed generically; their vocabulary is the catalog in `$HORIZON_ETC/
agent_team_flags.md` + `local.agent_team_flags.md`, which this tool reads to label
flags, list them (`--flags`), and warn on flags not in the registry.

This is the deterministic discovery the `/agent-teams` skill calls so the acting
model does not hand-glob. Stdlib only.

Usage:
    resolve_agent_teams.py [path] [--root DIR] [--json]
    resolve_agent_teams.py --flags [--root DIR] [--json]

Exit codes: 0 ok; 2 could not resolve the AIOS root.
"""

import argparse
import json
import os
import re
import sys

TEAM_RE = re.compile(r"^###\s+(.+?)\s*$")
# role label, model group, then everything else inside the parenthetical (flags).
ROLE_RE = re.compile(r"^\s*\d+\.\s+(.+?)\s*\(`(#?[A-Za-z0-9_-]+)`([^)]*)\)")
# a `**Name:** text` annotation line under a role.
ANNOT_RE = re.compile(r"^\s*(?:>\s*)?\*\*([A-Za-z][A-Za-z0-9 _-]*):\*\*\s*(.*)$")


def find_root(start, override):
    """Resolve $HORIZON_ROOT: explicit override, env, else walk up for the AIOS
    root marker (horizon_system/ai_os_etc + a shipped agent_teams.md)."""
    if override:
        return os.path.abspath(override)
    env = os.environ.get("HORIZON_ROOT")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    cur = os.path.abspath(start)
    fallback = None
    while True:
        if os.path.isfile(os.path.join(cur, "agent_teams.md")):
            fallback = fallback or cur
            if os.path.isdir(os.path.join(cur, "horizon_system", "ai_os_etc")):
                return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return fallback


def load_flags(root):
    """Read the shipped + local flag registries; return an ordered dict
    {name_lower: {name, form, means}} parsed from each `| flag | form | means |`
    table row (header/separator rows skipped)."""
    flags = {}
    etc = os.path.join(root, "horizon_system", "ai_os_etc")
    for fn in ("agent_team_flags.md", "local.agent_team_flags.md"):
        try:
            with open(os.path.join(etc, fn), encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        for line in lines:
            if not line.lstrip().startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            name = cells[0].strip().strip("`").strip()
            if not name or name.lower() == "flag" or set(name) <= set("-: "):
                continue
            flags[name.lower()] = {
                "name": name,
                "form": cells[1].strip() if len(cells) > 1 else "",
                "means": cells[2].strip() if len(cells) > 2 else "",
            }
    return flags


def parse_teams(path):
    """Return a list of team dicts for a file, or [] if absent/stub. Each team:
    {name, summary, roles:[{role, group, flags, annotations}], loop, loop_max,
    loop_target}."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    # Slice the file into team blocks: a `### ` heading until the next `###`/`##`.
    blocks = []
    cur = None
    for line in lines:
        m = TEAM_RE.match(line)
        if m:
            cur = {"name": m.group(1).strip(), "lines": []}
            blocks.append(cur)
            continue
        if cur is None:
            continue
        if line.startswith("## "):  # left the Teams section
            cur = None
            continue
        cur["lines"].append(line)

    teams = []
    for b in blocks:
        blk = b["lines"]
        # Summary = descriptive lines after the heading, up to the first blank line
        # or the first numbered role (joined; handles wrapped sentences).
        i = 0
        while i < len(blk) and not blk[i].strip():
            i += 1
        summ = []
        while i < len(blk) and blk[i].strip() and not ROLE_RE.match(blk[i]):
            summ.append(blk[i].strip())
            i += 1

        roles = []
        cur_role = None
        for line in blk:
            rm = ROLE_RE.match(line)
            if rm:
                flags = [t.strip() for t in rm.group(3).lstrip(",").split(",")
                         if t.strip()]
                cur_role = {"role": rm.group(1).strip(), "group": rm.group(2),
                            "flags": flags, "annotations": []}
                roles.append(cur_role)
                continue
            am = ANNOT_RE.match(line)
            if am and cur_role is not None:
                cur_role["annotations"].append({"name": am.group(1).strip(),
                                                "text": am.group(2).strip()})
                continue
            # continuation of the current annotation (indented wrap, no new marker)
            if (cur_role is not None and cur_role["annotations"] and line.strip()
                    and not ROLE_RE.match(line)):
                cur_role["annotations"][-1]["text"] += " " + line.strip()

        # Loop: a role annotation named 'loop' -> parse cap + return target.
        loop = loop_max = loop_target = None
        loop = False
        for r in roles:
            for a in r["annotations"]:
                if a["name"].lower() != "loop":
                    continue
                loop = True
                r["loop"] = True
                cap = re.search(r"or\s+(\d+)\s+iteration", a["text"], re.IGNORECASE)
                if cap:
                    loop_max = int(cap.group(1))
                tgt = re.search(r'(?:return to|from)\s+["“]([^"”]+)["”]',
                                a["text"], re.IGNORECASE)
                if tgt:
                    loop_target = tgt.group(1).strip()
                else:
                    stp = re.search(r"from step\s+(\d+)", a["text"], re.IGNORECASE)
                    if stp:
                        loop_target = f"step {stp.group(1)}"

        teams.append({"name": b["name"], "summary": " ".join(summ), "roles": roles,
                      "loop": loop, "loop_max": loop_max, "loop_target": loop_target})
    return teams


def collect_sources(path, root):
    """Ordered (least- to most-specific) list of (label, abspath) definition
    sources: shipped root agent_teams.md, then local.agent_teams.md overrides
    from the root (incl. root/.claude) down to the given path."""
    sources = [("shipped", os.path.join(root, "agent_teams.md"))]
    seen = set()

    def add(p):
        ap = os.path.abspath(p)
        key = os.path.normcase(os.path.realpath(ap))
        if key in seen or not os.path.isfile(ap):
            return
        seen.add(key)
        sources.append(("override", ap))

    add(os.path.join(root, "local.agent_teams.md"))
    add(os.path.join(root, ".claude", "local.agent_teams.md"))

    # Walk from root down to the target path so overrides list least->most specific.
    target = os.path.abspath(path)
    if os.path.isfile(target):
        target = os.path.dirname(target)
    chain = []
    cur = target
    while True:
        chain.append(cur)
        if os.path.normcase(cur) == os.path.normcase(root) or os.path.dirname(cur) == cur:
            break
        cur = os.path.dirname(cur)
    for d in reversed(chain):
        add(os.path.join(d, "local.agent_teams.md"))
    return sources


def build(path, root):
    sources = []
    resolved = {}        # name -> {source, label} (most-specific wins)
    teams_by_name = {}   # name -> winning team dict
    for label, ap in collect_sources(path, root):
        teams = parse_teams(ap)
        rel = os.path.relpath(ap, root)
        sources.append({"label": label, "path": ap, "rel": rel, "teams": teams})
        for t in teams:
            resolved[t["name"]] = {"source": rel, "label": label}
            teams_by_name[t["name"]] = t
    return sources, resolved, teams_by_name


def used_flags(teams_by_name):
    """All flag tokens + annotation names used across the resolved teams (lower)."""
    used = set()
    for t in teams_by_name.values():
        for r in t["roles"]:
            used.update(f.lower() for f in r.get("flags", []))
            used.update(a["name"].lower() for a in r.get("annotations", []))
    return used


def _prefs(team):
    """Compact 'Role `#group` (flags) -> ...' chain, with a loop marker."""
    parts = []
    for r in team["roles"]:
        s = f"{r['role']} `{r['group']}`"
        if r.get("flags"):
            s += " (" + ", ".join(r["flags"]) + ")"
        parts.append(s)
    chain = " -> ".join(parts) or "(roles not parsed)"
    if team.get("loop"):
        cap = f" <={team['loop_max']}" if team.get("loop_max") else ""
        tgt = f" -> {team['loop_target']}" if team.get("loop_target") else ""
        chain += f"  [loop{cap}{tgt}]"
    return chain


def human(path, root, sources, resolved, teams_by_name):
    out = []
    out.append(f"Agent teams in effect for: {os.path.abspath(path)}")
    out.append(f"OS root: {root}")
    out.append("")
    out.append("Sources (least -> most specific):")
    for s in sources:
        names = ", ".join(t["name"] for t in s["teams"]) or "(no custom teams)"
        out.append(f"  [{s['label']:<8}] {s['rel']}  ->  {names}")
    out.append("")
    if resolved:
        out.append("Resolved teams (most-specific wins):")
        out.append("")
        out.append("| Team | What it does | Model preferences (role -> group) | Source |")
        out.append("|------|--------------|-----------------------------------|--------|")

        def cell(s):
            return s.replace("|", "\\|")
        for name in resolved:
            t = teams_by_name[name]
            summary = t.get("summary") or ""
            src = "shipped" if resolved[name]["label"] == "shipped" else resolved[name]["source"]
            out.append(f"| {cell(name)} | {cell(summary)} | {cell(_prefs(t))} | {src} |")
    else:
        out.append("Resolved teams: (none)")
    return "\n".join(out)


def print_flags(registry, as_json):
    if as_json:
        print(json.dumps(list(registry.values()), indent=2))
        return
    print("Recognized agent-team role flags (agent_team_flags.md + local override):")
    print("")
    print("| Flag | Form | Means |")
    print("|------|------|-------|")
    for v in registry.values():
        print(f"| {v['name']} | {v['form']} | {v['means']} |")


def main():
    ap = argparse.ArgumentParser(description="Resolve Agent Teams in effect for a path.")
    ap.add_argument("path", nargs="?", default=os.getcwd(),
                    help="Path to resolve the scope cascade for (default: cwd).")
    ap.add_argument("--root", help="Override $HORIZON_ROOT instead of auto-resolving.")
    ap.add_argument("--json", action="store_true", help="Emit structured JSON.")
    ap.add_argument("--flags", action="store_true",
                    help="List the recognized role flags from the registry and exit.")
    args = ap.parse_args()

    root = find_root(args.path, args.root)
    if not root:
        sys.stderr.write("error: could not resolve the Horizon AIOS root "
                         "(no agent_teams.md found up-tree). Pass --root.\n")
        return 2

    registry = load_flags(root)
    if args.flags:
        print_flags(registry, args.json)
        return 0

    sources, resolved, teams_by_name = build(args.path, root)
    unknown = sorted(u for u in used_flags(teams_by_name) if u not in registry)
    if args.json:
        print(json.dumps({
            "path": os.path.abspath(args.path),
            "root": root,
            "sources": [{"label": s["label"], "path": s["path"], "rel": s["rel"],
                         "teams": s["teams"]} for s in sources],
            "resolved": [{"name": n, **resolved[n], "team": teams_by_name[n]}
                         for n in resolved],
            "flags_registry": list(registry.values()),
            "unknown_flags": unknown,
        }, indent=2))
    else:
        print(human(args.path, root, sources, resolved, teams_by_name))
        if unknown:
            print("")
            print("WARNING: flags used in a team but not in the registry: "
                  + ", ".join(unknown))
            print("Add them to local.agent_team_flags.md (or fix the typo).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
