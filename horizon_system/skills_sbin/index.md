# Skills Index — skills_sbin

Owner-only privileged skills. Brain users must not have access to this directory.

- **Windows:** explicit ACL Deny (Read, Execute) for all brain user accounts
- **Unix:** chmod 700, owned by primary user

**When adding a skill to skills_sbin: add an entry here in the same commit.**

| Skill | Trigger | Purpose |
|---|---|---|
| handoff | `/handoff` | Write a structured session handoff document |
| objective | `/objective` | Create/list/show/update durable multi-session objectives that handoffs chain back to |
| skill-creation | `/skill-creation` | Create a new AIOS skill with correct structure and index registration |
