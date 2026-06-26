FROM node:22-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y \
  git \
  curl \
  jq \
  python3 \
  python3-venv \
  python3-pip \
  && rm -rf /var/lib/apt/lists/*

# Build-args for UID/GID alignment: sandcastle docker build-image
# defaults these to the host user's UID/GID so image-built files
# and bind-mounted files share an owner without runtime chown.
ARG AGENT_UID=1000
ARG AGENT_GID=1000

# Rename the base image's "node" user to "agent" and align UID/GID.
# If the target GID already exists in the base image (e.g. macOS host GID 20 = staff),
# attach the user to that existing group instead of renaming node's group.
RUN if ! getent group "$AGENT_GID" >/dev/null; then groupmod -g "$AGENT_GID" node; fi \
  && usermod -u "$AGENT_UID" -g "$AGENT_GID" -d /home/agent -m -l agent node
USER ${AGENT_UID}:${AGENT_GID}

# Install Cursor Agent CLI
RUN curl https://cursor.com/install -fsS | bash

# Install uv (fast Python package manager) into ~/.local/bin
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Shared venv outside the bind-mounted repo so it never clobbers the host's.
ENV UV_PROJECT_ENVIRONMENT=/home/agent/venv
ENV VIRTUAL_ENV=/home/agent/venv
# venv first so `python`/`pip` resolve to it; then uv + cursor in ~/.local/bin
ENV PATH="/home/agent/venv/bin:/home/agent/.local/bin:$PATH"

# Pre-bake the project's (heavy) dependencies into the image so every run is
# fast and offline. Only the dependency manifests are copied here, so this
# layer is cached across code changes. The editable project itself is installed
# at runtime via the onSandboxReady hook (deps already satisfied -> fast).
WORKDIR /home/agent/.deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --extra dev

WORKDIR /home/agent

# In worktree sandbox mode, Sandcastle bind-mounts the git worktree at /home/agent/workspace
# and overrides the working directory to /home/agent/workspace at container start.
ENTRYPOINT ["sleep", "infinity"]
