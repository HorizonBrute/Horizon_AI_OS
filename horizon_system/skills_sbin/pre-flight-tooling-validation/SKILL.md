---
name: pre-flight-tooling-validation
description: Validate that the AIOS repo ships every tool needed to run its full lifecycle (install, create brain, create a second AIOS, switch, delete) on each major platform, then emit a ready-to-run admin/sudo test prompt per platform. Use when the user wants a pre-flight tooling check before testing a fresh clone on another machine, or types /pre-flight-tooling-validation.
tools: Agent, Bash, Read, Glob, Grep, Write
---

# Skill: /pre-flight-tooling-validation

Coordinate a **fleet of investigation agents — one per major platform** — that each
verify the AIOS, *as it would arrive from a fresh GitHub clone*, contains all the
tooling required to run its full lifecycle. If every capability is covered, emit a
single self-contained prompt **per platform** that a freshly installed Claude Code
(running with Administrator / sudo) can execute to test-run those capabilities on
the target machine.

This is a **read-only validation of the repo's tooling surface** on the dev
machine. It does not install, provision, switch, or delete anything here — the
actual exercising happens on the target machine via the emitted prompt.

## When to invoke

- "run a pre-flight tooling check", "validate the AIOS tooling before I test on
  another machine", "are we ready to dog-food a fresh clone".
- Before shipping a clone to a clean test box (pairs with
  `getting_started/lifecycle_test.md`).

## Platforms

The full design fans out one agent per major platform: **Windows, Linux, macOS**.
**This prototype run targets Windows only** — dispatch only the Windows agent.
The skill is structured so Linux/macOS agents drop in unchanged once those
platforms are promoted past prototype.

## The five capabilities each agent must validate

For its platform, an agent confirms the repo ships working tooling for each of:

| # | Capability | Expected tooling (verify presence + correct interface) |
|---|---|---|
| 1 | **Install an AIOS from a fresh clone** | `horizon_system/sbin/bootstrap.{ps1,sh}` (idempotent, `--yes`); supporting `horizon_aios_harden.py`, `horizon_aios_doctor.py`, `horizon_aios_switch.py init` |
| 2 | **Create a new brain in that AIOS** | `horizon_system/sbin/horizon_aios_create_brain.py` (`--automation`, `--dry-run`); supporting `horizon_aios_brain_credential.py`, `horizon_aios_brain_logon_rights.py`, `horizon_aios_harden.py` |
| 3 | **Create a new AIOS in another directory** | a second clone + `bootstrap.{ps1,sh}` + `horizon_aios_switch.py register <name> <path>` (no dedicated script — the path is clone→bootstrap→register; confirm `register` exists and validates the target root) |
| 4 | **Switch back and forth between AIOSs** | `horizon_system/sbin/horizon_aios_switch.py` with `list`/`current`/`register`/`switch` (+ `switch --dry-run`); the `aios` wrapper in `horizon_system/bin/` |
| 5 | **Delete an AIOS** | `horizon_system/sbin/uninstall.{ps1,sh}` (`--dry-run`, `--yes`, unknown-arg reject) and `aios uninstall`; brain teardown via `horizon_aios_remove_brain.py` (`--yes`) |

"Validate" means: the file **exists**, is non-empty, and exposes the **expected
interface** (subcommand / flag / argparse option) — grep the source for the flag
or `add_argument`, or run `--help` where safe and read-only. It does **not** mean
executing the install/provision/switch/delete here. Anything not positively
verified is a **FAIL** (no false greens).

## Execution protocol

### 1. Resolve the repo root
Use `$HORIZON_SYSTEM` / `$HORIZON_ROOT`. Never hardcode paths.

### 2. Dispatch one investigation agent per in-scope platform
For the prototype, dispatch **one general-purpose subagent for Windows** (use the
Agent tool, `subagent_type: general-purpose`). Subagents start cold — give each
the capability table above, the repo root, its platform, and these instructions:

> For platform `<P>`, verify each of the five capabilities by locating its tooling
> under `$HORIZON_SYSTEM` and confirming the expected interface (flag / subcommand
> / `add_argument`) via Read/Grep, or a read-only `--help`. Return a verdict table:
> capability → PASS/FAIL → positive evidence (`file:line`, matched flag, or
> `--help` line). Do not install, provision, switch, or delete anything. Do not
> commit. If a capability's tooling is missing or lacks its interface, mark FAIL
> with what's absent.

### 3. Gate on the results
- **If ANY capability on ANY in-scope platform is FAIL** → **stop**. Do not write
  any test prompt. Notify the user: which platform, which capability, and the
  missing/incomplete tool. That is the skill's terminal output.
- **If ALL capabilities PASS on all in-scope platforms** → proceed to step 4.

### 4. Emit one admin/sudo test-run prompt per platform
For each platform that fully passed, write a **single self-contained prompt** that
a **freshly installed Claude Code with Administrator/sudo** on the target machine
can run end-to-end. **Write it to the canonical path**
`$HORIZON_DOCS/development_tools/<platform>_install_switch_uninstall_test_prompt.md`
(e.g. `windows_install_switch_uninstall_test_prompt.md`) and register it in
`documentation/index.md` in the same commit (CC-G4). These prompts are durable,
shared lifecycle-test artifacts — useful to the owner and any future contributors —
not throwaway scratch. Each prompt must:
- State it requires elevation and a clean machine; never run on the dev box.
- Walk the full lifecycle in order: clone → bootstrap → **create a brain** →
  **register + create a second AIOS in another dir** → **switch back and forth** →
  back up user data to the operator's own remote → **uninstall / delete** (brain
  then AIOS) → verify clean.
- Use the platform's real commands (PowerShell for Windows; `sudo bash` for
  Unix), `--dry-run` before each destructive step, and reference
  `system/uninstall.md` for the authoritative verification checklist.
- Tell the agent to report PASS/FAIL per lifecycle step and stop on first failure.

### 5. Report
Summarize per platform: the verdict table, the gate decision, and (on success) the
emitted prompt(s). Keep the dev-machine side read-only throughout.

## Notes for the executing agent

- **Fail closed.** Missing tooling or an unverifiable interface is FAIL, not
  "probably fine". The whole point is to catch a gap before it wastes a
  test-machine run.
- Capability 3 ("new AIOS in another directory") has **no dedicated script** by
  design — it is clone → bootstrap → `aios register`. Validate that composite path,
  don't fail it for lacking a one-shot tool.
- This skill is read-only on the dev machine. The emitted prompt is the only thing
  that mutates state, and only on the target machine.
- Keep the fleet structure even in the Windows-only prototype, so promoting
  Linux/macOS is just enabling their agents.
- Cross-reference `getting_started/lifecycle_test.md` (operator runbook) and
  `system/uninstall.md` (authoritative teardown + verification) in emitted prompts.
