"""Original shared validation, authenticated I/O, and atomic filesystem helpers."""
import contextlib
import fcntl
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import resource
import stat
import subprocess
import tarfile
import tempfile
from urllib.parse import urlsplit

from spec import BUILTIN_DEFAULTS, DEFAULTS


class Refusal(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Refusal(message)


def value(env, key):
    if key in env:
        result = env[key]
    elif key in DEFAULTS:
        result = DEFAULTS[key]
    else:
        result = BUILTIN_DEFAULTS[key]
    require(isinstance(result, str) and all(32 <= ord(c) < 127 for c in result),
            key + ': only printable ASCII, no control characters')
    return result


def switch(env, key):
    result = value(env, key)
    require(result in ('0', '1'), key + ': expected 0 or 1')
    return result == '1'


def acknowledgments(env):
    for key in ('EA_EULA_ACCEPT', 'NONCOMMERCIAL_USE'):
        require(value(env, key) == 'YES', key + '=YES is required; read the EULA first')


def regular(path, executable=False):
    st = path.lstat()
    require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size > 0,
            'Expected nonempty regular file (no links): ' + path.name)
    if executable:
        require(st.st_mode & 0o111, 'Missing executable permission: ' + path.name)
    return st


def digest(path):
    regular(path)
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else hash_stream(f)


def hash_stream(f):
    h = hashlib.sha256()
    for chunk in iter(lambda: f.read(1024 * 1024), b''):
        h.update(chunk)
    return h.hexdigest()


def verify(path, size, sha):
    require(regular(path).st_size == size, 'Exact byte count mismatch: ' + path.name)
    require(digest(path) == sha, 'SHA-256 mismatch: ' + path.name)


def snapshot(source, dest, size, sha):
    """Verify the private copy that will actually be consumed, never reopen input."""
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as src:
        before = os.fstat(src.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == size,
                'Uploaded archive must be a regular file with the exact byte count')
        with dest.open('xb') as out:
            left = size
            while left:
                chunk = src.read(min(left, 1024 * 1024))
                require(chunk, 'Archive changed during copy')
                out.write(chunk)
                left -= len(chunk)
            require(not src.read(1), 'Archive grew during copy')
        after = os.fstat(src.fileno())
        require((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Archive changed during copy')
    verify(dest, size, sha)


def https_url(url):
    require(len(url) <= 2048 and all(33 <= ord(c) < 127 for c in url), 'Invalid HTTPS URL')
    parts = urlsplit(url)
    require(parts.scheme == 'https' and parts.hostname and not parts.username and
            not parts.password and not parts.fragment, 'Only HTTPS URLs without credentials/fragments are accepted')
    return url


def download(url, dest, size, sha, direct_hub=False):
    https_url(url)
    # No cookies, netrc, curlrc, proxy credentials, HTTP redirects, or verbose URLs in errors.
    cmd = ['curl', '--disable', '--fail', '--silent', '--show-error', '--proto', '=https',
           '--proto-redir', '=https', '--connect-timeout', '30', '--max-time', '900',
           '--max-filesize', str(size), '--output', str(dest), '--url', url]
    if not direct_hub:
        cmd[2:2] = ['--location', '--max-redirs', '5']
    # Enforce a kernel write cap even with unknown/chunked Content-Length and older curl.
    def cap_file_size():
        resource.setrlimit(resource.RLIMIT_FSIZE, (size, size))

    result = subprocess.run(cmd, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'},
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=930,
                            preexec_fn=cap_file_size)
    require(result.returncode == 0, 'HTTPS download failed; upload the exact archive and reinstall')
    verify(dest, size, sha)


def relative_name(name):
    require('\\' not in name and not name.startswith('/') and
            all(32 <= ord(c) < 127 for c in name), 'Unsafe archive path')
    while name.startswith('./'):
        name = name[2:]
    if name in ('', '.'):
        return ''
    path = PurePosixPath(name)
    require(all(p not in ('.', '..', '') for p in name.split('/')) and len(path.parts) <= 16 and
            len(name) <= 240, 'Unsafe archive path')
    return str(path)


def inspect_tar(tar, max_bytes=512 * 1024 * 1024, max_files=2048):
    names = set()
    total = 0
    items = []
    for member in tar:
        name = relative_name(member.name.rstrip('/'))
        require(member.isfile() or member.isdir(), 'Archive links and special files are forbidden')
        require(name.lower() not in names, 'Duplicate/case-colliding archive path')
        names.add(name.lower())
        total += member.size
        require(len(names) <= max_files and 0 <= member.size <= max_bytes and total <= max_bytes,
                'Archive exceeds extraction budget')
        items.append((member, name))
    return items


def extract_tar(path, dest, expected=None):
    with tarfile.open(path, 'r:gz') as tar:
        members = inspect_tar(tar)
        if expected is not None:
            require({n for m, n in members if m.isfile()} == set(expected), 'Unexpected archive file set')
        for member, name in members:
            if not name:
                continue
            target = dest / name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as src, target.open('xb') as out:
                    while chunk := src.read(1024 * 1024):
                        out.write(chunk)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)


def tree_check(root, lowercase=False):
    require(root.is_dir() and not root.is_symlink(), 'Expected real directory')
    count = 0
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            count += 1
            require(count < 100000, 'Tree exceeds entry budget')
            p = Path(base) / name
            st = p.lstat()
            require(stat.S_ISDIR(st.st_mode) or (stat.S_ISREG(st.st_mode) and st.st_nlink == 1),
                    'Tree contains link or special file')
            if lowercase and not (p.suffix == '.py' and name in files):
                require(name == name.lower(), 'Mod loose paths must be lowercase (except Python scripts)')


def atomic_write(path, content, mode=0o600):
    fd, temp = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


@contextlib.contextmanager
def locked(root):
    require(root.is_dir() and not root.is_symlink(), 'Volume must be a real directory')
    fd = os.open(root / '.bf2-egg.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o666)
    try:
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, 'Unsafe lock file')
        # Install containers run as root while game containers run as the Wings
        # UID. The lock contains no data and must remain openable by both; the
        # server-volume directory is the access boundary.
        if stat.S_IMODE(st.st_mode) != 0o666:
            os.fchmod(fd, 0o666)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise Refusal('Install/start already active; stop the server first') from e
        os.set_inheritable(fd, True)  # exec keeps the lock for the lifetime of the game.
        yield
    finally:
        os.close(fd)
