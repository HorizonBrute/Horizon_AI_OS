# Skills Index — skills_sbin

Owner-only privileged skills. Brain users must not have access to this directory.

- **Windows:** explicit ACL Deny (Read, Execute) for all brain user accounts
- **Unix:** chmod 700, owned by primary user

**When adding a skill to skills_sbin: add an entry here in the same commit.**

| Skill | Trigger | Model group | Purpose |
|---|---|---|---|
| create-brain | `/create-brain` | `#lowcost` | Provision a new brain — OS user, groups, workspace, shell profile, keystore credential (Admin/root) |
| harden | `/harden` | `#highcap` | Apply the authoritative brains-group ACL model to the AIOS layer (Admin/root) |
| pre-flight-tooling-validation | `/pre-flight-tooling-validation` | `#investigate` | Validate the repo ships full-lifecycle tooling per platform (install/brain/2nd-AIOS/switch/delete), then emit an admin/sudo test-run prompt per platform |
| objective | `/objective` | `#lowcost` | Bare `/objective` surfaces the conversation's active objective (else lists/creates); create/list/show/update durable multi-session objectives that handoffs chain back to |
| remove-brain | `/remove-brain` | `#highcap` | Deprovision a brain — remove its OS user, per-brain group, workspace, profile, and credential (Admin/root) |
| resync-user-skills | `/resync-user-skills` | `#lowcost` | Rebuild symlinks registering machine-local user skills (usrbin/usr_skills) into skills_sbin |
| skill-creation | `/skill-creation` | `#midcost` | Create a new AIOS skill with correct structure and index registration |
| model-prefs | `/model-prefs` | `#midcost` | Configure/inspect the in-context model-preference layer (groups incl. local/BYO models, slots, task-class routing) via the gitignored extend file |
| horizon_aios_dev_consistency_check | `/horizon_aios_dev_consistency_check` | `#midcost` | Run an iterative docs/implementation consistency validation pass against the consistency-check standard |
| horizon_aios_documentation_index_update | `/horizon_aios_documentation_index_update` | `#lowcost` | Create/rebuild the documentation index so every doc is referenceable by a stable entry |
| model-prefs-assign | `/model-prefs-assign` | `#lowcost` | Audit AIOS skills for their model-preference group callout and assign/refresh it, keeping both skill indexes' Model-group columns in sync |
| agent-teams | `/agent-teams` | `#midcost` | Bare `/agent-teams` lists the loaded agent_teams.md/local.agent_teams.md files and their team names; otherwise create/edit team definitions at any scope (chain, per-role model groups, loop/retry constructs) |
| horizon_aios_wiki_upkeep | `/horizon_aios_wiki_upkeep` | `#highcap` | Consistency pass between the operational wiki and its source documentation — finds drift, stale paths, outdated examples; fixes unambiguous issues and surfaces judgment calls |
| terseness-check | `/terseness-check` | `#highcap` | Evaluate every file in the Terseness Contract Index for context overhead — flags verbose prose, redundant rationale, unnecessary examples; reports FAIL/ADVISORY with file:line evidence and cut suggestions. Delegated by CC-T2 in the consistency check. |
| test-agent-teams | `/test-agent-teams` | `#midcost` | End-to-end self-test: walk every defined agent team, spawn each role so it echoes a nonce + its role + what it was told to do (charter) + the model it actually ran as; per-team table + PASS/FAIL of resolution + model routing |
| context-cost | `/context-cost` | `#lowcost` | Report harness context overhead (KB, words, ~tokens) for a given path — walks the directory tree collecting CLAUDE.md, agents.md, and @-import files the harness auto-loads. Symlink → skills_bin/context-cost. |
| convert-prompt-to-saill | `/convert-prompt-to-saill` | `#midcost` | Convert a natural-language prompt into a SAILL agent-team flow (roles + model groups + flags + boxes + loops + -context-); outputs the SAILL block + a gloss, then offers to save/run/test it |
| context-cost-tree | `/context-cost-tree` | `#lowcost` | Walk every directory under a root path and report harness context overhead (tokens, KB, words) per directory, with a grand summary table sorted by token cost descending |
