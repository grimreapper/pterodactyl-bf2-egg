#!/bin/bash
set -euo pipefail
cd "$(dirname -- "$(readlink -f -- "$0")")/.."
export PYTHONDONTWRITEBYTECODE=1
python3 -B scripts/render.py --check
# External bound prevents lifecycle regressions from hanging CI indefinitely.
timeout 120 python3 -B -m unittest discover -s tests -v
python3 -B -m json.tool egg-battlefield-2.json >/dev/null
sha256sum --check SHA256SUMS
python3 -B scripts/scan_public.py
git diff --check
python3 -B - <<'PY'
import hashlib, subprocess
from pathlib import Path
path = Path('dist/bf2-native-linux-egg.zip')
subprocess.run(['python3', '-B', 'scripts/build_release.py'], check=True)
first = hashlib.sha256(path.read_bytes()).hexdigest()
subprocess.run(['python3', '-B', 'scripts/build_release.py'], check=True)
assert hashlib.sha256(path.read_bytes()).hexdigest() == first
print('Deterministic release rebuild: PASS')
PY
(cd dist && sha256sum --check SHA256SUMS)
