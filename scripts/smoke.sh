#!/usr/bin/env bash
# Smoke test of the deployed service: real HTTP requests from inside the
# container, so it needs no network route from the CI agent.
#
#   EXPECT_REVISION=<sha> smoke.sh <container>
set -euo pipefail

docker exec -i -e EXPECT_REVISION="${EXPECT_REVISION:-}" "$1" python - <<'EOF'
import json, os, urllib.request

base = "http://127.0.0.1:8000"
health = json.load(urllib.request.urlopen(base + "/healthz", timeout=5))
print("healthz:", health)
assert health["status"] == "ok" and health["documents"] > 0
expected = os.environ.get("EXPECT_REVISION")
assert not expected or health["revision"] == expected, "old version still running"

req = urllib.request.Request(
    base + "/api/ask",
    data=json.dumps({"question": "How do I get VPN access?"}).encode(),
    headers={"Content-Type": "application/json"},
)
answer = json.load(urllib.request.urlopen(req, timeout=60))
print(f"ask ({answer['mode']}, {answer['latency_ms']} ms):", answer["answer"])
assert answer["sources"][0]["doc_id"] == "it-vpn-access"
print("smoke test passed")
EOF
