---
type: Reference
title: "Horizon AIOS — Options Package Readiness Standard"
description: The normative, checkable conformance standard a repo must meet to deploy as an AIOS Options Package. Every rule has a PKG-* ID, a MUST/SHOULD level, and a verification method; the bin/options_package_readiness.py checker is the executable form of this standard.
tags: [options-packages, conformance, readiness, standard, checklist, validation]
timestamp: 2026-07-20
status: draft
source_of_truth: doc
category: cross-cutting
---

# Horizon AIOS — Options Package Readiness Standard

**Point an agent or a human at this document and say: "make your code align with this."** When a repo
satisfies the MUST rules below, it can be deployed as a Horizon AIOS Options Package. This is the
normative, testable companion to the explanation in [DOC-0054 `aios_options_packages.md`](./aios_options_packages.md)
(read that first for *why* the contract exists). Here we enumerate *what is checked*.

Every rule has a stable **`PKG-*` ID**, a **level** (MUST = blocks deployment; SHOULD = expected, warns),
and a **verification** method:

- **static** — provable by reading the code/tree; the checker verifies it.
- **runtime** — only provable by installing; the checker does **not** verify it (see "Scope" below).
- **human** — requires judgment; the checker flags it for a reviewer.

## Scope — the checker is static only

The bundled checker (`$HORIZON_BIN/options_package_readiness.py`) performs **static analysis only. It
never executes the target installer.** This is deliberate: an installer registers itself into the AIOS
sync update pass and may create scheduled tasks / cron jobs — none of which are safe to trigger from a
readiness probe. A clean checker result therefore means the package is **structurally ready to test**,
not that it works. Proving it works is the developer's job: run a real `install` in a sandbox AIOS,
then `status`, `update`, and `uninstall`, and confirm each does what it should.

The checker uses the LAPP reference package
(`deployed_packages/horizon_agentic_project_planning/`) as its golden example — LAPP scores a clean
READY.

## Using the checker

```
# on-disk repo
python "$HORIZON_BIN/options_package_readiness.py" /path/to/repo

# a git URL (shallow-cloned to a temp dir, then removed)
python "$HORIZON_BIN/options_package_readiness.py" https://github.com/owner/repo

# machine-readable, for an agent
python "$HORIZON_BIN/options_package_readiness.py" /path/to/repo --json

# treat warnings as blocking too
python "$HORIZON_BIN/options_package_readiness.py" /path/to/repo --strict
```

Verdict + exit code: **READY** / **READY WITH WARNINGS** (exit 0) / **NOT READY** (exit 1; any MUST
failed). Or invoke `/horizon-options-package-readiness`.

---

## The rules

### A — Anatomy

| ID | Level | Verify | Rule |
|----|-------|--------|------|
| **PKG-A1** | MUST | static | An installer exists at `aios/install/horizon_<name>_package.py`. (Found elsewhere ⇒ warn; not found ⇒ fail — a repo with no installer cannot deploy.) |
| **PKG-A2** | SHOULD | static | The standalone feature lives under `core/` (zero AIOS dependency). A single-file package may legitimately differ. |
| **PKG-A3** | SHOULD | static | A `docs/` directory carries design notes / ADRs / examples. |

### I — Installer interface

| ID | Level | Verify | Rule |
|----|-------|--------|------|
| **PKG-I0** | MUST | static | The installer parses as valid Python. |
| **PKG-I1** | MUST | static | It exposes all four subcommands: `install`, `uninstall`, `update`, `status` (argparse subparsers). |
| **PKG-I2** | MUST | static | Imports are **standard-library only** (plus local sibling modules). No third-party dependency, so it runs on any AIOS host with no `pip install`. Python is house style, 3.8+. |
| **PKG-I3** | SHOULD | static | Accepts a `--horizon-root` override rather than depending on `$HORIZON_ROOT` alone. |

### N — Namespace

| ID | Level | Verify | Rule |
|----|-------|--------|------|
| **PKG-N1** | MUST | static | The installer (and the package) use the `horizon_<name>_*` namespace and **never** `horizon_aios_*` — that prefix is reserved for the OS core. |

### R — Registration

| ID | Level | Verify | Rule |
|----|-------|--------|------|
| **PKG-R1** | MUST | static | `install` registers the package in the deployed-packages registry (`horizon_deployed_packages.local.json`, schema `horizon_deployed_packages/v1`) so the AIOS sync can protect, update, and inventory it. |
| **PKG-R2** | MUST | static | The registered entry carries every required field: `name`, `version`, `clone_path`, `upstream`, `remotes`, `role`, `pull_only`, `sync`, `install_entrypoint`, `payload`. |

### D — Deployment discipline

| ID | Level | Verify | Rule |
|----|-------|--------|------|
| **PKG-D1** | SHOULD | static | A deployment clone is made **pull-only** (push disabled): it only ever *receives* from upstream. The dev publishes from the development canon. |
| **PKG-D2** | SHOULD | static | `update` is **upstream-authoritative**: `git fetch` + `git reset --hard <upstream>` (local overwritten, not merged), then re-deploy. |

### L — Machine-local file hygiene

| ID | Level | Verify | Rule |
|----|-------|--------|------|
| **PKG-L1** | MUST | static | Any machine-local `.local.*` file the installer materializes is git-ignored via **`.git/info/exclude`**, never the tracked `.gitignore` (which the official sync lane overwrites). |

### U — Uninstall

| ID | Level | Verify | Rule |
|----|-------|--------|------|
| **PKG-U1** | MUST | static | `uninstall` reverses the deploy (driven by the `payload` manifest) and deregisters the package. |
| **PKG-U2** | MUST | human | `uninstall` preserves user-created data (self-contained artifacts are never orphaned). Confirm by reading `cmd_uninstall`. |

### S — Scheduled tasks / cron

An installer *may* create recurring jobs (Task Scheduler, cron, launchd, systemd timers). Because the
checker never runs the installer, it can only inspect these statically — it tells you they exist and
whether they look sane, so you know to verify them in your post-install test.

| ID | Level | Verify | Rule |
|----|-------|--------|------|
| **PKG-S1** | — | static | Detect whether the installer creates scheduled jobs and report which kind. (Informational — always flagged for post-install verification.) |
| **PKG-S2** | SHOULD | static | Any literal cron expression is syntactically valid (5–6 fields, each within range). Expressions built at runtime cannot be checked and are noted as such. |
| **PKG-S3** | SHOULD | static | If `install` schedules a job, `uninstall` removes it (`schtasks /delete`, `crontab -r`, `Unregister-ScheduledTask`, `launchctl bootout`, `systemctl disable`). |

---

## Authoring shortcut

The fastest path to a READY package is to **copy the LAPP installer** and adapt it:
`deployed_packages/horizon_agentic_project_planning/aios/install/horizon_project_planning_package.py`.
Its helpers already satisfy PKG-I/R/D/L/U: `resolve_paths`, `read_registry`/`write_registry`,
`ensure_gitignored`, `configure_pull_only`, `is_deployment_clone`, and a `payload`-driven `uninstall`.
Keep behavior in `core/` (PKG-A2), keep the wrapper thin, and rename everything to your
`horizon_<name>_*` namespace (PKG-N1).

## Interpreting the result

- **NOT READY** — a MUST failed. Fix every `[FAIL]` before attempting to deploy.
- **READY WITH WARNINGS** — all MUSTs pass; the SHOULDs flagged are worth addressing but do not block.
- **READY** — structurally conformant. **Now run the real lifecycle test** (`install → status → update
  → uninstall`) in a sandbox; the checker cannot do that for you.
