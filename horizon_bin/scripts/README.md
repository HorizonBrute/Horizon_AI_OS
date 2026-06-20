# scripts/

Interactive setup and provisioning scripts. These run as the primary user
(not as brain OS users) and may require elevated privileges.

## create_brain.py

Provisions a new brain OS user with scoped folder access.
Requires Python 3.6+ and must be run as administrator (Windows) or root (Unix).

Usage:
    python create_brain.py <brain-name> [--dry-run]

Options:
    --dry-run    Show what would happen without making changes.

See $HORIZON_DOCS/ReadMeToSetupYourSystem.md for prerequisites.
