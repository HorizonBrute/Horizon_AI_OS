# AIOS Logging Directories — Pruning Registry

> **WARNING — AUTOMATED DELETION**
>
> Every directory listed in this file WILL have its contents automatically and
> irreversibly deleted by `horizon_aios_maintain_logs.py` according to the
> pruning rules below. Do not add a directory here unless you intend for its
> contents to be deleted on a schedule.
>
> This file is the **single source of truth** for what gets pruned. Do not add
> directory paths directly to `horizon_aios_maintain_logs.py` — add them here.
>
> Machine-local overrides (different paths or thresholds for a specific machine)
> go in `aios_logging_dirs.local.md` (gitignored). The script merges local
> overrides at runtime; local entries take precedence over entries here.

---

## Pruned directories

| Directory | Variable | Pruning mode | Default threshold | Config key |
|---|---|---|---|---|
| `$HORIZON_SYSTEM/logs/` | `$HORIZON_LOGS` | Age (files) + size (rotation) | 30 days / 10 MB per file | `AIOS_LOG_MAX_DAYS` / `AIOS_LOG_MAX_SIZE_MB` |
| `$HORIZON_ROOT/handoffs/` | — | Total size budget | 500 MB | `AIOS_HANDOFFS_MAX_SIZE_MB` |
| `$HORIZON_ROOT/objectives/` | — | Age | 90 days | `AIOS_OBJECTIVES_MAX_DAYS` |

### Pruning modes

**Age (files):** Files older than `AIOS_LOG_MAX_DAYS` days are deleted. Applies to all files under `$HORIZON_SYSTEM/logs/`.

**Size (rotation):** `.log` files exceeding `AIOS_LOG_MAX_SIZE_MB` MB are rotated (suffixed `.1`, `.2`, …) up to `AIOS_LOG_ROTATE_KEEP` generations (default: 3). Older rotations are deleted.

**Total size budget:** The entire directory is measured. If total size exceeds the budget threshold, the oldest files are deleted first until the directory is back under budget.

**Age (directory):** Files older than the configured age are deleted regardless of directory size.

### Disabling a category

Set the threshold to `0` in `$HORIZON_ETC/aios_local.conf` to disable pruning for that category:
```
AIOS_LOG_MAX_DAYS = 0          # disables log age pruning
AIOS_HANDOFFS_MAX_SIZE_MB = 0  # disables handoff pruning
AIOS_OBJECTIVES_MAX_DAYS = 0   # disables objective pruning
```

---

## Adding a new directory

To add a directory to automated pruning:

1. Add a row to the table above with the path, pruning mode, default threshold, and the config key name.
2. Implement the corresponding pruning logic in `horizon_aios_maintain_logs.py` referencing this file as the authoritative source.
3. Update `$HORIZON_DOCS/utilities.md` (the `horizon_aios_maintain_logs.py` entry) to document the new target.
4. Add the config key to `$HORIZON_ETC/aios_local.conf.template`.

Do not add a directory to the script without adding it here first.
