# Contributing to Horizon AIOS

Thank you for contributing. Horizon AIOS uses AGPL-3.0 as its public license
and offers a commercial license for proprietary use. To maintain the integrity
of the dual-licensing model, all contributions must include a Developer
Certificate of Origin (DCO) sign-off.

## Developer Certificate of Origin (DCO)

The DCO is a lightweight way to certify that you wrote the contribution and
have the right to submit it. It does not require a formal agreement — just a
sign-off line in your commit message.

**Add this to every commit:**

```
Signed-off-by: Your Name <your@email.com>
```

This certifies that:
- You wrote the contribution, or have the right to submit it.
- You understand the contribution will be licensed under AGPL-3.0 (and may also
  be used under a commercial license issued by the project owner).
- You are not submitting code with incompatible license obligations.

**How to add it:** Use `git commit -s` (the `-s` flag adds the line automatically)
or add it manually to your commit message.

PRs without a sign-off on every commit will be held until the sign-off is added.

---

## What's Welcome

1. **Skills** — new slash commands or harness behaviors useful across machines
2. **Sounds** — audio files for Claude lifecycle events (see `horizon_system/sounds/`)
3. **Harness configs** — settings and hooks for non-Claude backends (Ollama, Codex, etc.)
4. **Statusline improvements** — enhancements to the cross-platform statusline scripts
5. **Documentation** — corrections and additions to setup guides and reference docs
6. **Bug fixes** — fixes to scripts, hooks, or configuration errors

## What's Out of Scope

Individual user brains, personal configurations, and machine-specific files do not belong
in this repo. The system is designed so that personal layers live outside version control
or in separate forks.

## Path Placeholder Rule

All committed files must use the canonical env-var references (`$HORIZON_ROOT`, `$HORIZON_SYSTEM`,
`$HORIZON_BIN`, `$HORIZON_ETC`, etc.) instead of any hardcoded absolute path. Setup templates
that cannot reference env vars at copy time use substitution placeholders (e.g.,
`AIOS_EXEC_WRAPPER` in the Claude Code settings template; `[HORIZON_ROOT_PATH]` and
`[BRAIN_NAME]` in brain workspace templates). Submitting a file with a hardcoded path like
`C:\devroot` or `/home/user/devroot` will cause the PR to be rejected.

## No Personal Data

Do not include real names, email addresses, GPG key fingerprints, hostnames, or
machine-specific paths in any committed file. This mirrors the security invariants
documented in `horizon_system/documentation/security_architecture_invariants.md` (section 6).

## How to Contribute

1. Fork the repository.
2. Make your changes on a feature branch.
3. Open a pull request with a brief description of what changed and why.
