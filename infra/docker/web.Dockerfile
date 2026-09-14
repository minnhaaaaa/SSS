# check=skip=InvalidDefaultArgInFrom
ARG SSS_NODE_BASE_IMAGE
ARG SSS_CADDY_IMAGE
FROM ${SSS_NODE_BASE_IMAGE} AS build

WORKDIR /src
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN corepack enable && pnpm install --frozen-lockfile
COPY apps/web apps/web
RUN pnpm --filter @sss/web build

FROM ${SSS_CADDY_IMAGE}
RUN setcap -r /usr/bin/caddy
COPY infra/docker/Caddyfile.web /etc/caddy/Caddyfile
COPY --from=build /src/apps/web/dist /srv
USER 65532:65532
