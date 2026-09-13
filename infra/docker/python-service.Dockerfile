# check=skip=InvalidDefaultArgInFrom
# Supply a Python 3.12 image pinned by digest for reproducible rehearsal builds.
ARG SSS_PYTHON_BASE_IMAGE
FROM ${SSS_PYTHON_BASE_IMAGE}

ARG SSS_SERVICE_UID=65532
ARG SSS_SERVICE_GID=65532
ARG SSS_UV_VERSION

WORKDIR /opt/sss

COPY pyproject.toml ./
COPY uv.lock ./
COPY apps ./apps
COPY packages ./packages
COPY demo ./demo
COPY infra/exasol ./infra/exasol

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PATH="/opt/sss/.venv/bin:${PATH}"

RUN python -m pip install --no-cache-dir "uv==${SSS_UV_VERSION}" \
    && uv sync --frozen --no-dev --no-editable \
    && mkdir -p /state \
    && chown ${SSS_SERVICE_UID}:${SSS_SERVICE_GID} /state

USER ${SSS_SERVICE_UID}:${SSS_SERVICE_GID}
