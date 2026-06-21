# Horizon AIOS — Tested Configurations

This document tracks harness, model, OS, and deployment combinations that have been verified to work with Horizon AIOS. "Tested" means: bootstrap completed, skills loaded, audit hooks fired, brain isolation verified end-to-end.

Configurations not listed here may work but have not been validated. Contributions welcome — if you test a new combination, add a row and link the relevant how-to or deployment notes.

---

## Compatibility Matrix

| Harness | Harness Version | Model(s) Tested | OS / Platform | Deployment Mode | Status | Notes / Known Gaps | How-To |
|---|---|---|---|---|---|---|---|
| Claude Code (desktop app) | ≥1.0 | Claude Sonnet 4.6, Opus 4.8 | Windows 11 | Desktop | **Verified** | Skills via directory junction (`mklink /J`); DCO commit-msg hook; statusline; sounds; brain isolation via NTFS ACLs; memory layout user-defined. Full bootstrap tested. Primary reference implementation. | [deployment/desktop.md](deployment/desktop.md) · [ReadMeToSetupYourSystem.md](getting_started/ReadMeToSetupYourSystem.md) |
| Claude Code (CLI) | ≥1.0 | — | Linux (native) | Desktop / Server | Partial | bootstrap.sh runs; symlink skills redirect implemented. Brain OS user isolation and sbin Deny ACLs not yet end-to-end tested on Linux. | [deployment/desktop.md](deployment/desktop.md) |
| Claude Code (CLI) | ≥1.0 | — | Linux (container) | Docker | Template only | Dockerfile and bootstrap_docker.sh written; not yet run against a full brain provisioning cycle. See gap notes below. | [deployment/docker.md](deployment/docker.md) |
| Claude Code (desktop app) | ≥1.0 | — | macOS (native) | Desktop | Untested | bootstrap.sh is macOS-compatible (POSIX). ACL steps require macOS equivalents (chmod/chown, dscl for user accounts). No one has validated end-to-end. | — |

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
- `create_brain.py` has no macOS-specific branch; `dscl` (Directory Services) is the macOS equivalent of `useradd`.

---

## Adding a Tested Configuration

When you validate a new combination:

1. Run through all six verification criteria above.
2. Add a row to the matrix with status **Verified** or **Partial**.
3. Link a how-to doc if one exists; create one in `$HORIZON_DOCS/deployment/` if not.
4. Note any known gaps or workarounds in the Notes column.
5. Add an entry to `architecture_decisions.md` if the configuration required architectural changes.
