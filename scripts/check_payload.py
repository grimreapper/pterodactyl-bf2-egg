"""Optional private evidence check: no download, EULA execution/acceptance or game launch."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from common import digest, extract_tar, require, snapshot, verify
from install import unpack
from runtime import map_support, verify_install
from spec import ARCHIVE_SIZE, ARCHIVE_SHA256, HUB_SIZE, HUB_SHA256, HUB_HASHES


def check(archive, hub=None):
    # Keep all temporary proprietary bytes outside the repository and delete on exit.
    with tempfile.TemporaryDirectory(prefix='bf2-private-check-') as tmp:
        stage = Path(tmp)
        copy = stage / 'archive.tgz'
        snapshot(archive, copy, ARCHIVE_SIZE, ARCHIVE_SHA256)
        payload = unpack(copy, stage)
        require((payload / 'license.sh').exists(), 'Expected license wrapper missing')
        for name in ('pb_amd-64', 'pb_ia-32', 'bin/ia-32'):
            shutil.rmtree(payload / name)
        (payload / 'pb').mkdir()
        shutil.copyfile(payload / 'start.sh', payload / 'start_original.sh')
        (payload / 'start_original.sh').chmod(0o755)
        verify_install(payload)
        expected = json.loads((Path(__file__).resolve().parent.parent / 'data/vanilla-maps.json').read_text())
        actual = {p.name: [list(x) for x in sorted(map_support(p))]
                  for p in sorted((payload / 'mods/bf2/levels').iterdir())}
        require(actual == expected, 'Reviewed map manifest differs from exact payload')
        print(f'PASS: exact archive, safe --noexec extraction, original hashes, {len(actual)} map metadata intersections')
        with copy.open('r+b') as f:
            byte = f.read(1)
            f.seek(0)
            f.write(bytes([byte[0] ^ 1]))
        try:
            verify(copy, ARCHIVE_SIZE, ARCHIVE_SHA256)
        except ValueError:
            print('PASS: one-byte corruption rejected by exact SHA-256 gate')
        else:
            raise RuntimeError('Corruption gate failed')
        if hub:
            h = stage / 'hub.tar.gz'
            snapshot(hub, h, HUB_SIZE, HUB_SHA256)
            dest = stage / 'hub'
            dest.mkdir()
            extract_tar(h, dest, expected=HUB_HASHES)
            for name, sha in HUB_HASHES.items():
                require(digest(dest / name) == sha, 'BF2Hub per-file pin mismatch')
            print('PASS: exact BF2Hub R3 archive and all four per-file hashes (no execution)')
    print('Private extraction temporary files removed. No EULA accepted, game launched, or network download performed.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=Path)
    p.add_argument('--hub', type=Path)
    args = p.parse_args()
    check(args.archive, args.hub)
