---
name: horizon-options-package-readiness
description: Check whether a repo is ready to deploy as a Horizon AIOS Options Package. Points the static readiness checker at an on-disk repo or a git URL and reports, rule by rule (PKG-*), whether it meets the Options Package Readiness Standard. Use when the user types /horizon-options-package-readiness, asks "is this ready to be a package", "check my options package", "will this deploy as an AIOS package", or before publishing/installing a new package.
tools: Bash, Read
---

# Skill: /horizon-options-package-readiness

**Model preference:** `#lowcost` (per `horizon_aios_model_prefs.md`; overridable by a prompt directive).

Run the **static** Options Package readiness checker and surface its results. It answers one question:
*is this repo structurally ready to deploy as a Horizon AIOS Options Package?* — measured against the
Options Package Readiness Standard (`documentation/system/aios_options_package_readiness.md`, DOC-0055).

---

## When to invoke

The user types `/horizon-options-package-readiness`, or asks to "check if this is a valid options
package", "is my package ready to deploy", "will this repo install as an AIOS package", or wants a
pre-publish / pre-install conformance check.

---

## Step-by-step execution

### Step 1 — Identify the target

The target is either an on-disk repo path or a git URL. If the user gave neither, ask which repo (or
default to the current working directory if they say "this one").

### Step 2 — Run the checker

```
python "$HORIZON_BIN/options_package_readiness.py" <path-or-git-url>
```

- A git URL is shallow-cloned to a temp dir and removed afterward.
- Add `--json` when a machine-readable result is wanted (e.g. feeding another agent).
- Add `--strict` to treat SHOULD warnings as blocking too.

It is **static analysis only** — it never executes the target installer. No elevation required.

### Step 3 — Report the result

3.1 Relay the **VERDICT** line (READY / READY WITH WARNINGS / NOT READY) and the pass/warn/fail/info
counts.

3.2 For each `[FAIL]` and `[WARN]`, surface the `PKG-*` rule ID and the message. FAILs are MUST-rule
violations that block deployment; WARNs are SHOULDs worth fixing. Do not invent fixes beyond what the
finding states; point to the LAPP reference installer and DOC-0055 for the authoring pattern.

3.3 Always restate the scope caveat: a clean result means **structurally ready** — the developer must
still run a real `install → status → update → uninstall` in a sandbox to confirm it works. The checker
cannot do that. If the report flagged scheduled tasks / cron (PKG-S1), emphasize verifying those
post-install.

3.4 Exit code is `1` if any MUST failed (or, under `--strict`, any warning), else `0`. Report
success/failure accordingly.

---

## Notes for the executing agent

- `$HORIZON_BIN` must resolve. If it does not, report that the AIOS environment is not active and the
  user should source their profile or run the AIOS switcher.
- The authoritative ruleset is DOC-0055 (`aios_options_package_readiness.md`); the conceptual
  background is DOC-0054 (`aios_options_packages.md`). The golden-reference package is
  `deployed_packages/horizon_agentic_project_planning/` (LAPP), which scores a clean READY.
