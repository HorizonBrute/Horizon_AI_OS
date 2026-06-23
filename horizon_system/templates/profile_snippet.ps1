# Horizon AIOS - add this line to your PowerShell profile ($PROFILE).
# It loads HORIZON_ROOT + all derived vars for whichever AIOS is active.
# 'aios switch <name>' regenerates active_env.ps1, so switching repoints your
# shell without editing this profile. See $HORIZON_DOCS/system/aios_switching.md.
if (Test-Path "$HOME\.horizon\active_env.ps1") { . "$HOME\.horizon\active_env.ps1" }
