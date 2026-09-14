# check=skip=InvalidDefaultArgInFrom
ARG SSS_GO_BASE_IMAGE
ARG SSS_ALPINE_BASE_IMAGE

FROM ${SSS_GO_BASE_IMAGE} AS caddy-build
WORKDIR /build
COPY infra/docker/caddy-build/go.mod infra/docker/caddy-build/go.sum ./
RUN go mod download
RUN CGO_ENABLED=0 go build -mod=readonly -trimpath -o /go/bin/caddy \
    github.com/caddyserver/caddy/v2/cmd/caddy

FROM ${SSS_ALPINE_BASE_IMAGE}
RUN apk upgrade --no-cache \
    && apk add --no-cache ca-certificates \
    && mkdir -p /config /data \
    && chown -R 65532:65532 /config /data
COPY --from=caddy-build /go/bin/caddy /usr/bin/caddy
COPY infra/docker/Caddyfile.production /etc/caddy/Caddyfile
USER 65532:65532
ENTRYPOINT ["caddy"]
CMD ["run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
