# Skills Index — skills_sbin

Owner-only privileged skills. Brain users must not have access to this directory.

- **Windows:** explicit ACL Deny (Read, Execute) for all brain user accounts
- **Unix:** chmod 700, owned by primary user

**When adding a skill to skills_sbin: add an entry here in the same commit.**

| Skill | Trigger | Purpose |
|---|---|---|
| create-brain | `/create-brain` | Provision a new brain — OS user, groups, workspace, shell profile, keystore credential (Admin/root) |
| handoff | `/handoff` | Write a structured session handoff document |
| harden | `/harden` | Apply the authoritative brains-group ACL model to the AIOS layer (Admin/root) |
| objective | `/objective` | Create/list/show/update durable multi-session objectives that handoffs chain back to |
| remove-brain | `/remove-brain` | Deprovision a brain — remove its OS user, per-brain group, workspace, profile, and credential (Admin/root) |
| resync-user-skills | `/resync-user-skills` | Rebuild junctions registering machine-local user skills (usrbin/usr_skills) into skills_sbin |
| skill-creation | `/skill-creation` | Create a new AIOS skill with correct structure and index registration |
| horizon_aios_dev_consistency_check | `/horizon_aios_dev_consistency_check` | Run an iterative docs/implementation consistency validation pass against the consistency-check standard |
| horizon_aios_documentation_index_update | `/horizon_aios_documentation_index_update` | Create/rebuild the documentation index so every doc is referenceable by a stable entry |
