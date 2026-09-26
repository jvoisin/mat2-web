#!/bin/sh

set -eu

image_name="mat-web:seccomp-smoke"
network_name="mat-web-seccomp-$$"
container_name="mat-web-seccomp-$$"
test_workspace="$(mktemp -d)"
mat2_test_ref="${MAT2_TEST_REF:-0.15.0}"

cleanup() {
    status=$?
    if [ "$status" -ne 0 ]; then
        podman logs "$container_name" >&2 || true
    fi
    podman rm --force "$container_name" >/dev/null 2>&1 || true
    podman network rm "$network_name" >/dev/null 2>&1 || true
    rm -rf "$test_workspace"
    trap - EXIT
    exit "$status"
}

trap cleanup EXIT INT TERM

chmod a+rwx "$test_workspace"
podman run --rm --volume "$test_workspace:/work:Z" docker.io/curlimages/curl:8.12.1 \
    --fail --location \
    --output /work/mat2.tar.gz \
    "https://github.com/jvoisin/mat2/archive/${mat2_test_ref}.tar.gz"
podman run --rm --user 0 --volume "$test_workspace:/work:Z" docker.io/library/alpine:3.22 \
    sh -c 'tar -xzf /work/mat2.tar.gz -C /work && chmod -R a+rwX /work/mat2-*'
mat2_source_dir="$(find "$test_workspace" -mindepth 1 -maxdepth 1 -type d | head -n 1)"

podman build --tag "$image_name" --file Dockerfile.production .
python_version="$(podman run --rm --entrypoint python3 "$image_name" --version 2>&1 | sed -n 's/^Python \([0-9]*\.[0-9]*\).*/\1/p')"
if [ -z "$python_version" ]; then
    echo "Unable to determine Python version from the production image" >&2
    exit 1
fi
python_image="docker.io/library/python:${python_version}-alpine"

podman network create "$network_name" >/dev/null
podman run --detach --name "$container_name" \
    --entrypoint sh \
    --network "$network_name" \
    --network-alias matweb \
    --read-only \
    --tmpfs=/tmp \
    --tmpfs=/run/uwsgi \
    --tmpfs=/app/upload \
    --security-opt=no-new-privileges \
    --security-opt=seccomp="$PWD/config/seccomp.json" \
    "$image_name" -c 'nginx; uwsgi --ini /etc/uwsgi/apps-enabled/mat2-web.ini;' >/dev/null

podman run --rm --network "$network_name" docker.io/curlimages/curl:8.12.1 \
    --fail --retry 30 --retry-all-errors --retry-connrefused --retry-delay 1 \
    http://matweb:8080/api/extension >/dev/null

podman run --rm \
    --network "$network_name" \
    --volume "$mat2_source_dir/tests/data:/fixtures:ro,Z" \
    --volume "$PWD/test/test_upstream_fixtures_api.py:/test.py:ro,Z" \
    "$python_image" \
    python /test.py http://matweb:8080/api/upload /fixtures

response="$(printf '%s' '{"file_name":"test_name.gif","file":"R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="}' | podman run --rm --interactive --network "$network_name" docker.io/curlimages/curl:8.12.1 --fail-with-body --header 'Content-Type: application/json' --data-binary @- http://matweb:8080/api/upload)"

printf '%s' "$response" | grep -Eq '"output_filename"[[:space:]]*:[[:space:]]*"test_name\.cleaned\.gif"'