"""Rebuild the source-only egg, full checksum inventory and deterministic local ZIP."""
import hashlib
import io
import os
from pathlib import Path
import stat
import tempfile
import zipfile

from render import ROOT, EGG, render
from scan_public import candidate_files, scan, check_text, scan_git


def atomic_write(path, data):
    """Replace a generated file without ever opening its destination."""
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            os.fchmod(output.fileno(), 0o644)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def release_directory(path):
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        path.mkdir(mode=0o755)
        mode = path.lstat().st_mode
    if not stat.S_ISDIR(mode) or path.is_symlink():
        raise ValueError('dist must be a real directory')


def build():
    output = ROOT / 'dist'
    release_directory(output)
    atomic_write(ROOT / EGG, render())
    files = candidate_files()
    for name in files:
        check_text((ROOT / name).read_bytes(), name)
    # During a rebuild, generated egg/checksum bytes can legitimately be ahead of
    # the index. The release pass still scans every indexed blob; validate.sh runs
    # the strict staged/workspace equality gate after the candidate is staged.
    scan_git(files, exact_index=False)
    sums = ''.join(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() + '  ' + p + '\n'
                   for p in files if p != 'SHA256SUMS')
    atomic_write(ROOT / 'SHA256SUMS', sums.encode())
    archive = output / 'bf2-native-linux-egg.zip'
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in files:
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, (ROOT / name).read_bytes())
    data = archive_bytes.getvalue()
    atomic_write(archive, data)
    checksum = hashlib.sha256(data).hexdigest() + '  ' + archive.name + '\n'
    atomic_write(output / 'SHA256SUMS', checksum.encode())
    scan(exact_index=False)
    print('Release built and scanned: dist/bf2-native-linux-egg.zip')


if __name__ == '__main__':
    build()
