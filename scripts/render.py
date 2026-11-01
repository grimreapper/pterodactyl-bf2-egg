"""Deterministic PTDL_v2 renderer; embedded bytes come only from canonical sources."""
import argparse
import json
from pathlib import Path

from spec import INSTALL_IMAGE, RUNTIME_IMAGE, VARIABLES

ROOT = Path(__file__).resolve().parent.parent
EMBEDDED = ('spec.py', 'common.py', 'runtime.py', 'install.py', 'start.sh', 'install.sh')
EGG = 'egg-battlefield-2.json'


def installer():
    parts = ['#!/bin/bash\nset -euo pipefail\numask 077\n',
             'unset LD_PRELOAD LD_LIBRARY_PATH PYTHONPATH PYTHONHOME BASH_ENV ENV\n',
             'work=$(mktemp -d)\ntrap \'rm -rf -- "$work"\' EXIT\n']
    for name in EMBEDDED:
        data = (ROOT / 'scripts' / name).read_bytes()
        assert b'\r' not in data and data.endswith(b'\n')
        delimiter = 'BF2_SOURCE_' + name.replace('.', '_').upper()
        assert delimiter.encode() not in data.splitlines()
        parts.append(f'cat > "$work/{name}" <<\'{delimiter}\'\n' + data.decode() + delimiter + '\n')
    parts.append('/bin/bash "$work/install.sh"\n')
    return ''.join(parts)


def render():
    egg = {
        '_comment': 'Original-code local candidate. Build the supplied image on the node before import. No game files included.',
        'meta': {'version': 'PTDL_v2', 'update_url': None},
        'exported_at': '2026-11-01T00:00:00+00:00',
        'name': 'Battlefield 2 (2005)', 'author': 'community@example.invalid',
        'description': 'Native Linux v1.5 amd64, unranked. Exact operator archive and explicit EA/noncommercial acknowledgments required. BF2Hub patched clients required for BF2Hub discovery. Panel import, container runtime, public listing and client join remain unverified.',
        'features': [], 'docker_images': {'BF2 amd64 (build container/Dockerfile locally)': RUNTIME_IMAGE},
        'file_denylist': [], 'startup': '/bin/bash server/egg/start.sh',
        'config': {
            'files': json.dumps({}, separators=(',', ':')),
            'startup': json.dumps({'done': []}, separators=(',', ':')),
            'logs': json.dumps({}, separators=(',', ':')),
            'stop': '^C',
        },
        'scripts': {'installation': {'script': installer(), 'container': INSTALL_IMAGE, 'entrypoint': 'bash'}},
        'variables': [
            {'name': key.replace('_', ' ').title(), 'description': description, 'env_variable': key,
             'default_value': default, 'user_viewable': True, 'user_editable': True, 'rules': rules,
             'field_type': 'text'}
            for key, (default, rules, description) in VARIABLES.items()
        ],
    }
    return (json.dumps(egg, indent=2, ensure_ascii=True) + '\n').encode()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    target = ROOT / EGG
    if args.check:
        if not target.exists() or target.read_bytes() != render():
            raise SystemExit('Generated egg differs; run python3 -B scripts/render.py')
        print('Renderer byte equality: PASS')
    else:
        target.write_bytes(render())
