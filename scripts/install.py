"""Exact-hash archive installation; never run license.sh or modify a live installation."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from common import (Refusal, acknowledgments, digest, download, extract_tar, inspect_tar,
                    locked, regular, require, snapshot, switch, tree_check, value)
from runtime import settings, verify_install
from spec import (ARCHIVE, ARCHIVE_SIZE, ARCHIVE_SHA256, INNER, INNER_SIZE, PAYLOAD_OFFSET,
                  MIRROR, HUB_ARCHIVE, HUB_URL, HUB_SIZE, HUB_SHA256, HUB_HASHES)


def acquire(root, stage, env, hub=False):
    name, size, sha = (HUB_ARCHIVE, HUB_SIZE, HUB_SHA256) if hub else (ARCHIVE, ARCHIVE_SIZE, ARCHIVE_SHA256)
    source = root / name
    dest = stage / name
    if source.exists() or source.is_symlink():
        snapshot(source, dest, size, sha)
        return dest
    if hub:
        download(HUB_URL, dest, size, sha, direct_hub=True)
    else:
        url = value(env, 'ARCHIVE_URL')
        if not url:
            require(switch(env, 'ALLOW_THIRD_PARTY_MIRROR'),
                    'Upload ' + ARCHIVE + ' to the volume root, set ARCHIVE_URL, or explicitly enable the third-party mirror')
            print('Using optional THIRD-PARTY community HTTPS mirror; not an EA origin.', flush=True)
            url = MIRROR
        download(url, dest, size, sha)
    return dest


def unpack(archive, stage):
    outer = stage / 'outer'
    outer.mkdir()
    extract_tar(archive, outer, expected={INNER})
    script = outer / INNER
    require(regular(script).st_size == INNER_SIZE, 'Unexpected makeself installer size')
    # Inspect authenticated embedded tar BEFORE the legacy extractor sees it.
    with script.open('rb') as f:
        for _ in range(375):
            f.readline()
        require(f.tell() == PAYLOAD_OFFSET, 'Unexpected makeself header boundary')
        with tarfile.open(fileobj=f, mode='r|gz') as tar:
            inspect_tar(tar)
    payload = stage / 'payload'
    subprocess.run(['/bin/sh', str(script), '--noexec', '--nox11', '--nochown', '--target', str(payload)],
                   cwd=outer, env={'PATH': '/usr/bin:/bin', 'LANG': 'C', 'TMPDIR': str(stage)},
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                   timeout=300, check=True)
    tree_check(payload)
    return payload


def install(root, env):
    acknowledgments(env)  # Before any filesystem changes or network calls.
    hub = switch(env, 'BF2HUB_ENABLED')
    switch(env, 'ALLOW_THIRD_PARTY_MIRROR')
    require(not hub or switch(env, 'INTERNET'), 'BF2Hub requires INTERNET=1')
    with locked(root):
        destination = root / 'server'
        if destination.exists() or destination.is_symlink():
            verify_install(destination, hub)
            settings(destination, env)
            print('Existing installation verified; preserved without changes. See reinstall documentation.')
            return
        require(shutil.disk_usage(root).free >= 2 * 1024**3, 'At least 2 GiB free staging space is required')
        with tempfile.TemporaryDirectory(prefix='.bf2-install-', dir=root) as tmp:
            stage = Path(tmp)
            archive = acquire(root, stage, env)
            payload = unpack(archive, stage)
            for name in ('pb_amd-64', 'pb_ia-32', 'bin/ia-32'):
                path = payload / name
                if path.exists():
                    shutil.rmtree(path)
            # Keep EULA/readmes; never run or ship an acceptance wrapper as a startup path.
            (payload / 'license.sh').unlink()
            (payload / 'pb').mkdir()
            shutil.copyfile(payload / 'start.sh', payload / 'start_original.sh')
            (payload / 'start_original.sh').chmod(0o755)
            if hub:
                hubarchive = acquire(root, stage, env, hub=True)
                overlay = stage / 'hub'
                overlay.mkdir()
                extract_tar(hubarchive, overlay, expected=HUB_HASHES)
                for name, sha in HUB_HASHES.items():
                    require(digest(overlay / name) == sha, 'BF2Hub per-file hash mismatch')
                    if '/ia-32/' not in name:
                        target = payload / name
                        require(not target.exists(), 'BF2Hub overlay would overwrite a file')
                        shutil.copyfile(overlay / name, target)
                        target.chmod(0o755 if name.endswith(('.sh', '.so')) else 0o644)
            code = payload / 'egg'
            code.mkdir()
            for name in ('common.py', 'spec.py', 'runtime.py', 'start.sh'):
                shutil.copyfile(Path(__file__).parent / name, code / name)
                (code / name).chmod(0o755 if name.endswith('.sh') else 0o644)
            verify_install(payload, hub)
            settings(payload, env)  # Validate all operator config before committing anything.
            require(not destination.exists() and not destination.is_symlink(), 'Destination appeared during installation')
            os.rename(payload, destination)  # Same filesystem, whole server published atomically.
        print('BF2 installation complete. EULA/readmes retained in server/readmes. Runtime acceptance still required.')


if __name__ == '__main__':
    try:
        install(Path(os.environ.get('BF2_ROOT', '/mnt/server')), os.environ)
    except (Refusal, OSError, ValueError, tarfile.TarError, ET.ParseError, zipfile.BadZipFile, subprocess.SubprocessError) as e:
        print('BF2 install refused: ' + str(e), file=sys.stderr)
        sys.exit(1)
