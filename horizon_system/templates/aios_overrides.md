# aios_overrides.md — Project-Level AIOS Configuration Overrides
#
# Place at your project root (not inside .claude/). AIOS skills walk upward
# from cwd to find this file; first match wins; missing keys use AIOS defaults.
#
# Format: key: value  (plain string, no quotes, no YAML/JSON)
# Lines starting with # are ignored. Blank lines are ignored.

# handoffs_dir
#   Where /handoff writes session handoff docs for this project.
#   Default: $HORIZON_ROOT/handoffs/
#   Value: absolute path; created if missing.
# handoffs_dir:

# project_display_name
#   Project name in handoff headers/filenames. Default: basename of cwd.
#   Spaces allowed; converted to hyphens in filenames.
# project_display_name:

# objectives_dir
#   Where /objective stores durable, multi-session objectives for this project.
#   Default: $HORIZON_ROOT/objectives/
#   Value: absolute path; created if missing.
# objectives_dir:

# --- Future keys (reserved, not yet active) ---
# default_handoff_recipient:
# skills_disabled:
