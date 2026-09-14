# check=skip=InvalidDefaultArgInFrom
ARG SSS_CADDY_IMAGE
FROM ${SSS_CADDY_IMAGE}
RUN setcap -r /usr/bin/caddy
COPY infra/docker/Caddyfile.production /etc/caddy/Caddyfile
USER 65532:65532
