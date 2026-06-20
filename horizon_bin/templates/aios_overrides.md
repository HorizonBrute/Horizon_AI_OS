# aios_overrides.md — Project-Level AIOS Configuration Overrides
#
# PURPOSE
# -------
# This file lets a project override Horizon AIOS defaults without touching
# the OS-level configuration. Place a copy of this file at your project root
# (not inside .claude/) and configure the keys below.
#
# USAGE
# -----
# Copy this template to <your-project-root>/aios_overrides.md and uncomment
# the keys you want to override. Keys that remain commented-out (or are
# absent from the file entirely) fall back to AIOS defaults automatically.
#
# FORMAT
# ------
# Each key is on its own line in the format:
#
#   key: value
#
# Values are plain strings. No quotes. No YAML or JSON — just key: value.
# Lines beginning with # are comments and are ignored.
# Blank lines are ignored.
#
# HOW AIOS READS THIS FILE
# ------------------------
# The /handoff skill (and any other AIOS skill that supports overrides) walks
# upward from the current working directory looking for this file, stopping at
# $HORIZON_ROOT. The first aios_overrides.md found wins. If no file is found,
# all defaults apply.
#
# EXTENSIBILITY
# -------------
# New override keys can be added below as AIOS gains new configurable behaviors.
# Each new key must be documented here with its purpose, default, and valid values.

# =============================================================================
# KEY: handoffs_dir
# =============================================================================
# PURPOSE:  Override the directory where /handoff writes session handoff docs.
# DEFAULT:  $HORIZON_ROOT/handoffs/  (e.g., C:\devroot\handoffs\)
# USE WHEN: You want handoffs for this project stored inside the project folder
#           (e.g., in its own docs/handoffs/ directory) rather than the central
#           AIOS handoffs directory.
# VALUE:    Absolute path. On Windows, use backslashes or forward slashes.
#           The directory will be created if it does not exist.
# EXAMPLE:
#   handoffs_dir: C:\devroot\MyProject\docs\handoffs
#
# handoffs_dir:

# =============================================================================
# KEY: project_display_name
# =============================================================================
# PURPOSE:  Override the project name used in handoff document headers and
#           handoff filenames. Without this key, AIOS derives the name from
#           the basename of the current working directory.
# DEFAULT:  basename of the current working directory
# USE WHEN: The directory name is a code name, slug, or otherwise not what you
#           want to appear in handoff docs (e.g., "sp" -> "SorceryPunk").
# VALUE:    Human-readable display name. Spaces are allowed. For the filename,
#           spaces are converted to hyphens automatically.
# EXAMPLE:
#   project_display_name: SorceryPunk
#
# project_display_name:

# =============================================================================
# FUTURE KEYS (reserved for upcoming AIOS features — not yet active)
# =============================================================================
#
# default_handoff_recipient:
#   Who the /handoff skill addresses handoffs to by default for this project.
#   Example: default_handoff_recipient: next session
#
# skills_disabled:
#   Comma-separated list of AIOS skill names to suppress for this project.
#   Example: skills_disabled: handoff, doc-sync
