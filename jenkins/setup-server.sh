#!/usr/bin/env bash
# One-time setup of the Jenkins controller on the test server. Run as root
# from a copy of this directory:
#   sudo bash setup-server.sh
# Safe to re-run: secrets are kept, the image is rebuilt and the container recreated.
set -euo pipefail

dir=/srv/jenkins
here=$(cd "$(dirname "$0")" && pwd)

install -d -m 750 "$dir" "$dir/secrets"
cp "$here"/{Dockerfile,plugins.txt,casc.yaml,compose.yml} "$dir/"

secrets=$dir/secrets
[ -s "$secrets/jenkins_admin_password" ] || openssl rand -base64 18 | tr -d '\n' > "$secrets/jenkins_admin_password"
[ -f "$secrets/llm_api_key" ] || printf 'none' > "$secrets/llm_api_key"
# uid 1000 is the jenkins user inside the container.
chown -R 1000:1000 "$secrets"
chmod 500 "$secrets"
chmod 400 "$secrets"/*

echo "DOCKER_GID=$(stat -c %g /var/run/docker.sock)" > "$dir/.env"

cd "$dir"
docker compose up -d --build
echo "jenkins: http://127.0.0.1:8090 (admin password in $secrets/jenkins_admin_password)"
