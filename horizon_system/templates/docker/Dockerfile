# Horizon AIOS — Docker Image Template
# =============================================================================
# Builds the AIOS OS layer with Claude Code CLI pre-installed.
#
# BYOH: To swap Claude Code for another harness, replace the
# "Install Claude Code CLI" block with your harness installation commands.
# The AIOS layer (everything else) is harness-agnostic.
#
# Build (from HORIZON_ROOT):
#   docker build -f horizon_system/templates/docker/Dockerfile -t horizon-aios .
#
# Or via Compose:
#   docker compose -f horizon_system/templates/docker/docker-compose.yml up
#
# Tested on: Ubuntu 22.04 base, Claude Code ≥1.0 CLI
# See: horizon_system/documentation/deployment/docker.md
# =============================================================================

FROM ubuntu:22.04

LABEL org.opencontainers.image.title="Horizon AIOS"
LABEL org.opencontainers.image.description="Horizon AI Operating System layer"
LABEL org.opencontainers.image.licenses="AGPL-3.0"

ENV DEBIAN_FRONTEND=noninteractive

# ---------------------------------------------------------------------------
# System dependencies
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    git \
    curl \
    ca-certificates \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Node.js 20 LTS (required for Claude Code CLI)
# BYOH: remove this block if your harness does not need Node.js
# ---------------------------------------------------------------------------
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Claude Code CLI
# BYOH: replace with your harness installation command
# ---------------------------------------------------------------------------
RUN npm install -g @anthropic-ai/claude-code

# ---------------------------------------------------------------------------
# AIOS user and brains group
# Primary AIOS user runs as "aios" (not root) — mirrors the native OS model.
# ---------------------------------------------------------------------------
RUN groupadd --system brains \
    && useradd --system --create-home --shell /bin/bash --groups brains aios

# ---------------------------------------------------------------------------
# Horizon AIOS environment — fixed container-internal paths
# On native installs these come from shell profile; in Docker they are baked here.
# ---------------------------------------------------------------------------
ENV HORIZON_ROOT=/aios
ENV HORIZON_SYSTEM=/aios/horizon_system
ENV HORIZON_BIN=/aios/horizon_system/bin
ENV HORIZON_ETC=/aios/horizon_system/ai_os_etc
ENV HORIZON_DOCS=/aios/horizon_system/documentation
ENV HORIZON_USRBIN=/aios/usrbin
ENV HORIZON_PROJECTS=/aios/Projects
ENV HORIZON_LOGS=/aios/horizon_system/logs

# ---------------------------------------------------------------------------
# Copy AIOS repo into the image
# Mutable state (logs, handoffs, brains, keys) is expected to be volume-mounted
# at runtime and will overlay these empty scaffold directories.
# ---------------------------------------------------------------------------
WORKDIR /aios
COPY --chown=aios:aios . .

# Ensure mutable directories exist as mount points
RUN mkdir -p /aios/horizon_system/logs \
             /aios/handoffs \
             /aios/brains \
    && chown -R aios:aios /aios

# ---------------------------------------------------------------------------
# Bootstrap the AIOS layer (non-interactive, Docker mode)
# ---------------------------------------------------------------------------
USER aios
RUN bash /aios/horizon_system/sbin/bootstrap_docker.sh

# ---------------------------------------------------------------------------
# Default entry point: interactive shell ready for Claude Code
# Override with: docker run -it horizon-aios claude
# ---------------------------------------------------------------------------
CMD ["bash"]
