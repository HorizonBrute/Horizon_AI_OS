# Terseness Contract Index — Horizon AIOS

Files in this index are loaded into every session's context unconditionally. Every
byte costs tokens on every session for every user and every brain. **Being verbose
here is a tax on every interaction the AIOS will ever have.** The Terseness
Contract is the commitment to keep these files as small as their function allows.

Checked by the `/terseness-check` skill and by CC-T checks in
`consistency_checks.md`. Update this index whenever a file is added to or removed
from the always-loaded chain (an `@`-import in any of these files, or a new
CLAUDE.md layer inserted into the harness loading path).

---

## Terseness Criteria

A file in this index PASSES the terseness check if, and only if:

1. **Every line earns its keep.** Removing it would break the file's function or
   leave a required instruction unspecified. Pure explanation is a FAIL.
2. **Instructions are imperative, not discursive.** Tell the model what to do.
   Rationale belongs in `dev_values.md` or `philosophy.md`, not here.
3. **No rationale that belongs elsewhere.** If the "why" is in a higher-authority
   doc, cut it. A pointer to that doc is fine; the prose is not.
4. **No inline examples when a pointer suffices.** "See `$HORIZON_DOCS/X.md`" is
   cheaper than pasting the example inline.
5. **No redundancy with sibling always-loaded files.** If another file in this
   index already says it, one copy is the defect.
6. **No commented-out content.** Dead code and `# TODO` prose still cost tokens.
7. **@-imports only for always-needed files.** An @-import of a large reference doc
   "for convenience" is a FAIL. Use a prose pointer instead.

---

## Index — Tracked (contract enforced)

These files are tracked in the repo and subject to the strict terseness contract.
The `/terseness-check` skill evaluates each one on every pass.

| File | Loaded by | Role | Special constraints |
|---|---|---|---|
| `CLAUDE.md` | Harness — auto at devroot | Thin @-import shim | One logical block: `@./agents.md` |
| `.claude/CLAUDE.md` | Harness — auto, .claude scope | Thin @-import shim | One logical block: `@./agents.md` |
| `.claude/agents.md` | @-import from `.claude/CLAUDE.md` | Scope @-router | Only @-imports + gitignored override slots; no prose |
| `agents.md` | @-import from `.claude/agents.md` and `CLAUDE.md` | Cross-harness instruction root | Every line taxes every session; any prose must be strictly operative |
| `horizon_system/ai_os_etc/horizon_aios_agents.md` | @-import from `agents.md` | OS-layer agent config | Imperative directives only; no tutorials; no rationale beyond a one-phrase label |
| `horizon_system/ai_os_etc/horizon_aios_model_prefs.md` | @-import from `agents.md` | Model preference spec | Structural headings + mechanism description; examples in the extend template, not here |
| `agent_teams.md` | @-import from `agents.md` | Agent team definitions | Team blocks + loop/flag grammar only; no narrative onboarding prose |
| `horizon_system/ai_os_etc/agent_team_flags.md` | @-import from `agents.md` | Role-flag catalog | Table only + one-line header; no prose examples |

---

## Index — Gitignored / User-controlled (best effort)

These files are in the always-loaded chain but are owned by the user or brain, not
the repo. The terseness contract is advisory here: the user bears the cost of
their own verbosity. The `/terseness-check` skill reports on them but marks
findings `ADVISORY` (not `FAIL`) and does not apply fixes without prompting.

| File | Loaded by | Role |
|---|---|---|
| `horizon_system/ai_os_etc/horizon_aios_model_prefs.local.md` | @-import from `agents.md` | User model-pref overrides |
| `local.agent_teams.md` | @-import from `agents.md` | User team overrides |
| `horizon_system/ai_os_etc/local.agent_team_flags.md` | @-import from `agents.md` | User flag extensions |
| `local.agents.md` | @-import from `agents.md` | User session overrides |
| `.claude/local.agent_teams.md` | @-import from `.claude/agents.md` | .claude scope team overrides |
| `.claude/local.agents.md` | @-import from `.claude/agents.md` | .claude scope overrides |
| `brains/<name>/.claude/CLAUDE.md` | Harness — auto, brain sessions | Brain identity + scope | Brain identity, persona, skill pointers; no large doc blocks |

---

## What is NOT in this index

Files loaded **on demand** (read mid-session by the model, not at session start) are
not subject to this contract. Being thorough is a virtue for on-demand docs;
being terse is a virtue for this index's members. Do not add an on-demand doc
here unless it becomes an @-import.

The `~/.claude/CLAUDE.md` user-global file is outside the repo and user-owned;
apply the same advisory standard as the gitignored files above.
