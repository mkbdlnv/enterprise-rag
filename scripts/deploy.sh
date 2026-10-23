#!/usr/bin/env bash
# Continuous delivery to the test server: replace the running container with a
# new image, wait for its Docker health check, roll back if it never gets healthy.
#
#   deploy.sh <image:tag> <host-port>     (NAME=rag by default)
#
# LLM_API_KEY / LLM_MODEL are passed through from the caller's environment
# (Jenkins injects the key from its credential store), never on the command line.
set -euo pipefail

image=$1
port=$2
name=${NAME:-rag}

# "none" is the placeholder credential of a Jenkins without a key: answer extractively.
if [ "${LLM_API_KEY:-}" = none ]; then unset LLM_API_KEY; fi

prev=$(docker inspect -f '{{.Config.Image}}' "$name" 2>/dev/null || true)

run() {
    docker run -d --name "$name" --restart unless-stopped \
        -p "127.0.0.1:$port:8000" \
        --memory 256m --cpus 0.5 \
        -e LLM_API_KEY -e LLM_MODEL -e LLM_BASE_URL \
        "$1" >/dev/null
}

wait_healthy() {
    for _ in $(seq 1 30); do
        status=$(docker inspect -f '{{.State.Health.Status}}' "$name" 2>/dev/null || echo missing)
        case $status in
            healthy) return 0 ;;
            unhealthy | missing) return 1 ;;
        esac
        sleep 2
    done
    return 1
}

echo "deploying $image (running now: ${prev:-nothing})"
docker rm -f "$name" >/dev/null 2>&1 || true
run "$image"

if wait_healthy; then
    echo "healthy: $image on 127.0.0.1:$port"
    # Keep the new and the previous image for rollback; drop older builds.
    repo=${image%%:*}
    docker image ls "$repo" --format '{{.Repository}}:{{.Tag}}' | while read -r ref; do
        case $ref in
            "$image" | "$prev" | *:latest | *:test-*) ;;
            *) docker rmi "$ref" >/dev/null 2>&1 || true ;;
        esac
    done
    exit 0
fi

echo "new version did not become healthy; last logs:" >&2
docker logs --tail 50 "$name" >&2 || true
docker rm -f "$name" >/dev/null 2>&1 || true
if [ -n "$prev" ]; then
    run "$prev"
    wait_healthy && echo "rolled back to $prev" >&2
fi
exit 1
