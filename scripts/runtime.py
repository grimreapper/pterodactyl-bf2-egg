"""Validate the installed server, generate isolated configuration, then exec its launcher."""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from common import (Refusal, acknowledgments, atomic_write, digest, locked, regular,
                    relative_name, require, switch, tree_check, value)
from spec import BASE_HASHES, HUB_HASHES


def integer(env, key, low, high):
    text = value(env, key)
    require(re.fullmatch(r'0|[1-9][0-9]{0,5}', text), key + ': expected decimal integer')
    number = int(text)
    require(low <= number <= high, key + ': outside supported range')
    return number


def token(text):
    require(re.fullmatch(r'[a-z0-9][a-z0-9_]{0,47}', text), 'Expected lowercase map/mod token')
    return text


def quoted(text):
    # The legacy console's escape grammar is not established. Refuse ambiguous input.
    require('"' not in text and '\\' not in text and all(32 <= ord(c) < 127 for c in text),
            'Quotes, backslashes and control characters are not supported')
    return '"' + text + '"'


def secret(text, rcon=False):
    if not text and not rcon:
        return text
    require((16 if rcon else 12) <= len(text) <= 64, 'Secret length outside supported range')
    folded = re.sub(r'[^a-z0-9]', '', text.lower())
    require(not any(x in folded for x in ('password', 'changeme', 'changeit', 'replace', 'example',
                                         'placeholder', 'default', 'secret', 'letmein', 'qwerty',
                                         'admin', '123456', 'yourrcon')) and len(set(text)) >= 6,
            'Refusing placeholder/weak secret')
    quoted(text)
    if rcon:
        require(re.fullmatch(r'[A-Za-z0-9._!@%+:\-]+', text), 'RCON secret contains unsupported characters')
    return text


def map_support(level):
    """Intersect advertised map types with actual gameplay data, without extracting ZIPs."""
    require(level.is_dir() and not level.is_symlink(), 'Map directory missing or unsafe')
    info = level / 'info'
    require(info.is_dir() and not info.is_symlink(), 'Map info directory missing or unsafe')
    desc = info / (level.name + '.desc')
    require(regular(desc).st_size <= 256 * 1024, 'Map metadata too large')
    data = desc.read_bytes()
    require(b'<!DOCTYPE' not in data.upper() and b'<!ENTITY' not in data.upper(), 'XML entities forbidden')
    doc = ET.fromstring(data)
    require(doc.tag == 'map', 'Unexpected map metadata root')
    declared = set()
    for mode in doc.findall('./modes/mode'):
        kind = mode.get('type')
        if kind not in ('gpm_cq', 'gpm_coop'):
            continue
        for size in mode.findall('maptype'):
            n = size.get('players')
            if n in ('16', '32', '64'):
                pair = (kind, int(n))
                require(pair not in declared, 'Duplicate map metadata combination')
                declared.add(pair)
    archive = level / 'server.zip'
    require(regular(archive).st_size <= 512 * 1024 * 1024, 'Map archive too large')
    with zipfile.ZipFile(archive) as z:
        require(len(z.infolist()) <= 50000, 'Map ZIP exceeds entry budget')
        seen = set()
        actual = set()
        for entry in z.infolist():
            name = relative_name(entry.filename.rstrip('/')).lower()
            require(name not in seen, 'Duplicate/case-colliding map ZIP entry')
            seen.add(name)
            require(not entry.flag_bits & 1 and (entry.external_attr >> 16) & 0o170000 != 0o120000,
                    'Encrypted entries and links are forbidden in map ZIP')
            m = re.fullmatch(r'gamemodes/(gpm_cq|gpm_coop)/(16|32|64)/gameplayobjects\.con', name)
            if m and entry.file_size > 0:
                actual.add((m[1], int(m[2])))
    return declared & actual


def settings(root, env):
    acknowledgments(env)
    name = value(env, 'SERVER_NAME')
    require(1 <= len(name) <= 64, 'SERVER_NAME must have 1–64 characters')
    password = secret(value(env, 'SERVER_PASSWORD'))
    mod = token(value(env, 'MOD'))
    mods = root / 'mods'
    require(mods.is_dir() and not mods.is_symlink(), 'Unsafe mods directory')
    modroot = mods / mod
    tree_check(modroot, lowercase=True)
    require((modroot / 'init.con').is_file(), 'Incomplete mod: init.con missing')
    players = integer(env, 'MAX_PLAYERS', 1, 64)
    minimum = integer(env, 'MIN_PLAYERS', 1, 64)
    bots = integer(env, 'BOT_COUNT', 0, 64)
    require(minimum <= players and bots <= players, 'Minimum players/bot count exceeds MAX_PLAYERS')
    internet = switch(env, 'INTERNET')
    hub = switch(env, 'BF2HUB_ENABLED')
    require(not hub or internet, 'BF2Hub requires INTERNET=1')
    rcon = switch(env, 'RCON_ENABLED')
    rpassword = value(env, 'RCON_PASSWORD')
    if rcon or rpassword:
        secret(rpassword, rcon=True)
    voip = switch(env, 'VOIP_ENABLED')
    ports = {k: integer(env, k, 1024, 65535) for k in
             ('SERVER_PORT', 'QUERY_PORT', 'RCON_PORT', 'VOIP_CLIENT_PORT', 'VOIP_BF_PORT', 'VOIP_SERVER_PORT')}
    active = [ports['SERVER_PORT'], ports['QUERY_PORT']]
    if rcon:
        active.append(ports['RCON_PORT'])
    if voip:
        active.extend(ports[k] for k in ('VOIP_CLIENT_PORT', 'VOIP_BF_PORT', 'VOIP_SERVER_PORT'))
    require(len(set(active)) == len(active), 'Active ports must be distinct')
    bind = str(ipaddress.IPv4Address(value(env, 'SERVER_BIND_IP')))
    rotation = value(env, 'MAP_ROTATION')
    require(0 < len(rotation) <= 4096, 'MAP_ROTATION must be nonempty, at most 4096 characters')
    lines = []
    modes = set()
    cache = {}
    for item in rotation.split(';'):
        fields = item.split()
        require(len(fields) == 3, 'Rotation entries must be: map mode size')
        level, mode, size = fields
        token(level)
        require(mode in ('gpm_cq', 'gpm_coop') and size in ('16', '32', '64'), 'Unsupported mode or size')
        if level not in cache:
            cache[level] = map_support(modroot / 'levels' / level)
        require((mode, int(size)) in cache[level], 'Map/mode/size lacks matching metadata and gameplay data')
        lines.append(f'mapList.append {level} {mode} {size}')
        modes.add(mode)
    require(not bots or 'gpm_coop' in modes, 'Bots require at least one gpm_coop map')
    entries = {
        'serverName': quoted(name), 'password': quoted(password), 'internet': int(internet),
        'serverIP': quoted(bind), 'serverPort': ports['SERVER_PORT'], 'gameSpyPort': ports['QUERY_PORT'],
        'maxPlayers': players, 'numPlayersNeededToStart': minimum,
        'roundsPerMap': integer(env, 'ROUNDS_PER_MAP', 1, 99),
        'ticketRatio': integer(env, 'TICKET_RATIO', 1, 1000), 'timeLimit': integer(env, 'TIME_LIMIT', 0, 1440),
        'coopBotCount': bots, 'coopBotRatio': integer(env, 'BOT_RATIO', 0, 100),
        'coopBotDifficulty': integer(env, 'BOT_DIFFICULTY', 10, 100),
        'punkBuster': 0, 'useGlobalRank': 0, 'useGlobalUnlocks': 0, 'allowNATNegotiation': 0,
        'voipEnabled': int(voip), 'voipServerRemote': 0,
        'voipBFClientPort': ports['VOIP_CLIENT_PORT'], 'voipBFServerPort': ports['VOIP_BF_PORT'],
        'voipServerPort': ports['VOIP_SERVER_PORT'], 'adminScript': quoted('default' if rcon else ''),
    }
    return {
        'serversettings.con': ''.join(f'sv.{k} {v}\n' for k, v in entries.items()).encode(),
        'maplist.con': ('\n'.join(lines) + '\n').encode(),
        'default.cfg': (f'port={ports["RCON_PORT"]}\npassword={rpassword if rcon else ""}\n').encode(),
    }, mod, hub


def verify_install(root, hub=False):
    require(root.is_dir() and not root.is_symlink(), 'Installed server directory missing/unsafe')
    for dirname in ('bin', 'bin/amd-64', 'admin', 'readmes', 'python', 'pb'):
        p = root / dirname
        require(p.is_dir() and not p.is_symlink(), 'Incomplete or unsafe server directory: ' + dirname)
    require(not any((root / 'pb').iterdir()) and not (root / 'pb_amd-64').exists() and
            not (root / 'pb_ia-32').exists(), 'PunkBuster is unsupported and must remain absent')
    for name, sha in BASE_HASHES.items():
        p = root / name
        regular(p, executable=True)
        require(digest(p) == sha, 'Original server file hash mismatch: ' + name)
    for name in ('readmes/eula.txt', 'readmes/readme-linux.txt', 'readmes/readmeserver.txt',
                 'pylib-2.3.4.zip', 'admin/default.py'):
        regular(root / name)
    if hub:
        for name, sha in HUB_HASHES.items():
            if '/ia-32/' in name:
                continue
            regular(root / name, executable=name.endswith(('.sh', '.so')))
            require(digest(root / name) == sha, 'BF2Hub R3 file hash mismatch: ' + name)


def runtime_preflight(root, hub):
    require(platform.machine() == 'x86_64', 'This image supports amd64 only; ia32 is not offered')
    binary = root / 'bin/amd-64/bf2'
    header = binary.read_bytes()[:20]
    require(header[:5] == b'\x7fELF\x02' and header[5] == 1 and header[18:20] == b'\x3e\x00',
            'Expected native little-endian amd64 ELF')
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LD_LIBRARY_PATH': str(root / 'bin/amd-64')}
    targets = [binary, root / 'bin/amd-64/libaidll.so', root / 'bin/amd-64/libdice_py.so']
    if hub:
        targets.append(root / 'bin/amd-64/libbf2hub.so')
    output = ''
    for target in targets:
        result = subprocess.run(['ldd', str(target)], env=env, capture_output=True, text=True, timeout=20)
        require(result.returncode == 0 and 'not found' not in result.stdout + result.stderr,
                'Missing runtime dependency; use the supplied amd64 ncurses5 image')
        output += result.stdout
    match = re.search(r'libncurses\.so\.5\s+=>\s+(\S+)', output)
    require(match, 'Genuine libncurses.so.5 is required')
    actual = Path(match[1]).resolve(strict=True)
    result = subprocess.run(['readelf', '-d', str(actual)], capture_output=True, text=True, timeout=20)
    require(result.returncode == 0 and '(SONAME)' in result.stdout and
            re.search(r'\(SONAME\).*\[libncurses\.so\.5\]', result.stdout),
            'Wrong ncurses ABI; symlinking ncurses6 to ncurses5 is forbidden')


def publish_config(root, files):
    """One atomic generation switch updates all three files; preserve vendor settings."""
    folder = root / 'egg-config'
    folder.mkdir(exist_ok=True, mode=0o700)
    require(not folder.is_symlink(), 'Unsafe generated config directory')
    current = folder / 'current'
    admin = root / 'admin/default.cfg'
    expected = '../egg-config/current/default.cfg'
    require(not admin.exists() and not admin.is_symlink() or
            admin.is_symlink() and os.readlink(admin) == expected, 'Operator admin/default.cfg exists; back it up explicitly first')
    old = None
    if current.exists() or current.is_symlink():
        require(current.is_symlink() and re.fullmatch(r'g-[0-9a-f]{64}', os.readlink(current)),
                'Unexpected generated configuration pointer')
        old = folder / os.readlink(current)
        require(old.is_dir() and not old.is_symlink(), 'Unsafe config generation')
        require(regular(old / 'hashes.json').st_size < 4096, 'Unsafe config manifest')
        saved = json.loads((old / 'hashes.json').read_text())
        require(set(saved) == set(files), 'Invalid generated config manifest')
        require({p.name for p in old.iterdir()} == set(files) | {'hashes.json'},
                'Previous config generation contains unexpected files; preserve for inspection')
        for name, sha in saved.items():
            require(digest(old / name) == sha, 'Generated config was edited; preserve edits before restarting')
    hashes = {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}
    gen_name = 'g-' + hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    target = folder / gen_name
    if target.exists() or target.is_symlink():
        require(target.is_dir() and not target.is_symlink(), 'Unsafe config generation')
        require(regular(target / 'hashes.json').st_size < 4096, 'Unsafe config manifest')
        require(json.loads((target / 'hashes.json').read_text()) == hashes, 'Config manifest differs')
        for name, sha in hashes.items():
            require(digest(target / name) == sha, 'Existing config generation differs')
    else:
        with tempfile.TemporaryDirectory(prefix='.config-', dir=folder) as tmp:
            stage = Path(tmp) / 'generation'
            stage.mkdir(mode=0o700)
            for name, content in files.items():
                atomic_write(stage / name, content)
            atomic_write(stage / 'hashes.json', json.dumps(hashes, sort_keys=True).encode())
            os.rename(stage, target)
    created_admin = False
    link = folder / '.next'
    require(not link.exists() and not link.is_symlink(), 'Stale config transaction; inspect .next')
    try:
        if not admin.is_symlink():
            admin.symlink_to(expected)
            created_admin = True
        link.symlink_to(gen_name)
        os.replace(link, current)
    except BaseException:
        if created_admin:
            admin.unlink()
        if link.is_symlink():
            link.unlink()
        raise
    # Old generations contain passwords. Keep only the active generation, after publication.
    if old is not None and old != target:
        shutil.rmtree(old)


def launch(root, env):
    acknowledgments(env)
    hub = switch(env, 'BF2HUB_ENABLED')
    verify_install(root, hub)
    files, mod, hub = settings(root, env)
    runtime_preflight(root, hub)
    publish_config(root, files)
    launch_env = dict(env)
    for key in list(launch_env):
        if key.startswith('LD_') or key in ('BASH_ENV', 'ENV', 'PYTHONPATH', 'PYTHONHOME'):
            del launch_env[key]
    launch_env.update(PATH='/usr/bin:/bin', LANG='C', TERM='xterm', HOME=str(root.parent))
    launcher = './start_bf2hub.sh' if hub else './start_original.sh'
    argv = [launcher, '+modPath', 'mods/' + mod, '+config', 'egg-config/current/serversettings.con',
            '+mapList', 'egg-config/current/maplist.con']
    os.chdir(root)
    print('BF2 preflight passed; launching original amd64 server. Readiness is unverified.', flush=True)
    os.execve(launcher, argv, launch_env)


def main():
    root = Path(__file__).resolve().parent.parent
    with locked(root.parent):
        launch(root, os.environ)


if __name__ == '__main__':
    try:
        main()
    except (Refusal, OSError, ValueError, ET.ParseError, zipfile.BadZipFile, subprocess.SubprocessError) as e:
        print('BF2 startup refused: ' + str(e), file=sys.stderr)
        sys.exit(1)
