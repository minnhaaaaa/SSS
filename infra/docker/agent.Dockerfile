# check=skip=InvalidDefaultArgInFrom
# The final rehearsal must supply a digest-pinned Linux image containing the chosen agent runtime.
ARG SSS_AGENT_BASE_IMAGE
FROM ${SSS_AGENT_BASE_IMAGE}

ARG SSS_AGENT_UID=65532
ARG SSS_AGENT_GID=65532

WORKDIR /workspace

USER ${SSS_AGENT_UID}:${SSS_AGENT_GID}
