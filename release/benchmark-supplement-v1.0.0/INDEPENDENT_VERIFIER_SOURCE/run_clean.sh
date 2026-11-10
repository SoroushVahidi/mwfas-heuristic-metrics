#!/bin/bash
set -euo pipefail
# Run from a new, empty directory. Argument is the supplied audit bundle.
BUNDLE=$(realpath "$1")
ROOT=$(pwd -P)
if [ -n "$(ls -A .)" ]; then echo 'Destination must be empty' >&2; exit 1; fi
mkdir home
cp -R "$BUNDLE/INDEPENDENT_VERIFIER_SOURCE" source
cp -R "$BUNDLE/supplied_manifests" supplied_manifests
exec env -i PATH=/usr/bin:/bin HOME="$ROOT/home" /bin/bash -c '
set -euo pipefail
/usr/bin/python3 -m venv venv
venv/bin/python -I -B source/download.py > download.log 2>&1
venv/bin/python -I -B source/verify_release.py > verification.log 2>&1
venv/bin/python -I -B source/run_guarded.py source/test_verifier.py > VERIFIER_TEST_RESULTS.txt 2>&1
venv/bin/python -I -B source/run_guarded.py source/usage_example.py table45 > BENCHMARK_USAGE_RESULT.json
venv/bin/python -I -B source/run_guarded.py mwfas-heuristic-metrics-d5fb6c885a6ae55b3d4d9c8acec98442f535a8b8/release/public_reproducibility/replay_table45.py table45 public_replay > public_replay.log 2>&1
venv/bin/python -I -B -c "import json; from pathlib import Path; assert json.loads(Path(\"SUMMARY.json\").read_text())[\"status\"] == \"PASS\"; print(\"COMPLETED_SUCCESS\")"
'
