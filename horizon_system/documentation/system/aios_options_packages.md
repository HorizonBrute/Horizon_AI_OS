---
type: Explanation
title: "Horizon AIOS — Options Packages"
description: What an AIOS Options Package is, the standalone + installer/uninstaller contract, the deployed-packages registry, clone location, sync integration (protection gate + update pass + pull-only deployments), the build/install/maintain/uninstall lifecycle, and how to adopt a generic (non-AIOS) GitHub repo as a package.
tags: [options-packages, extensibility, deployment, sync, registry]
timestamp: 2026-07-19
status: draft
source_of_truth: doc
category: cross-cutting
---

# Horizon AIOS — Options Packages

An **Options Package** is an optional, separately-versioned feature you can deploy into a Horizon AIOS
install without it being part of the OS core. Options packages are how the AIOS is extended: a package
ships its own repository, is cloned into the install, registers itself, and is thereafter kept current,
protected, and backed up by the AIOS sync — while the OS core stays lean and neither owns nor ships it.

> **See also:** the install & troubleshooting how-to — `../deployment/aios_options_packages.md`.

The first options package is **Horizon Lightweight Agentic Project Plans (LAPP)**
(`horizon_agentic_project_planning`), which adds the `/project-plan` skill. It is used as the worked
example throughout.

## The contract (what makes something an Options Package)

A conforming options package **MUST**:

1. **Be standalone.** It must work fully on its own, with no dependency on Horizon AIOS. An agent or a
   human must be able to use it in a plain repository. (LAPP's `core/` is the whole system; the AIOS
   layer only adds discovery and install.) This keeps packages portable and testable outside the OS.
2. **Ship an installer and uninstaller for AIOS.** A cross-platform, standard-library entrypoint
   (Python is house style; namespace it `horizon_<package>_*`, never `horizon_aios_*` — that prefix is
   the OS core's) exposing at least `install`, `uninstall`, `status`, and `update`. `install` deploys
   the package's artifacts and **registers** the package; `uninstall` reverses the deploy without
   destroying user data the package created; `update` refreshes the deployment from upstream.
3. **Register itself** in the machine-local deployed-packages registry (below) so the AIOS sync can
   protect, update, and inventory it.

A conforming package **SHOULD** keep the OS-facing wrapper thin: all real behavior lives in the
standalone part, and the AIOS layer only wires discovery, installation, and sync integration.

## Anatomy

```
<package>/
  core/            # STANDALONE — the entire feature, zero AIOS dependency
  aios/            # OPTIONAL wrapper — thin; discovery + install, no new behavior
    install/horizon_<package>_package.py   # install / uninstall / update / status
  docs/            # package docs (design, decisions/ADRs, examples)
```

The installer copies whatever the package deploys (a skill, a tool, config) into the appropriate AIOS
location, injects any discovery context, and registers the package. A package's catalog row is
machine-local: it is written to `$HORIZON_SKILLS_BIN/index.local.md` (untracked) plus the
deployed-packages registry, so the registration survives OS/official-lane updates; the tracked
`$HORIZON_SKILLS_BIN/index.md` lists core skills only.

## The deployed-packages registry

Registry file: **`$HORIZON_ETC/horizon_deployed_packages.local.json`** (schema
`horizon_deployed_packages/v1`). It is **machine-local** by design — the set of installed packages
differs per machine. The `.local.json` name means it is git-ignored from OS canon (so an upstream sync
never overwrites it) yet carried by the hourly personal backup sync (its name matches the `*local*`
re-include rule). Each entry:

| Field | Meaning |
|---|---|
| `name` | package name |
| `version` | package version at install |
| `clone_path` | clone location **relative to `$HORIZON_ROOT`** |
| `upstream` | the canonical upstream URL (where updates come from) |
| `remotes` | the clone's actual git remotes (captures forks) |
| `role` | `deployment` (a mirror) or `development-canon` (the dev checkout) |
| `pull_only` | true if the clone's push is disabled (a deployment) |
| `sync` | if `false`, the sync neither protects nor updates it |
| `install_entrypoint` | installer path **within the clone**; the sync runs `<entrypoint> update` |
| `payload` | manifest of what was deployed (for exact uninstall) |

## Clone location

A deployed package is a git clone at **`$HORIZON_SYSTEM/deployed_packages/<name>/`** — a dedicated home,
separate from user `projects/` and OS tooling `usrbin/`. It lives under the official-owned
`horizon_system/`, so it depends on the sync gate (below) to survive upstream syncs.

## Sync integration

The two-lane OS sync (`horizon_aios_sync.py`) treats registered packages three ways:

1. **Protection gate.** The official lane overwrites everything except `projects/usrbin/brains` from
   upstream. `official_pathspec()` additionally **excludes every registered clone with `sync != false`**,
   so an upstream sync can never clobber a separately-versioned package that lives under
   `horizon_system/`. (`horizon_aios_sync.py --status` reports the protected count.)
2. **Update pass.** After the official lane, `update_options_packages()` invokes each registered
   package's own `install_entrypoint update` — `python <clone>/<install_entrypoint> update`. This is
   how registration *is* enrollment: a package's installer registers it, and that registration adds it
   to the update pass with no per-package sync code. Disable with `UPDATE_OPTIONS_PACKAGES=no`; run in
   isolation with `horizon_aios_sync.py --update-packages`. Best-effort: a failing package is logged
   and skipped, never failing the OS sync.
3. **Backup.** Each clone is a nested git repo, so the nightly nested-repo sync backs it up to its own
   remote (subject to that clone's push configuration).

### Pull-only deployments

A **deployment** is a read-only mirror: the installer configures its clone **pull-only** (push URL
pointed at a disabled sentinel), and `update` is **upstream-authoritative** (`git fetch` +
`git reset --hard <upstream>`, local overwritten). The developer publishes from the **development
canon** (a separate checkout with push enabled); a deployment only ever *receives*. The installer
distinguishes the two by clone path (under `deployed_packages/` ⇒ deployment). This enforces one-way
flow: **canon → upstream → deployment**. See the LAPP `docs/decisions/ADR-0008`.

## Lifecycle

1. **Build** — develop the standalone core and the thin AIOS wrapper (installer with
   install/uninstall/update/status). Keep the OS namespace clean (`horizon_<package>_*`).
2. **Publish** — push the development canon to the package's upstream repository.
3. **Install** — on the target AIOS:
   ```
   git clone <upstream> "$HORIZON_SYSTEM/deployed_packages/<name>"
   python "$HORIZON_SYSTEM/deployed_packages/<name>/aios/install/horizon_<name>_package.py" install
   ```
   `install` deploys artifacts, configures the clone pull-only, and registers the package.
4. **Maintain** — the AIOS sync's update pass keeps the deployment current automatically; or run
   `… <entrypoint> update` (or `horizon_aios_sync.py --update-packages`) on demand.
5. **Uninstall** — `… <entrypoint> uninstall` reverses the deploy and deregisters the package. It
   leaves the clone and any user data the package created (self-contained artifacts are never orphaned).

## Adopting a generic (non-AIOS) GitHub repo as a package

Most useful repositories were not built with AIOS in mind. To adopt one as an options package you add
a thin AIOS wrapper around it — you do not rewrite it:

1. **Fork or vendor** the upstream repo into a repository you control (you need somewhere to add the
   wrapper and to publish from). The original repo is already "standalone" — the contract's first
   requirement is satisfied for free.
2. **Add the AIOS wrapper** — an `aios/` directory with a `horizon_<name>_package.py` installer meeting
   the contract. Its `install` must:
   - copy/deploy the repo's artifacts into the right AIOS location (a skill → `skills_bin/<name>/`; a
     CLI tool → wherever it belongs; config → its target), and inject any discovery context;
   - **register** the package in `$HORIZON_ETC/horizon_deployed_packages.local.json` with `clone_path`,
     `upstream`, `remotes`, `role`/`pull_only`, `sync`, `install_entrypoint`, and a `payload` manifest;
   - configure a deployment clone **pull-only** and git-ignore any machine-local `.local.*` files it
     materializes (via the repo's `.git/info/exclude`, not a tracked `.gitignore`).
   Its `uninstall` reverses exactly that from the `payload`; `update` does fetch + reset-to-upstream +
   redeploy; `status` prints the registry view.
3. **Keep the fork current with the original** using git's normal two-remote model: track the original
   as a second remote and merge its releases into your fork, then publish. Your fork is the package's
   `upstream`; deployments pull from your fork.
4. **Publish and install** as in the lifecycle above.

The wrapper is small and mechanical; the LAPP installer
(`deployed_packages/horizon_agentic_project_planning/aios/install/horizon_project_planning_package.py`)
is the reference implementation to copy from.

## Worked example — LAPP

- Upstream: the LAPP GitHub repository; deployments clone it to
  `$HORIZON_SYSTEM/deployed_packages/horizon_agentic_project_planning/`.
- Installer: `aios/install/horizon_project_planning_package.py` (`install`/`uninstall`/`update`/`status`).
- Deploys the `/project-plan` skill to `skills_bin/project-plan/` (+ a copy of `core/` as `kit/`),
  injects a terse context pointer into `projects/agents.md`, materializes an admin `.local.` guide
  override, and registers itself.
- Protected by the sync gate; updated by the sync update pass; pull-only as a deployment.

## Requirements checklist

- [ ] Works standalone with no AIOS dependency.
- [ ] Ships `horizon_<name>_package.py` with `install` / `uninstall` / `update` / `status`.
- [ ] `install` registers the package (name, version, clone_path, upstream, remotes, role, pull_only,
      sync, install_entrypoint, payload).
- [ ] Deployment clone configured pull-only; `update` is upstream-authoritative.
- [ ] Machine-local `.local.*` files git-ignored via `.git/info/exclude`, not tracked `.gitignore`.
- [ ] Namespace is `horizon_<name>_*`, never `horizon_aios_*`.
- [ ] `uninstall` reverses the deploy and deregisters, without destroying user data.
