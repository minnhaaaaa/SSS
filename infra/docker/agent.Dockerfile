# check=skip=InvalidDefaultArgInFrom
ARG SSS_NODE_BASE_IMAGE
ARG SSS_PYTHON_BASE_IMAGE
FROM ${SSS_NODE_BASE_IMAGE} AS node-runtime

# check=skip=InvalidDefaultArgInFrom
FROM ${SSS_PYTHON_BASE_IMAGE}

ARG SSS_AGENT_UID=65532
ARG SSS_AGENT_GID=65532
ARG SSS_UV_VERSION=0.12.13
ARG SSS_NPM_VERSION=12.0.2
ARG SSS_PNPM_VERSION=12.4.1
ARG SSS_POETRY_VERSION=2.4.3
ARG SSS_YARN_VERSION=1.22.22
ARG SSS_NPM_TAR_VERSION=7.5.21
ARG SSS_NPM_IP_ADDRESS_VERSION=10.3.1
ARG SSS_NPM_BRACE_EXPANSION_VERSION=5.0.9

COPY --from=node-runtime /usr/local /usr/local

WORKDIR /opt/sss
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PATH="/opt/sss/shims:/opt/sss/.venv/bin:/usr/local/bin:/usr/bin:/bin"

RUN rm -f /usr/local/bin/corepack /usr/local/bin/pnpm /usr/local/bin/pnpx \
        /usr/local/bin/yarn /usr/local/bin/yarnpkg \
    && rm -rf /usr/local/lib/node_modules/corepack \
    && npm install --global "npm@${SSS_NPM_VERSION}" \
    && cd /usr/local/lib/node_modules/npm \
    && npm pkg delete devDependencies \
    && npm install --no-save --ignore-scripts --omit=dev "tar@${SSS_NPM_TAR_VERSION}" \
        "ip-address@${SSS_NPM_IP_ADDRESS_VERSION}" \
        "brace-expansion@${SSS_NPM_BRACE_EXPANSION_VERSION}" \
    && cd /opt/sss \
    && npm install --global "pnpm@${SSS_PNPM_VERSION}" "yarn@${SSS_YARN_VERSION}"

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install "uv==${SSS_UV_VERSION}" "poetry==${SSS_POETRY_VERSION}"

COPY apps ./apps
COPY packages ./packages
COPY demo ./demo

RUN uv sync --frozen --no-dev --no-editable \
    && mkdir -p /opt/sss/shims /workspace \
    && cp apps/cli/sss_cli/shims/* /opt/sss/shims/ \
    && chmod 0555 /opt/sss/shims/* \
    && chown -R ${SSS_AGENT_UID}:${SSS_AGENT_GID} /workspace

WORKDIR /workspace
USER ${SSS_AGENT_UID}:${SSS_AGENT_GID}

ENV SSS_REAL_EXECUTABLES_JSON='{"pip":"/usr/local/bin/pip","pip3":"/usr/local/bin/pip3","python":"/usr/local/bin/python","uv":"/usr/local/bin/uv","poetry":"/usr/local/bin/poetry","npm":"/usr/local/bin/npm","pnpm":"/usr/local/bin/pnpm","yarn":"/usr/local/bin/yarn","npx":"/usr/local/bin/npx"}'

ENTRYPOINT ["sss-demo-agent"]
