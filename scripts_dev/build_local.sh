#!/usr/bin/env bash
# Build the submission image inside this proxied dev environment.
# Generates a patched Dockerfile that (a) pulls the identical official base
# through mirror.gcr.io and (b) trusts the local egress-proxy CA during build.
# The shipped Dockerfile stays canonical for 8090's unrestricted builder.
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p dev
cp /root/.ccr/ca-bundle.crt dev/proxy-ca.crt

python3 - << 'PYEOF'
src = open("Dockerfile").read()
src = src.replace("ARG BASE_IMAGE=ubuntu:24.04",
                  "ARG BASE_IMAGE=mirror.gcr.io/library/ubuntu:24.04")
# Trust the dev proxy CA for apt(https)/pip during build only.
src = src.replace(
    "RUN apt-get update",
    "COPY dev/proxy-ca.crt /usr/local/share/ca-certificates/proxy-ca.crt\n"
    "ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt \\\n"
    "    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt\n"
    "RUN apt-get update")
src = src.replace(
    "&& rm -rf /var/lib/apt/lists/*",
    "&& update-ca-certificates && rm -rf /var/lib/apt/lists/*")
open("dev/Dockerfile.local", "w").write(src)
PYEOF
docker build -f dev/Dockerfile.local -t mib-submission "$@" .
