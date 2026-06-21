# Horizon AIOS — Docker Deployment

Deploys the AIOS OS layer as a Docker container. Brains run as sub-containers (one container per brain) or as OS users within the AIOS container. See `philosophy.md §5` for the conceptual model.

**Status:** Template only — not yet end-to-end verified. See `tested_configurations.md`.

---

## Prerequisites

- Docker Engine ≥24 and Docker Compose ≥2.20 installed on the host.
- `ANTHROPIC_API_KEY` set in your environment (or a `.env` file in the deployment directory).
- The Horizon AIOS repo cloned to the host.

---

## Quick Start

All commands run from `$HORIZON_ROOT` (the repo root).

```bash
# Build the AIOS image
docker build \
  -f horizon_system/templates/docker/Dockerfile \
  -t horizon-aios \
  .

# Start the AIOS container
docker compose \
  -f horizon_system/templates/docker/docker-compose.yml \
  up -d

# Open an interactive Claude Code session inside the container
docker exec -it horizon-aios claude
```

---

## Volumes and Mutable State

The Docker image bakes in the AIOS layer (repo contents + bootstrap). Mutable state must be volume-mounted from the host to persist across container restarts and rebuilds.

| Volume / Mount | Default (named volume) | Notes |
|---|---|---|
| `/aios/horizon_system/logs` | `aios-logs` | Audit and operational logs |
| `/aios/handoffs` | `aios-handoffs` | Session handoff documents |
| `/aios/brains` | Host path (commented out) | Brain directories — set `HOST_BRAINS_PATH` in compose file |

Edit `horizon_system/templates/docker/docker-compose.yml` to mount host paths before starting.

---

## Brain Isolation in Docker

In a native AIOS deployment, each brain is an OS user account. In Docker, each brain is a separate container.

**Brain container model:**
1. Uncomment and duplicate the `brain-template` service block in `docker-compose.yml`.
2. Give the brain its own named volume for `/aios/brains/BRAINNAME`.
3. Inject credentials for the brain via environment variables (set in the compose service definition); retrieve from the OS credential store or a secrets manager on the host.
4. Mount `skills_bin` read-only into `/aios/horizon_system/skills_bin`.
5. The brain container has no access to `sbin/` or `skills_sbin/` — enforce with Docker security options or read-only mounts.

**Audit trail in Docker:** The AIOS container's audit log volume (`aios-logs`) must not be accessible to brain containers. Do not mount it into brain service definitions.

---

## Rebuilding After AIOS Updates

The AIOS layer is baked into the image. After pulling a new version of the repo:

```bash
docker compose -f horizon_system/templates/docker/docker-compose.yml build
docker compose -f horizon_system/templates/docker/docker-compose.yml up -d
```

Named volumes (`aios-logs`, `aios-handoffs`) persist across rebuilds. Host-mounted brain and key directories are unaffected.

---

## BYOH — Swapping the Harness

Claude Code is the default harness in the Dockerfile. To use a different harness:

1. Remove the Node.js and `npm install -g @anthropic-ai/claude-code` blocks from the Dockerfile.
2. Add your harness installation commands in their place.
3. Update the `CMD` line to launch your harness, or leave it as `["bash"]` and invoke the harness via `docker exec`.

The AIOS OS layer (env vars, bootstrap, skills, audit hooks, brain isolation) is harness-agnostic.

---

## Known Gaps

- `create_brain.py` is not yet adapted for Docker — it provisions OS user accounts, not Docker containers. Brain container provisioning is currently manual (duplicate the compose service template).
- `bootstrap_docker.sh` runs the standard bootstrap; the skills symlink (`~/.claude/skills/ → skills_sbin/`) is created but not verified in a full session.
- Sync schedule (`setup_sync_schedule.py`) is skipped in Docker mode. AIOS updates are delivered by rebuilding the image.
- macOS Docker host has not been tested; Linux Docker host is the target environment.
