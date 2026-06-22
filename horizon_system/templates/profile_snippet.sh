# Horizon AIOS — add this line to your shell profile (~/.bashrc, ~/.zshrc, …).
# It loads HORIZON_ROOT + all derived vars for whichever AIOS is active.
# 'aios switch <name>' regenerates active_env.sh, so switching repoints your
# shell without editing this profile. See $HORIZON_DOCS/system/aios_switching.md.
[ -f "$HOME/.horizon/active_env.sh" ] && . "$HOME/.horizon/active_env.sh"
