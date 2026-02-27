#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python -m venv .venv
source .venv/bin/activate
pip install -q -e .[dev]

vectrion --workdir .demo start INC-2026-0001 || true
for layer in A B C D E G H; do
  vectrion --workdir .demo proceed INC-2026-0001 --layer "$layer"
done

echo "--- STATUS ---"
vectrion --workdir .demo status INC-2026-0001

echo "--- VQL DEMO ---"
vectrion-vql "SELECT event_id,subject FROM evidence WHERE source='vpn' LIMIT 2"

echo "--- TESTS ---"
pytest -q
