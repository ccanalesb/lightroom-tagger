FROM node:24-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y \
  git \
  curl \
  jq \
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

ENV PATH="/home/agent/.local/bin:$PATH"

# Pre-bake the backend's (heavy: sharp, better-sqlite3, transformers) dependencies
# into the image so every run is fast and offline. Only the manifests are copied
# here, so this layer caches across code changes. A runtime hook symlinks
# node_modules into the bind-mounted worktree.
WORKDIR /home/agent/.be-deps
COPY apps/visualizer/backend-ts/package.json apps/visualizer/backend-ts/package-lock.json ./
RUN npm ci --no-audit --no-fund

# Pre-bake the frontend deps too (same rationale). Skip Playwright's browser
# download — the contract check needs none.
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
WORKDIR /home/agent/.fe-deps
COPY apps/visualizer/frontend/package.json apps/visualizer/frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps --no-audit --no-fund

WORKDIR /home/agent

# In worktree sandbox mode, Sandcastle bind-mounts the git worktree at /home/agent/workspace
# and overrides the working directory to /home/agent/workspace at container start.
ENTRYPOINT ["sleep", "infinity"]
