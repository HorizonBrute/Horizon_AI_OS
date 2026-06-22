# Horizon AIOS — Tested Configurations

This document tracks harness, OS, and deployment combinations that have been verified to work with Horizon AIOS. "Tested" means: bootstrap completed, skills loaded, audit hooks fired, brain isolation verified end-to-end. Model selection is the brain author's choice and is not tracked here — AIOS is model-agnostic.

Configurations not listed here may work but have not been validated. Contributions welcome — if you test a new combination, add a row and link the relevant how-to or deployment notes.

---

## Compatibility Matrix

| Harness | Harness Version | OS / Platform | Deployment Mode | Status | Notes / Known Gaps | How-To |
|---|---|---|---|---|---|---|
| Claude Code (desktop app) | ≥1.0 | Windows 11 | Desktop | **Verified (harness + ACL enforcement); brain-account isolation pending** | Verified: skills via directory junction (`mklink /J`), DCO commit-msg hook, statusline, sounds, memory layout user-defined. **ACL enforcement verified (2026-06-22):** `harden_aios.py` run elevated on Windows 11; `doctor.py` passes the `sbin`/`skills_sbin`/`logs` ACL checks; `Get-Acl` confirms an explicit `brains` Deny on each privileged dir with SYSTEM/Administrators and inherited/infra ACLs preserved. Criterion #6 (audit log captures an event) confirmed via `monitor_aios.py`. **Still pending:** criterion #5 end-to-end — no brain has been provisioned via `create_brain.py` yet, so a *real* brain OS account being denied `sbin` is verified at the ACL level but not yet by a live brain account. Primary reference implementation. | [deployment/desktop.md](deployment/desktop.md) · [ReadMeToSetupYourSystem.md](getting_started/ReadMeToSetupYourSystem.md) |
| Claude Code (CLI) | ≥1.0 | Linux (native) | Desktop / Server | Partial | bootstrap.sh runs; symlink skills redirect implemented. Brain OS user isolation and sbin Deny ACLs not yet end-to-end tested on Linux. | [deployment/desktop.md](deployment/desktop.md) |
| Claude Code (CLI) | ≥1.0 | Linux (container) | Docker | Template only | Dockerfile and bootstrap_docker.sh written; not yet run against a full brain provisioning cycle. See gap notes below. | [deployment/docker.md](deployment/docker.md) |
| Claude Code (desktop app) | ≥1.0 | macOS (native) | Desktop | Untested | bootstrap.sh is macOS-compatible (POSIX). ACL steps require macOS equivalents (chmod/chown, dscl for user accounts). No one has validated end-to-end. | — |
| Ollama | any | Linux / macOS / Windows | Desktop / Server | Minimal stub | No hook system, no sounds integration, no skills equivalent. Only integration: paste `agents.md` content into brain's Modelfile `SYSTEM` block. Brain OS isolation still applies. See Known Gaps by Harness below. | `$HORIZON_SYSTEM/harness_configs/ollama/Modelfile.template` |

---

## Verification Criteria

A configuration is **Verified** when all of the following have been exercised:

1. `bootstrap.sh` (or `bootstrap.ps1`) completes with zero failures.
2. `doctor.py` reports all checks passed.
3. A skill (`/handoff` or similar) executes in a live session.
4. An event hook fires (task complete sound plays).
5. At least one brain is provisioned via `create_brain.py` and the brain's OS account can read `$HORIZON_BIN` but cannot read `$HORIZON_SYSTEM/sbin`.
6. The audit log captures at least one monitored file event.

**Partial** means steps 1–3 are known to work but steps 4–6 have gaps or have not been run.

**Template only** means the deployment artifacts exist but have not been executed in a real environment.

---

## Known Gaps by Platform

### Linux native (bare metal)
- `create_brain.py` generates `useradd` / `chmod` commands — logic exists but has not been run against a real Linux machine.
- Explicit Deny ACLs use `chmod 700` on `sbin/` — correct POSIX approach, not verified.

### Docker (Linux container)
- Brain isolation in Docker maps to container isolation, not OS user accounts inside the container. `create_brain.py` is not yet adapted to launch sub-containers.
- `bootstrap_docker.sh` runs the standard bootstrap in Docker mode; sync schedule is skipped.
- `~/.claude/skills/` symlink setup tested in bootstrap logic only, not in a running container.
- See [deployment/docker.md](deployment/docker.md) for deployment guide and known gaps.

### macOS
- No one has run bootstrap on macOS. POSIX paths should work; `launchd` plist would be needed for sync schedule instead of cron/systemd.
- `create_brain.py` has a macOS-specific branch (`_macos_create_user` using `dscl` / `dseditgroup` / `createhomedir`, the macOS equivalents of `useradd`), but it has not been validated end-to-end on a real macOS machine.

---

## Known Gaps by Harness

### Ollama
Ollama has no event hook system. The AIOS hook taxonomy (sounds on task complete, permission request, failure) does not apply — Ollama provides no mechanism to fire external commands on model events.

What works: OS-level brain isolation (separate user accounts, NTFS ACLs / POSIX permissions), brain directory scoping, OS-native credential containment via `brain_credential.py`, audit logging via `monitor_aios.py`. The AIOS OS layer is fully in effect; only the harness-level integration (hooks, skills) is absent.

What does not work: sounds, statusline, `/handoff` skill, any skill that depends on a Claude Code session context.

To use Ollama with AIOS: provision a brain account normally via `create_brain.py`, then add the AIOS agent instructions to the Modelfile SYSTEM block manually using `$HORIZON_SYSTEM/harness_configs/ollama/Modelfile.template` as a starting point.

---

## Adding a Tested Configuration

When you validate a new combination:

1. Run through all six verification criteria above.
2. Add a row to the matrix with status **Verified** or **Partial**.
3. Link a how-to doc if one exists; create one in `$HORIZON_DOCS/deployment/` if not.
4. Note any known gaps or workarounds in the Notes column.
5. Add an entry to `architecture_decisions.md` if the configuration required architectural changes.
