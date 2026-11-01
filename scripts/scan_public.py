"""Strict allowlisted release surface plus filesystem, Git metadata and blob checks."""
import argparse
import ipaddress
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_SUFFIXES = {'.py', '.sh', '.md', '.json', '.yml', '.yaml'}
SPECIAL = {'.gitignore', '.dockerignore', 'LICENSE', 'SHA256SUMS', 'Makefile', 'Dockerfile', 'PUBLIC_FILES'}
BINARY_SUFFIXES = {'.exe', '.dll', '.so', '.cab', '.tgz', '.gz', '.tar', '.zip', '.pyc', '.pyo', '.con', '.cfg', '.sav', '.db', '.log'}
PUBLIC_HOSTS = {'static.nihlen.net', 'www.bf2hub.com', 'www.bf-games.net', 'packages.debian.org',
                'snapshot.debian.org', 'github.com', 'raw.githubusercontent.com', 'hub.docker.com'}
ALLOWED_EMAILS = {'community@example.invalid', '10205216+grimreapper@users.noreply.github.com'}
ALLOWED_GIT_IDENTITIES = {
    'BF2 Egg Contributors <community@example.invalid>',
    'grimreapper <10205216+grimreapper@users.noreply.github.com>',
}


def check_text(data, label):
    try:
        text = data.decode('utf-8').replace(r'\n', '\n').replace(r'\r', '\n')
    except UnicodeDecodeError as e:
        raise ValueError(label + ': non-text content') from e
    if '\x00' in text:
        raise ValueError(label + ': binary content')
    patterns = [
        r'(?<![A-Za-z0-9.:])/(?:ho' + r'me|Users)/(?!(?:container)(?:[/\s\"\']|$))[^\s\"\']+',
        r'-----BEGIN [A-Z ]*PRIVATE KEY-----',
        r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})\b',
        r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',
        r'(?i)\b(?:legal-' + r'safe|lawful ' + r'egg|privacy-' + r'safe)\b',
    ]
    for pattern in patterns:
        if re.search(pattern, text):
            raise ValueError(label + ': private path, credential, identifier or disallowed branding')
    for addr in re.findall(r'(?<![\w.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![\w.])', text):
        try:
            ip = ipaddress.IPv4Address(addr)
        except ipaddress.AddressValueError:
            continue  # Version strings, such as the server build, are not addresses.
        if str(ip) != '0.0.0.0' and not any(ip in ipaddress.ip_network(n) for n in
                                           ('192.0.2.0/24', '198.51.100.0/24', '203.0.113.0/24')):
            raise ValueError(label + ': non-documentation IPv4 address')
    for email in re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', text):
        if email not in ALLOWED_EMAILS:
            raise ValueError(label + ': non-neutral email')
    for host in re.findall(r'https?://([^/\s\)\"\'<>]+)', text):
        if host not in PUBLIC_HOSTS:
            raise ValueError(label + ': unapproved URL host')


def candidate_files(root=ROOT):
    manifest = root / 'PUBLIC_FILES'
    files = manifest.read_text().splitlines()
    if files != sorted(set(files)) or 'PUBLIC_FILES' not in files:
        raise ValueError('PUBLIC_FILES must be sorted, unique, and include itself')
    actual = set()
    for p in root.rglob('*'):
        rel = p.relative_to(root)
        if rel.parts[0] == '.git':
            continue
        if p.is_symlink():
            raise ValueError('Public workspace contains symlink: ' + str(rel))
        if p.is_dir():
            if p.name in ('__pycache__', '.fixtures', '.private', '.pytest_cache'):
                raise ValueError('Private/generated directory in public workspace: ' + str(rel))
            continue
        if rel.parts[0] == 'dist':
            continue  # Scanned recursively as a separate release below.
        if p.suffix.lower() in BINARY_SUFFIXES or (p.suffix not in ALLOWED_SUFFIXES and p.name not in SPECIAL):
            raise ValueError('Forbidden/unexpected artifact: ' + str(rel))
        actual.add(str(rel))
    if actual != set(files):
        raise ValueError('PUBLIC_FILES does not exactly match candidate files: ' + repr(sorted(actual ^ set(files))))
    return files


def scan_zip(path, files):
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None or set(z.namelist()) != set(files) or len(z.namelist()) != len(files):
            raise ValueError('Release ZIP file set/integrity mismatch')
        for name in z.namelist():
            data = z.read(name)
            check_text(data, 'release/' + name)
            if data != (ROOT / name).read_bytes():
                raise ValueError('Release differs from source: ' + name)
            mode = z.getinfo(name).external_attr >> 16
            expected = 0o100755 if name.endswith('.sh') else 0o100644
            if mode != expected:
                raise ValueError('Release mode mismatch: ' + name)


def git_output(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True).stdout


def scan_index(files, exact=True):
    entries = {}
    for raw in git_output('ls-files', '--stage', '-z').split(b'\0'):
        if not raw:
            continue
        metadata, name_bytes = raw.split(b'\t', 1)
        mode, sha, stage = metadata.decode().split()
        name = name_bytes.decode('utf-8')
        check_text(name_bytes, 'Git index path')
        if mode not in ('100644', '100755') or stage != '0' or name in entries:
            raise ValueError('Unsafe staged mode/conflict/duplicate')
        if name.endswith('.sh') and mode != '100755':
            raise ValueError('Tracked shell file lacks executable bit')
        entries[name] = sha
    if exact and set(entries) != set(files):
        raise ValueError('Git index does not exactly match PUBLIC_FILES: ' +
                         repr(sorted(set(entries) ^ set(files))))
    for name, sha in entries.items():
        data = git_output('cat-file', 'blob', sha)
        check_text(data, 'Git index')
        if exact and data != (ROOT / name).read_bytes():
            raise ValueError('Git index differs from public workspace: ' + name)


def scan_annotated_tags():
    pending = git_output('for-each-ref', '--format=%(objectname)', 'refs/tags').decode().splitlines()
    seen = set()
    while pending:
        sha = pending.pop()
        if sha in seen:
            continue
        seen.add(sha)
        if git_output('cat-file', '-t', sha).strip() != b'tag':
            continue
        data = git_output('cat-file', 'tag', sha)
        check_text(data, 'Git tag object')
        header, separator, _message = data.partition(b'\n\n')
        if not separator:
            raise ValueError('Malformed annotated Git tag')
        objects = [line[7:].decode() for line in header.splitlines() if line.startswith(b'object ')]
        taggers = [line for line in header.splitlines() if line.startswith(b'tagger ')]
        if len(objects) != 1 or len(taggers) != 1:
            raise ValueError('Malformed annotated Git tag metadata')
        match = re.fullmatch(rb'tagger ([^<>\n]+ <[^<>\n]+>) [0-9]+ [+-][0-9]{4}', taggers[0])
        if match is None or match.group(1).decode() not in ALLOWED_GIT_IDENTITIES:
            raise ValueError('Git tag has non-neutral tagger metadata')
        pending.append(objects[0])  # Also inspect an annotated tag that tags another tag.


def scan_git(files, exact_index=True):
    refs = git_output('for-each-ref', '--format=%(refname)').decode()
    check_text(refs.encode(), 'Git refs')
    scan_annotated_tags()
    commits = git_output('rev-list', '--all').decode().splitlines()
    for commit in commits:
        identities = git_output('show', '-s', '--format=%an <%ae>%n%cn <%ce>', commit).decode().splitlines()
        if any(x not in ALLOWED_GIT_IDENTITIES for x in identities):
            raise ValueError('Git history has non-neutral author/committer metadata')
        check_text(git_output('show', '-s', '--format=%B', commit), 'Git message')
    # Include every reachable blob, even if removed from the current candidate.
    for line in git_output('rev-list', '--objects', '--all').decode().splitlines():
        sha, _, name = line.partition(' ')
        if git_output('cat-file', '-t', sha).strip() == b'blob':
            if Path(name).suffix.lower() in BINARY_SUFFIXES:
                raise ValueError('Forbidden historical blob')
            check_text(git_output('cat-file', 'blob', sha), 'Git blob')
    scan_index(files, exact=exact_index)


def scan(exact_index=True):
    files = candidate_files()
    for name in files:
        check_text((ROOT / name).read_bytes(), name)
        if name.endswith('.sh') and not (ROOT / name).stat().st_mode & 0o111:
            raise ValueError('Shell source lacks executable bit')
    scan_git(files, exact_index=exact_index)
    dist = ROOT / 'dist'
    if dist.exists():
        for path in dist.iterdir():
            if path.name == 'bf2-native-linux-egg.zip':
                scan_zip(path, files)
            elif path.name == 'SHA256SUMS':
                check_text(path.read_bytes(), 'dist/SHA256SUMS')
            else:
                raise ValueError('Unexpected release artifact')
    qualifier = 'exact index' if exact_index else 'index safety'
    print(f'Public scan: PASS ({len(files)} files; workspace, {qualifier}, reachable history, release)')
    return files


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    scan()
