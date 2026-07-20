# Horizon AIOS — Installing Deployable Modules

A **deployable_module** is a standalone git repo that plugs into the AIOS platform. It ships its own
cross-platform, standard-library-only Python installer (`install` / `uninstall` / `update` / `status`).
The reference implementation is the Lightweight Agentic Project Plans (LAPP) package; the steps below
generalize to any module built on that model. See `philosophy.md` for the framework-vs-user-space model.

---

## Deployment model

A canonical deploy is:

1. A **git clone** under `$HORIZON_SYSTEM/deployed_packages/<name>/` (so it can pull its own updates).
2. A machine-local **registry entry** in `$HORIZON_ETC/horizon_deployed_packages.local.json`.
3. The module's **skill payload** copied into `$HORIZON_SKILLS_BIN/<skill>/` (+ a registration row in `$HORIZON_SKILLS_BIN/index.md`).
4. A terse, marker-delimited **context pointer** appended to `$HORIZON_ROOT/projects/agents.md` so project-scope agents discover the feature.
5. A `.local.` **admin override guide** materialized in `$HORIZON_ETC` (admin-editable, never overwritten by updates).

The installer writes only inside `$HORIZON_SKILLS_BIN`, `$HORIZON_ETC`, and a managed block in
`projects/agents.md`. It does not touch privileged system dirs. All five steps are idempotent.

---

## Prerequisite — `HORIZON_*` env vars

The installer resolves paths from `$HORIZON_ROOT` / `$HORIZON_SYSTEM` / `$HORIZON_ETC` /
`$HORIZON_SKILLS_BIN` (with fallback derivations from root). These must be live in the shell:

- **Linux:** `bootstrap.sh` exports all ten `HORIZON_*` vars system-wide via `/etc/profile.d/horizon_aios.sh` (login-shell scope). Use a **login shell** so they are inherited.
- **Windows:** `bootstrap.ps1` sets them at **Machine** scope (`setx`).

If the vars are not set, pass `--horizon-root PATH` explicitly.

> Non-login / systemd contexts on Linux do not inherit `profile.d` exports — a known scope limitation.
> In those contexts, pass `--horizon-root`.

---

## Install

Clone the module to its deployed home, then run its installer from there:

```bash
git clone <module-remote> "$HORIZON_SYSTEM/deployed_packages/<name>"
python "$HORIZON_SYSTEM/deployed_packages/<name>/aios/install/<installer>.py" install
```

Windows/PowerShell is identical — same Python entry point:

```powershell
python "$env:HORIZON_SYSTEM\deployed_packages\<name>\aios\install\<installer>.py" install
```

**Two ways to resolve paths:**

1. **Env-var** (no flag) — resolves from `$HORIZON_ROOT`; requires the vars live in the shell (login shell).
2. **`--horizon-root /path/to/aios`** — explicit override; use when the vars are not exported.

Options: `--force` (overwrite an existing deploy). After install, **restart the harness** (skills load at
session start), then invoke the module's skill.

### Placement matters

| Clone location | Registered role | Effect |
|---|---|---|
| Under `$HORIZON_SYSTEM/deployed_packages/<name>/` | `role=deployment`, `pull_only=true` | Push URL neutered to a sentinel (fetch/pull only), `clone_path` relative-inside-root, **sync-protected**. |
| Anywhere else | `role=development-canon` | Prints a warning that the clone is outside `$HORIZON_ROOT` (no sync coverage). |

Deploy under `deployed_packages/` unless you are the module's developer working from canon.

---

## Sync durability

The AIOS two-lane sync's **official lane** overwrites everything except `projects/usrbin/brains` from
upstream. A module under `horizon_system/` is protected only if the installed
`horizon_system/sbin/horizon_aios_sync.py` is a version whose `official_pathspec()` excludes registered
clones (it reads the deployed-packages registry). Verify:

```
python horizon_system/sbin/horizon_aios_sync.py --status
#   Deployed pkgs : N protected from official overwrite (...)
```

The official lane only hard-restores when the deployment is checked out on the official branch
(`master`); it deliberately skips on a feature branch. Set a package's `sync` to `false` in the registry
to opt it out of protection.

---

## Lifecycle

| Subcommand | Action |
|---|---|
| `install` | Deploys steps 1–5 (idempotent; `--force` to overwrite). |
| `uninstall` | Reverses the skill, index row, context block, and registry entry. **Leaves** the clone, any scaffolded artifacts, and the admin guide. |
| `update` | Git-pulls the deployment clone from upstream, then re-deploys (`install --force`). |
| `status` | Prints the registry and what is currently deployed. |

---

## Verification

```bash
# 1. Installer's own view
python .../aios/install/<installer>.py status

# 2. Skill registration row
grep '<skill>' "$HORIZON_SKILLS_BIN/index.md"

# 3. Context pointer in projects/agents.md
grep -n '<module-marker>' "$HORIZON_ROOT/projects/agents.md"

# 4. Registry entry (role, pull_only, clone_path, sync, payload)
cat "$HORIZON_ETC/horizon_deployed_packages.local.json"

# 5. Sync protection
python horizon_system/sbin/horizon_aios_sync.py --status
```

The registry is `*.local.json` → machine-local: gitignored from OS canon (never rides the official lane)
yet carried by the personal backup sync (its name matches the `*local*` re-include).

---

## Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `HORIZON_ROOT is not set` / empty in shell | Env vars not exported. Ensure `/etc/profile.d/horizon_aios.sh` exports them (re-run bootstrap) and use a login shell, or pass `--horizon-root`. |
| `already deployed at ...` | Re-run with `--force`, or `uninstall` first. |
| Skill / registration row disappears after a nightly sync | Installed sync tool predates deployed-packages protection. Update the AIOS to a `master` with that support and re-run `install --force`. |
| `--status` shows no "Deployed pkgs protected" line | Stale sync tool — same fix as above. |
| Official lane logs "skipping the hard-restore ... not on master" | Check out `master` to run the official lane. |
| Deployment can't push (`DISABLED-pull-only-deployment`) | By design — a deployment is a read-only mirror. Use the `update` subcommand to pull upstream changes. |
| Push shows a "verified signatures" rule violation | The pusher's SSH key isn't registered as a *signing* key on GitHub (auth key ≠ signing key). The commit still lands if admin bypass is allowed. |

### Windows vs Linux parity

Same Python entry point on both. Only the env-var mechanism differs: **Machine** scope via `setx`
(Windows) vs **login-shell** scope via `profile.d` (Linux). Non-login / systemd contexts on Linux will
not inherit `HORIZON_*` — a known scope limitation; pass `--horizon-root` there.
