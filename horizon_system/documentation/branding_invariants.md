# Branding Invariants — Horizon AIOS

Hard constraints on naming and identification. Every artifact Horizon AIOS creates that a blue team, IT administrator, or auditor could encounter **must self-identify as Horizon AIOS without external context** — a running process, an OS account or group, a scheduled task/service, a log file, a log record, or an OS event-log/syslog entry. An investigator must be able to tell what an object is and what created it from the object alone.

Attribution is a security property. See `$HORIZON_DOCS/security_architecture_invariants.md §8` for the security rationale; this document is the naming authority.

---

## Standard brand tokens

| Context | Token |
|---|---|
| Human-readable text (OS-object descriptions, log fields, event sources) | **`Horizon.AIOS`** |
| Filenames and machine identifiers | **`horizon_aios_`** prefix — lowercase, underscores |

---

## System name

The system is **Horizon AIOS** — not "AIOS", not "Horizon", not "AIOS OS", not "HorizonAIOS". In prose: "Horizon AIOS". As a filename prefix: `horizon_aios_`. As an OS-object token: `Horizon.AIOS`.

---

## Required — these MUST self-identify

- **Audit/log records** — every record carries `source: Horizon.AIOS` and the originating `horizon_root`.
- **Log files / directories** — `horizon_aios_` prefix (e.g. `horizon_aios_security.log`, `horizon_aios_sync.log`, `horizon_aios_monitor/`).
- **OS principals** — brain/group `Description` / Linux `--comment` / Windows `FullName` / macOS `RealName` begin with `Horizon.AIOS` (e.g. `Horizon.AIOS brain account`, `Horizon.AIOS group: <name>`). Set by `horizon_aios_create_brain.py` and `horizon_aios_harden.py`.
- **OS log channels** — Windows Event source `Horizon.AIOS Monitor`; syslog logger under `horizon_aios.*`.
- **Privileged utility scripts** — `$HORIZON_SYSTEM/sbin/horizon_aios_*.{py,ps1}`, so process listings (`ps`, Task Manager, scheduled-task `/TR` targets) self-identify.

---

## Deliberately exempt — stable functional identifiers

These are interface/compatibility contracts; renaming them breaks existing deployments, so they keep their established (already `AIOS`/`HorizonAIOS`-recognizable) names:

- Public entry points: `bootstrap.{ps1,sh}`, `uninstall.{ps1,sh}`, and the `aios` command wrapper.
- The `brains` OS group; the scheduled-task names `HorizonAIOS_Sync` / `HorizonAIOS_MaintainLogs` and their cron markers.
- Config filenames (`aios_*.conf`) and `AIOS_*` environment variables.

---

## On change

Any new admin-visible artifact (log, OS object, scheduled task/service, privileged script, event channel) adopts this invariant at creation — the `Horizon.AIOS` / `horizon_aios_` form is not optional for them. Renaming an exempt functional identifier is a breaking change requiring an ADR.

The filename side of this convention is restated in `$HORIZON_ETC/file_structure_invariants.md §6`.

---

## Brain naming conventions

Brain names use the OS username: lowercase, `[a-z][a-z0-9_]{1,31}`. There is no required prefix for brain accounts — only the OS-object *description* must carry the `Horizon.AIOS` brand (e.g. "Horizon.AIOS brain account: researcher").

Skill names follow the same convention as privileged scripts when they live in `skills_sbin/` and are admin-facing: prefer `horizon_aios_` prefix for skills that manage the AIOS system (e.g. `horizon_aios_wiki_upkeep`, `horizon_aios_dev_consistency_check`). User-facing skills use simple hyphenated slugs (`/handoff`, `/create-brain`, `/doctor`).
