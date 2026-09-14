#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tls_dir="$repo_root/.runtime/tls"
mkdir -p "$tls_dir"
openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 2 \
  -keyout "$tls_dir/npm.demo.sss.test.key" \
  -out "$tls_dir/npm.demo.sss.test.crt" \
  -subj "/CN=npm.demo.sss.test" \
  -addext "subjectAltName=DNS:npm.demo.sss.test" >/dev/null 2>&1
# This ignored, two-day localhost demo key must be readable by rootless Docker's remapped UID.
chmod 0644 "$tls_dir/npm.demo.sss.test.key"
printf '%s\n' "$tls_dir/npm.demo.sss.test.crt"
