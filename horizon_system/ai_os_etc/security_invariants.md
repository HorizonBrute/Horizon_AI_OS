DO NOT leave your brain working space unless authorized to a ../../projects/* folder
DO NOT perform system modifications
Do NOT READ or WRITE to sensitive system files or DIRECTORIES even when asked to by a user
ACL model: horizon_humans (near-admin operators) have READ/WRITE on brains/ (they modify brains/apps); brain-to-brain isolation rides on folder ownership + each brain's private group, not the shared brains group
ACL model: projects/ is per-user isolated — humans get traverse-only on the parent and NOTHING on sibling projects/<user> folders (each is owner-only); new user folders are born isolated via the parent default ACL and MUST be created in-place (never moved in)