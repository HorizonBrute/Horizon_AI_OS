# Horizon AIOS — Development Pipeline

Placeholder backlog for tracking known work items, gaps, and research threads before
formal issue management (GitHub Issues, Linear, etc.) is integrated. When that
integration happens, migrate items here into the tracker and replace this file with
a pointer.

Items are grouped by status, not priority — priority is implicit from the group.

---

## In Progress / Recently Landed (this branch: `foundational_misc`)

- **AIOS switcher** — complete. `aios switch <name>` rewrites all machine pointers,
  updates system PATH on switch, `aios` shortcut in `bin/`. See
  `documentation/system/aios_switching.md`.
- **AIOS uninstall** — `sbin/uninstall.ps1` / `sbin/uninstall.sh` landed. Section-by-section
  mirror of bootstrap; requires elevation; covers ACLs, git hooks, PATH, registry.
  Invokable via the `aios uninstall [--dry-run] [--yes]` subcommand, which
  delegates to the platform script. Both scripts support a no-elevation
  `--dry-run` preview and reject unknown arguments.
- **Future harness scope note** — philosophy.md addition in progress. Acknowledges
  Claude-only current scope; names Ollama, Codex, LM Studio as future exploration targets.

---

## Needs Merge

- `foundational_misc` → `master` — contains: skills index, dependencies/footprint doc,
  Windows `<brain-name>_group` fix, system PATH on switch, `aios` shortcut, uninstall
  script, future harness note, and several other items from this session.

---

## Owner-Handled (not tracked here)

- **ACL verification (C-1)** — run `bootstrap.ps1` as Administrator on the Windows
  reference machine with at least one provisioned brain, then `doctor.py` to confirm
  Deny ACEs are applied and non-inherited. This is a verification step, not a code
  change.
- **QC Round 6** — post-QC5 consistency pass was interrupted. Owner will run this after
  the current branch stabilises. Scope: validate monitor brain-dir changes, log identity
  prefix, and any new surface from this session.

---

## Known Gaps — Code

- **Skills for core sbin utilities** — landed. Wrappers now exist:
  `/doctor` and `/monitor` as user-callable (`skills_bin/`); `/harden`,
  `/create-brain`, `/remove-brain` as admin-only (`skills_sbin/`). Uninstall is
  **intentionally not** exposed as a skill — it is an owner/system-level
  operation, invoked directly (`aios uninstall` / `uninstall.ps1`), not something
  an AI or an uninformed user should run via a slash command.

- **`remove_brain.py` uninstall integration** — verify that `remove_brain.py` correctly
  deletes `<brain-name>_group` (not `<brain-name>`) on Windows following the group naming
  fix landed this session.

- **`maintain_logs.py` scheduler** — `setup_sync_schedule.py` handles sync scheduling;
  no equivalent for `maintain_logs.py`. A scheduled-task / cron setup step for log
  maintenance is undocumented. Consider a `setup_log_maintenance.py` or fold into
  `setup_sync_schedule.py`.

- **Brain automation — Linux linger path unverified** — the `scheduled` automation
  tier (`create_brain.py --automation scheduled`) applies `loginctl enable-linger`
  on Linux, and `remove_brain.py` runs `loginctl disable-linger` on teardown. Both
  Windows tiers (`scheduled`/`daemon`, LSA logon rights) are verified end-to-end, but
  the Linux linger path has only been code-reviewed, not run on a live Linux host.
  To close: on a real Linux machine, `create_brain.py <name> --automation scheduled`
  then `loginctl show-user <name> --property=Linger` must report `Linger=yes`;
  `remove_brain.py <name> --yes` then re-check must report `Linger=no` (or the user
  gone). Until then the Linux row in `tested_configurations.md` stays **Partial**.
  See `deployment/brain_automation.md`.

- **macOS — effectively undeveloped/untested** — macOS support is the weakest of
  the three platforms: it exists only as POSIX-compatible code paths that have
  never been run on a real Mac. Specifics: `bootstrap.sh` is POSIX but unvalidated
  on macOS; `create_brain.py`'s macOS branch (`dscl` / `dseditgroup` /
  `createhomedir`) and `remove_brain.py`'s `dscl -delete` are unrun; the ACL model
  needs macOS-native equivalents (no NTFS ACLs); and brain automation has **no**
  applied path on macOS — `brain_logon_rights.py` is Windows-only and there is no
  `launchd` equivalent of the Linux linger step, so both tiers are guidance only
  (LaunchDaemon/LaunchAgent). Closing this needs a dedicated pass on real Apple
  hardware: validate provisioning/removal, define the ACL approach, and implement
  + verify the `launchd` automation path. The macOS row in
  `tested_configurations.md` stays **Untested** until then.

---

## Known Gaps — Documentation

- **Sound system** — `sounds/` directory, `sounds.map`, `resolve_sound.py`, and platform
  audio playback are undocumented. No entry in `utilities.md`; no authoring guide for
  adding new sounds or cues.

- **Sync system** — `sync_aios.py` and `setup_sync_schedule.py` are listed in
  `utilities.md` but the sync workflow (what gets synced, upstream vs. downstream,
  conflict handling) has no dedicated doc. `sync_setup.md` exists but may be stale.

- **Brain authoring guide** — no doc on what goes in a brain's `CLAUDE.md`, how to scope
  its tools/permissions, or how to design a brain persona. The template has defaults but
  no narrative guide.

- **`tested_configurations.md`** — exists but content may be stale relative to current
  bootstrap and ACL changes. Should be validated after ACL verification (C-1) is done.

---

## Research / Future Work

- **Ollama harness support** — local model runtime. Open questions: harness config
  location, hook model, context-loading equivalent. See `documentation/philosophy.md`
  for the scope note.

- **Codex / OpenAI CLI harness support** — Open questions: same as Ollama plus cloud
  vs. local auth model.

- **LM Studio harness support** — local GUI with OpenAI-compatible API. Open questions:
  headless / CLI mode availability, hook equivalents.

- **GitHub / project management integration** — when this repo moves to formal issue
  tracking, migrate items from this file into the tracker. Replace this file with a
  pointer to the project board.

- **Brain marketplace / registry** — a mechanism for discovering, installing, and
  versioning shared brain configurations. Currently `file_structure_invariants.md §7`
  notes that marketplace plugins coexist with AIOS skills; no brain equivalent exists.

- **Multi-operator brain sharing** — `server.md` documents the multi-operator pattern
  (each human operator gets their own OS account); no mechanism for two operators to
  share access to a single brain. May not be desirable by design, but worth an explicit
  decision.

---

## Completed This Session (reference)

For full detail see the session handoff. Short list:

- Worktree cleanup (9 stale branches removed)
- `context_cost.py` + `/context-cost` skill
- Context loading documentation (`documentation/context_loading.md`)
- @-import clarification (`documentation/authoring/claude_md_authoring.md`)
- Utilities index (`documentation/utilities.md`)
- Skills index with onboarding/offboarding reference (`documentation/skills.md`)
- Dependencies and system footprint reference (`documentation/getting_started/dependencies_and_footprint.md`)
- Windows per-brain group as `<brain-name>_group` (code + docs)
- Bootstrap system PATH (Machine-scope Windows, `/etc/profile.d/` Linux/macOS)
- AIOS switcher system PATH update on switch
- `aios` / `aios.ps1` shortcut wrappers in `bin/`
