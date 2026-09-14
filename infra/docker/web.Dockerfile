# check=skip=InvalidDefaultArgInFrom
ARG SSS_NODE_BASE_IMAGE
ARG SSS_GO_BASE_IMAGE
ARG SSS_ALPINE_BASE_IMAGE

FROM ${SSS_GO_BASE_IMAGE} AS caddy-build
WORKDIR /build
COPY infra/docker/caddy-build/go.mod infra/docker/caddy-build/go.sum ./
RUN go mod download
RUN CGO_ENABLED=0 go build -mod=readonly -trimpath -o /go/bin/caddy \
    github.com/caddyserver/caddy/v2/cmd/caddy

FROM ${SSS_NODE_BASE_IMAGE} AS build

WORKDIR /src
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN corepack enable && pnpm install --frozen-lockfile
COPY apps/web apps/web
RUN pnpm --filter @sss/web build

FROM ${SSS_ALPINE_BASE_IMAGE}
RUN apk upgrade --no-cache \
    && apk add --no-cache ca-certificates \
    && mkdir -p /config /data /srv \
    && chown -R 65532:65532 /config /data /srv
COPY --from=caddy-build /go/bin/caddy /usr/bin/caddy
COPY infra/docker/Caddyfile.web /etc/caddy/Caddyfile
COPY --from=build /src/apps/web/dist /srv
USER 65532:65532
ENTRYPOINT ["caddy"]
CMD ["run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
