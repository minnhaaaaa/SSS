# check=skip=InvalidDefaultArgInFrom
ARG SSS_NODE_BASE_IMAGE
ARG SSS_PYTHON_BASE_IMAGE
FROM ${SSS_NODE_BASE_IMAGE} AS node-runtime

# check=skip=InvalidDefaultArgInFrom
FROM ${SSS_PYTHON_BASE_IMAGE}

ARG SSS_AGENT_UID=65532
ARG SSS_AGENT_GID=65532
ARG SSS_UV_VERSION=0.12.13
ARG SSS_PNPM_VERSION=10.31.0

COPY --from=node-runtime /usr/local /usr/local

WORKDIR /opt/sss
COPY pyproject.toml uv.lock ./
COPY apps ./apps
COPY packages ./packages
COPY demo ./demo

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PATH="/opt/sss/shims:/opt/sss/.venv/bin:/usr/local/bin:/usr/bin:/bin"

RUN python -m pip install --no-cache-dir "uv==${SSS_UV_VERSION}" \
    && corepack enable pnpm \
    && corepack prepare "pnpm@${SSS_PNPM_VERSION}" --activate \
    && cp -a "/root/.cache/node/corepack/v1/pnpm/${SSS_PNPM_VERSION}" /opt/pnpm \
    && rm /usr/local/bin/pnpm /usr/local/bin/pnpx \
    && ln -s /opt/pnpm/bin/pnpm.cjs /usr/local/bin/pnpm \
    && ln -s /opt/pnpm/bin/pnpx.cjs /usr/local/bin/pnpx \
    && uv sync --frozen --no-dev --no-editable \
    && mkdir -p /opt/sss/shims /workspace \
    && cp apps/cli/sss_cli/shims/pnpm /opt/sss/shims/pnpm \
    && chmod 0555 /opt/sss/shims/pnpm \
    && chown -R ${SSS_AGENT_UID}:${SSS_AGENT_GID} /workspace

WORKDIR /workspace
USER ${SSS_AGENT_UID}:${SSS_AGENT_GID}

ENTRYPOINT ["sss-demo-agent"]
