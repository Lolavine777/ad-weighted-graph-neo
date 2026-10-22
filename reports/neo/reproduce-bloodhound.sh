#!/bin/sh
# Run from the repository root. Choose a new tag and six unused loopback ports.
set -eu
# Bind URLs/auth to this pinned compose, ignoring settings for another local stack.
unset BLOODHOUND_URL NEO4J_URL NEO4J_USER NEO4J_SECRET
: "${BH_RUN_TAG:?Set BH_RUN_TAG to a new unique experiment tag}"
run="reports/generated/bh-live-$BH_RUN_TAG"
compose="deploy/bloodhound/compose.seamless.yml"
seamless_project="neo-bh-seamless-$BH_RUN_TAG"
wraith_project="neo-bh-wraith-$BH_RUN_TAG"
test ! -e "$run"
for project in "$seamless_project" "$wraith_project"; do
  test -z "$(docker ps -aq --filter "label=com.docker.compose.project=$project")"
  test -z "$(docker volume ls -q --filter "label=com.docker.compose.project=$project")"
done
# Bind checks fail before any dataset import or container creation.
.venv/bin/python - <<'PY'
import socket
for port in (28080, 27474, 27687, 38080, 37474, 37687):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))
PY
.venv/bin/python -m scripts.neo_import --raw-dir data/raw/SEAMLESS \
  --manifest data/samples/manifests/seamless-raw-v1.json \
  --time-policy tests/fixtures/ranking/seamless_time_policy.json \
  --output-dir "$run/inputs/seamless"
.venv/bin/python -m scripts.neo_import --raw-dir data/raw/ad_sampledata \
  --manifest data/samples/manifests/ad-sampledata-v1.json \
  --time-policy data/samples/time-policies/ad-sampledata-v1.json \
  --export-prefix 20240305111414 --output-dir "$run/inputs/wraith"
.venv/bin/python -m scripts.convert_seamless_ce --output "$run/inputs/seamless-ce"
.venv/bin/python -m scripts.neo_bloodhound \
  --seamless-snapshot "$run/inputs/seamless/snapshot.json" \
  --wraith-snapshot "$run/inputs/wraith/snapshot.json" --output-dir "$run/native"
.venv/bin/python - "$run/native/comparison.json" <<'PY'
import json
import sys
from pathlib import Path
fixed = json.loads(Path("reports/neo/bloodhound-query-pack.json").read_text())
fresh = json.loads(Path(sys.argv[1]).read_text())
for name, dataset in fresh["datasets"].items():
    for key in ("pairs", "request", "scenario_policy", "techniques"):
        assert dataset[key] == fixed["datasets"][name][key], (name, key)
PY
sh "$run/native/neo-commands.sh" > "$run/native-run.log" 2>&1
export BLOODHOUND_PORT=28080 NEO4J_WEB_PORT=27474 NEO4J_BOLT_PORT=27687
.venv/bin/python -m scripts.run_bloodhound_baseline --snapshot seamless \
  --compose-file "$compose" --project-name "$seamless_project" \
  --seamless-ce-dir "$run/inputs/seamless-ce" --output "$run/seamless-ingest.json"
.venv/bin/python -m scripts.neo_bloodhound_live --dataset seamless \
  --project-name "$seamless_project" --pack "$run/native/comparison.json" \
  --snapshot "$run/inputs/seamless/snapshot.json" --output-dir "$run/live-seamless"
export BLOODHOUND_PORT=38080 NEO4J_WEB_PORT=37474 NEO4J_BOLT_PORT=37687
.venv/bin/python -m scripts.run_bloodhound_baseline --snapshot wraith \
  --compose-file "$compose" --project-name "$wraith_project" --output "$run/wraith-ingest.json"
.venv/bin/python -m scripts.neo_bloodhound_live --dataset wraith \
  --project-name "$wraith_project" --pack "$run/native/comparison.json" \
  --snapshot "$run/inputs/wraith/snapshot.json" --output-dir "$run/live-wraith"
.venv/bin/python -m scripts.neo_bloodhound_live --dataset wraith --remediation \
  --project-name "$wraith_project" --pack "$run/native/comparison.json" \
  --snapshot "$run/inputs/wraith/snapshot.json" --output-dir "$run/live-remediation"
