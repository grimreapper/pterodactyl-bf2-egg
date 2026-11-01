"""Non-proprietary executable failure matrix. No game archive download or server launch."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import common
import build_release
import install
import render
import runtime
import scan_public
import spec


def fixture(root):
    for name in ('admin', 'pb', 'bin/amd-64', 'readmes', 'python'):
        (root / name).mkdir(parents=True, exist_ok=True)
    mod = root / 'mods/bf2'
    mod.mkdir(parents=True, exist_ok=True)
    (mod / 'init.con').write_text('rem synthetic test\n')
    for level, support in [('strike_at_karkand', [('gpm_cq', 32), ('gpm_coop', 16)]),
                           ('wake_island_2007', [('gpm_cq', 64)])]:
        p = mod / 'levels' / level
        (p / 'info').mkdir(parents=True)
        xml = '<map><modes>' + ''.join(f'<mode type="{m}"><maptype players="{s}"/></mode>' for m, s in support) + '</modes></map>'
        (p / 'info' / (level + '.desc')).write_text(xml)
        with zipfile.ZipFile(p / 'server.zip', 'w') as z:
            for m, s in support:
                z.writestr(f'GameModes/{m}/{s}/GamePlayObjects.con', 'rem synthetic fixture\n')
    return root


def env(**kwargs):
    return dict(spec.DEFAULTS, EA_EULA_ACCEPT='YES', NONCOMMERCIAL_USE='YES') | kwargs


def tar(path, entries):
    with tarfile.open(path, 'w:gz') as t:
        for name, kind, content in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            if kind == tarfile.REGTYPE:
                member.size = len(content)
                t.addfile(member, io.BytesIO(content))
            else:
                member.linkname = content.decode()
                t.addfile(member)


class Workspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)


class Configuration(Workspace):
    def setUp(self):
        super().setUp()
        fixture(self.root)

    def test_defaults_and_vendor_files_preserved(self):
        vendor = self.root / 'mods/bf2/settings'
        vendor.mkdir()
        p = vendor / 'serversettings.con'
        p.write_text('operator config')
        files, mod, hub = runtime.settings(self.root, env())
        runtime.publish_config(self.root, files)
        self.assertEqual(p.read_text(), 'operator config')
        self.assertEqual(mod, 'bf2')
        self.assertFalse(hub)
        self.assertIn(b'sv.adminScript ""\n', files['serversettings.con'])
        self.assertIn(b'sv.punkBuster 0\n', files['serversettings.con'])
        self.assertIn(b'sv.voipEnabled 0\n', files['serversettings.con'])
        self.assertEqual(files['maplist.con'], b'mapList.append strike_at_karkand gpm_cq 32\n')

    def test_config_atomic_idempotent_and_private(self):
        files, _, _ = runtime.settings(self.root, env())
        runtime.publish_config(self.root, files)
        before = os.readlink(self.root / 'egg-config/current')
        runtime.publish_config(self.root, files)
        self.assertEqual(before, os.readlink(self.root / 'egg-config/current'))
        self.assertEqual((self.root / 'admin/default.cfg').read_bytes(), files['default.cfg'])
        self.assertEqual((self.root / 'admin/default.cfg').stat().st_mode & 0o777, 0o600)
        files['default.cfg'] += b'\n'
        runtime.publish_config(self.root, files)
        self.assertNotEqual(before, os.readlink(self.root / 'egg-config/current'))
        self.assertEqual(len(list((self.root / 'egg-config').glob('g-*'))), 1)

    def test_admin_operator_file_preserved(self):
        p = self.root / 'admin/default.cfg'
        p.write_text('operator data')
        with self.assertRaises(common.Refusal):
            runtime.publish_config(self.root, runtime.settings(self.root, env())[0])
        self.assertEqual(p.read_text(), 'operator data')

    def test_admin_external_symlink_refused(self):
        outside = self.root / 'outside'
        outside.write_text('unchanged')
        (self.root / 'admin/default.cfg').symlink_to(outside)
        with self.assertRaises(common.Refusal):
            runtime.publish_config(self.root, runtime.settings(self.root, env())[0])
        self.assertEqual(outside.read_text(), 'unchanged')

    def test_config_transaction_failure_preserves_previous(self):
        files = runtime.settings(self.root, env())[0]
        runtime.publish_config(self.root, files)
        before = os.readlink(self.root / 'egg-config/current')
        files['default.cfg'] += b'\n'
        with mock.patch.object(runtime.os, 'replace', side_effect=OSError('injected')):
            with self.assertRaises(OSError):
                runtime.publish_config(self.root, files)
        self.assertEqual(before, os.readlink(self.root / 'egg-config/current'))

    def test_first_config_failure_removes_admin_link(self):
        files = runtime.settings(self.root, env())[0]
        real_replace = os.replace
        def failure(src, dst):
            if Path(dst).name == 'current':
                raise OSError('injected')
            return real_replace(src, dst)
        with mock.patch.object(runtime.os, 'replace', side_effect=failure):
            with self.assertRaises(OSError):
                runtime.publish_config(self.root, files)
        self.assertFalse((self.root / 'admin/default.cfg').is_symlink())

    def test_unexpected_generation_file_preserved_before_switch(self):
        files = runtime.settings(self.root, env())[0]
        runtime.publish_config(self.root, files)
        before = os.readlink(self.root / 'egg-config/current')
        operator = self.root / 'egg-config/current/operator.save'
        operator.write_text('preserve')
        files['default.cfg'] += b'\n'
        with self.assertRaises(common.Refusal):
            runtime.publish_config(self.root, files)
        self.assertEqual(before, os.readlink(self.root / 'egg-config/current'))
        self.assertEqual(operator.read_text(), 'preserve')

    def test_current_symlink_escape_refused(self):
        (self.root / 'egg-config').mkdir()
        (self.root / 'egg-config/current').symlink_to(self.root)
        with self.assertRaises(common.Refusal):
            runtime.publish_config(self.root, runtime.settings(self.root, env())[0])

    def test_manual_generated_edit_refused(self):
        files = runtime.settings(self.root, env())[0]
        runtime.publish_config(self.root, files)
        (self.root / 'egg-config/current/maplist.con').write_text('operator edit')
        with self.assertRaises(common.Refusal):
            runtime.publish_config(self.root, files)

    def test_eula_exact_gate(self):
        for key in ('EA_EULA_ACCEPT', 'NONCOMMERCIAL_USE'):
            for bad in ('', 'NO', 'yes', '1', 'YES ', 'YES\n'):
                with self.subTest(key=key, bad=repr(bad)), self.assertRaises(common.Refusal):
                    runtime.settings(self.root, env(**{key: bad}))

    def test_control_character_and_quote_matrix(self):
        for key in spec.VARIABLES:
            for bad in ('x\n', 'x\r', 'x\x00', 'x\x7f', 'x\t'):
                with self.subTest(key=key), self.assertRaises(common.Refusal):
                    common.value({key: bad}, key)
        for bad in ('x"y', 'x\\y', ''):
            with self.assertRaises(common.Refusal):
                runtime.settings(self.root, env(SERVER_NAME=bad))

    def test_integer_and_switch_domains(self):
        for bad in ('-1', '65', '1.5', '01', ' 2', '', '1e1'):
            with self.assertRaises(common.Refusal):
                runtime.settings(self.root, env(MAX_PLAYERS=bad))
        for key in ('RCON_ENABLED', 'BF2HUB_ENABLED', 'INTERNET', 'VOIP_ENABLED'):
            with self.assertRaises(common.Refusal):
                runtime.settings(self.root, env(**{key: 'true'}))

    def test_player_bot_constraints(self):
        for updates in ({'MIN_PLAYERS': '33'}, {'BOT_COUNT': '33'}, {'BOT_COUNT': '10'},
                        {'BOT_DIFFICULTY': '9'}, {'BOT_RATIO': '101'}):
            with self.assertRaises(common.Refusal):
                runtime.settings(self.root, env(**updates))
        files, _, _ = runtime.settings(self.root, env(BOT_COUNT='16', MAP_ROTATION='strike_at_karkand gpm_coop 16'))
        self.assertIn(b'sv.coopBotCount 16\n', files['serversettings.con'])

    def test_ports_binding_and_distinctness(self):
        for changes in ({'SERVER_PORT': '80'}, {'QUERY_PORT': '16567'}, {'SERVER_BIND_IP': 'not-an-ip'},
                        {'RCON_ENABLED': '1', 'RCON_PORT': '16567', 'RCON_PASSWORD': 'N7!bk4_Q9pZ2.vR8'},
                        {'VOIP_ENABLED': '1', 'VOIP_BF_PORT': '55123'}):
            with self.assertRaises(ValueError):
                runtime.settings(self.root, env(**changes))
        files, _, _ = runtime.settings(self.root, env(VOIP_ENABLED='1', QUERY_PORT='29901'))
        self.assertIn(b'sv.gameSpyPort 29901\n', files['serversettings.con'])
        self.assertIn(b'sv.voipEnabled 1\n', files['serversettings.con'])

    def test_placeholder_secret_matrix(self):
        for bad in ('', 'password123456789', 'ChangeMe_12345678', 'YOUR_RCON_PASSWORD', 'a'*20,
                    'Admin-Password-123', 'long enough=but invalid', 'long enough spaces'):
            with self.subTest(bad=bad), self.assertRaises(common.Refusal):
                runtime.settings(self.root, env(RCON_ENABLED='1', RCON_PASSWORD=bad))
        for bad in ('changeme12345678', 'short', 'passwordpassword'):
            with self.assertRaises(common.Refusal):
                runtime.settings(self.root, env(SERVER_PASSWORD=bad))

    def test_rcon_exact_output(self):
        pwd = 'N7!bk4_Q9pZ2.vR8'
        files, _, _ = runtime.settings(self.root, env(RCON_ENABLED='1', RCON_PASSWORD=pwd, RCON_PORT='4712'))
        self.assertEqual(files['default.cfg'], f'port=4712\npassword={pwd}\n'.encode())
        self.assertIn(b'sv.adminScript "default"\n', files['serversettings.con'])

    def test_mod_tokens_and_case(self):
        for bad in ('BF2', '../bf2', 'bf2/../../', '.hidden', 'x-pack', ''):
            with self.assertRaises(common.Refusal):
                runtime.settings(self.root, env(MOD=bad))
        path = self.root / 'mods/bf2/UPPER.txt'
        path.write_text('fixture')
        with self.assertRaises(common.Refusal):
            runtime.settings(self.root, env())
        path.rename(path.with_name('AllowedPython.py'))
        runtime.settings(self.root, env())

    def test_rotation_invalid_and_no_invented_support(self):
        for bad in ('', ';', 'strike_at_karkand gpm_cq', 'strike_at_karkand gpm_cq 32;',
                    'wake_island_2007 gpm_coop 16', 'wake_island_2007 gpm_cq 32',
                    'strike_at_karkand gpm_cq 128', 'strike_at_karkand gpm_sl 32',
                    '../escape gpm_cq 32', '* gpm_cq 32', 'missing gpm_cq 32'):
            with self.subTest(bad=bad), self.assertRaises((common.Refusal, OSError)):
                runtime.settings(self.root, env(MAP_ROTATION=bad))

    def test_multiple_modes_preserved_in_order(self):
        rotation = 'wake_island_2007 gpm_cq 64; strike_at_karkand gpm_coop 16'
        files, _, _ = runtime.settings(self.root, env(MAP_ROTATION=rotation, BOT_COUNT='8'))
        self.assertEqual(files['maplist.con'].decode().splitlines(),
                         ['mapList.append wake_island_2007 gpm_cq 64', 'mapList.append strike_at_karkand gpm_coop 16'])

    def test_zip_data_alone_does_not_add_support(self):
        p = self.root / 'mods/bf2/levels/wake_island_2007'
        with zipfile.ZipFile(p / 'server.zip', 'a') as z:
            z.writestr('GameModes/gpm_coop/16/GamePlayObjects.con', 'fixture')
        self.assertEqual(runtime.map_support(p), {('gpm_cq', 64)})

    def test_desc_alone_does_not_add_support(self):
        p = self.root / 'mods/bf2/levels/wake_island_2007'
        d = p / 'info/wake_island_2007.desc'
        d.write_text(d.read_text().replace('</modes>', '<mode type="gpm_coop"><maptype players="16"/></mode></modes>'))
        self.assertEqual(runtime.map_support(p), {('gpm_cq', 64)})

    def test_xml_entity_and_bad_root_refused(self):
        p = self.root / 'mods/bf2/levels/wake_island_2007'
        for text in ('<!DOCTYPE map><map/>', '<wrong/>', '<map><modes><mode type="gpm_cq"><maptype players="64"/><maptype players="64"/></mode></modes></map>'):
            (p / 'info/wake_island_2007.desc').write_text(text)
            with self.assertRaises(common.Refusal):
                runtime.map_support(p)

    def test_zip_case_collision_and_traversal_refused(self):
        p = self.root / 'mods/bf2/levels/wake_island_2007'
        for entry in ('gamemodes/GPM_CQ/64/gameplayobjects.con', '../outside'):
            with zipfile.ZipFile(p / 'server.zip', 'w') as z:
                z.writestr('GameModes/gpm_cq/64/GamePlayObjects.con', 'fixture')
                z.writestr(entry, 'fixture')
            with self.assertRaises(common.Refusal):
                runtime.map_support(p)

    def test_symlink_mod_refused(self):
        (self.root / 'mods/custom').symlink_to(self.root / 'mods/bf2', target_is_directory=True)
        with self.assertRaises(common.Refusal):
            runtime.settings(self.root, env(MOD='custom'))

    def test_hub_requires_internet(self):
        with self.assertRaises(common.Refusal):
            runtime.settings(self.root, env(BF2HUB_ENABLED='1'))


class ArchiveSafety(Workspace):
    def test_exact_size_and_hash(self):
        p = self.root / 'input'
        p.write_bytes(b'fixture')
        sha = hashlib.sha256(b'fixture').hexdigest()
        common.verify(p, 7, sha)
        for size, digest in [(8, sha), (7, '0'*64)]:
            with self.assertRaises(common.Refusal):
                common.verify(p, size, digest)

    def test_real_pin_rejects_sparse_wrong_content(self):
        p = self.root / spec.ARCHIVE
        with p.open('wb') as f:
            f.truncate(spec.ARCHIVE_SIZE)
        with self.assertRaisesRegex(common.Refusal, 'SHA-256'):
            common.verify(p, spec.ARCHIVE_SIZE, spec.ARCHIVE_SHA256)

    def test_snapshot_links_rejected(self):
        p = self.root / 'input'
        p.write_bytes(b'fixture')
        s = self.root / 'symlink'
        s.symlink_to(p)
        for source in (s,):
            with self.assertRaises(OSError):
                common.snapshot(source, self.root / 'out', 7, hashlib.sha256(b'fixture').hexdigest())
        os.link(p, self.root / 'hardlink')
        with self.assertRaises(common.Refusal):
            common.snapshot(p, self.root / 'out', 7, hashlib.sha256(b'fixture').hexdigest())

    def test_snapshot_is_verified_private_copy(self):
        p = self.root / 'input'
        p.write_bytes(b'fixture')
        out = self.root / 'out'
        common.snapshot(p, out, 7, hashlib.sha256(b'fixture').hexdigest())
        p.write_bytes(b'changed')
        self.assertEqual(out.read_bytes(), b'fixture')

    def test_tar_path_and_type_matrix(self):
        for name, kind in [('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE),
                           ('dir/../../escape', tarfile.REGTYPE), ('dir\\bad', tarfile.REGTYPE),
                           ('link', tarfile.SYMTYPE), ('hard', tarfile.LNKTYPE), ('fifo', tarfile.FIFOTYPE),
                           ('dev', tarfile.CHRTYPE)]:
            tar(self.root / 'a.gz', [(name, kind, b'x')])
            with tarfile.open(self.root / 'a.gz') as t, self.assertRaises(common.Refusal):
                common.inspect_tar(t)

    def test_tar_duplicate_case_and_budgets(self):
        for entries in [[('same', tarfile.REGTYPE, b'x'), ('same', tarfile.REGTYPE, b'y')],
                        [('same', tarfile.REGTYPE, b'x'), ('SAME', tarfile.REGTYPE, b'y')]]:
            tar(self.root / 'a.gz', entries)
            with tarfile.open(self.root / 'a.gz') as t, self.assertRaises(common.Refusal):
                common.inspect_tar(t)
        tar(self.root / 'a.gz', [('file', tarfile.REGTYPE, b'too long')])
        with tarfile.open(self.root / 'a.gz') as t, self.assertRaises(common.Refusal):
            common.inspect_tar(t, max_bytes=3)

    def test_exact_outer_file_set(self):
        tar(self.root / 'a.gz', [('different.sh', tarfile.REGTYPE, b'fixture')])
        with self.assertRaises(common.Refusal):
            common.extract_tar(self.root / 'a.gz', self.root / 'out', {spec.INNER})
        self.assertFalse((self.root / 'out').exists())

    def test_https_only_credentials_and_controls(self):
        for url in ('http://www.bf2hub.com/file', 'file:///tmp/file', 'https://' + 'u:p' + '@' + 'www.bf2hub.com/file',
                    'https://www.bf2hub.com/file#fragment', 'https://www.bf2hub.com/\nfile', '--config=x'):
            with self.assertRaises(ValueError):
                common.https_url(url)
        self.assertEqual(common.https_url(spec.HUB_URL), spec.HUB_URL)

    def test_curl_redirect_policies_and_html_rejection(self):
        def fake(cmd, **kwargs):
            p = Path(cmd[cmd.index('--output') + 1])
            p.write_bytes(b'<html>')
            return subprocess.CompletedProcess(cmd, 0)
        for hub in (False, True):
            with mock.patch.object(common.subprocess, 'run', side_effect=fake) as run:
                with self.assertRaises(common.Refusal):
                    common.download(spec.HUB_URL, self.root / 'out', spec.HUB_SIZE, spec.HUB_SHA256, direct_hub=hub)
                cmd = run.call_args.args[0]
                self.assertEqual(cmd[cmd.index('--proto-redir')+1], '=https')
                self.assertEqual('--location' in cmd, not hub)
                self.assertEqual(cmd[1], '--disable')

    def test_download_has_kernel_size_cap(self):
        real_run = subprocess.run
        def oversized(cmd, **kwargs):
            destination = cmd[cmd.index('--output') + 1]
            return real_run([sys.executable, '-B', '-c',
                             "import sys;f=open(sys.argv[1],'wb',buffering=0);f.write(b'x'*100000)",
                             destination], **kwargs)
        with mock.patch.object(common.subprocess, 'run', side_effect=oversized):
            with self.assertRaises(common.Refusal):
                common.download(spec.HUB_URL, self.root / 'out', 7, '0'*64)
        self.assertLessEqual((self.root / 'out').stat().st_size, 7)

    def test_local_upload_precedes_all_network(self):
        (self.root / spec.ARCHIVE).write_bytes(b'bad upload')
        stage = self.root / 'stage'
        stage.mkdir()
        with mock.patch.object(install, 'download') as download:
            with self.assertRaises(common.Refusal):
                install.acquire(self.root, stage, env(ALLOW_THIRD_PARTY_MIRROR='1', ARCHIVE_URL=spec.MIRROR))
            download.assert_not_called()

    def test_network_source_selection(self):
        stage = self.root / 'stage'
        stage.mkdir()
        with self.assertRaises(common.Refusal):
            install.acquire(self.root, stage, env())
        for changes in ({'ARCHIVE_URL': spec.MIRROR}, {'ALLOW_THIRD_PARTY_MIRROR': '1'}):
            with mock.patch.object(install, 'download') as download:
                install.acquire(self.root, stage, env(**changes))
                self.assertEqual(download.call_args.args[0], spec.MIRROR)
        with mock.patch.object(install, 'download') as download:
            install.acquire(self.root, stage, env(), hub=True)
            self.assertEqual(download.call_args.args[0], spec.HUB_URL)
            self.assertTrue(download.call_args.kwargs['direct_hub'])

    def test_acknowledgments_before_mutation_or_network(self):
        for changes in ({}, {'EA_EULA_ACCEPT': 'YES'}, {'EA_EULA_ACCEPT': 'yes', 'NONCOMMERCIAL_USE': 'YES'}):
            with mock.patch.object(install, 'acquire') as acquire:
                with self.assertRaises(common.Refusal):
                    install.install(self.root, changes)
                acquire.assert_not_called()
                self.assertEqual(list(self.root.iterdir()), [])

    def test_install_failure_leaves_no_server(self):
        with mock.patch.object(install, 'acquire', side_effect=common.Refusal('injected')):
            with self.assertRaises(common.Refusal):
                install.install(self.root, env())
        self.assertFalse((self.root / 'server').exists())
        self.assertFalse(list(self.root.glob('.bf2-install-*')))

    def test_reinstall_preserves_state_and_never_downloads(self):
        p = self.root / 'server'
        fixture(p)
        (p / 'operator.save').write_text('keep')
        with mock.patch.object(install, 'verify_install'), mock.patch.object(install, 'acquire') as acquire:
            install.install(self.root, env())
            acquire.assert_not_called()
        self.assertEqual((p / 'operator.save').read_text(), 'keep')

    def test_atomic_install_success_with_synthetic_payload(self):
        def unpack_fake(_archive, stage):
            payload = fixture(stage / 'payload')
            for name in ('pb_amd-64', 'pb_ia-32', 'bin/ia-32'):
                (payload / name).mkdir(parents=True)
            (payload / 'pb').rmdir()
            (payload / 'license.sh').write_text('must never execute')
            (payload / 'start.sh').write_text('synthetic launcher')
            (payload / 'start.sh').chmod(0o755)
            return payload
        with mock.patch.object(install, 'acquire', return_value=self.root / 'input'), \
             mock.patch.object(install, 'unpack', side_effect=unpack_fake), \
             mock.patch.object(install, 'verify_install'):
            install.install(self.root, env())
        server = self.root / 'server'
        self.assertEqual((server / 'start_original.sh').read_text(), 'synthetic launcher')
        self.assertTrue((server / 'egg/runtime.py').is_file())
        self.assertFalse((server / 'license.sh').exists())
        self.assertFalse((server / 'pb_amd-64').exists())
        self.assertFalse(list(self.root.glob('.bf2-install-*')))

    def test_invalid_config_never_publishes_payload(self):
        def unpack_fake(_archive, stage):
            payload = fixture(stage / 'payload')
            (payload / 'pb').rmdir()
            (payload / 'license.sh').write_text('must never execute')
            (payload / 'start.sh').write_text('synthetic launcher')
            return payload
        with mock.patch.object(install, 'acquire', return_value=self.root / 'input'), \
             mock.patch.object(install, 'unpack', side_effect=unpack_fake), \
             mock.patch.object(install, 'verify_install'):
            with self.assertRaises(common.Refusal):
                install.install(self.root, env(MAP_ROTATION=''))
        self.assertFalse((self.root / 'server').exists())
        self.assertFalse(list(self.root.glob('.bf2-install-*')))

    def test_snapshot_detects_source_change(self):
        from types import SimpleNamespace
        source = self.root / 'source'
        source.write_bytes(b'fixture')
        real = os.fstat
        count = [0]
        def changing(fd):
            st = real(fd)
            count[0] += 1
            return SimpleNamespace(st_mode=st.st_mode, st_nlink=st.st_nlink, st_size=st.st_size,
                                   st_mtime_ns=st.st_mtime_ns, st_ctime_ns=st.st_ctime_ns + count[0])
        with mock.patch.object(common.os, 'fstat', side_effect=changing), self.assertRaisesRegex(common.Refusal, 'changed'):
            common.snapshot(source, self.root / 'out', 7, hashlib.sha256(b'fixture').hexdigest())

    def test_lock_rejects_overlap_and_symlink(self):
        with common.locked(self.root):
            with self.assertRaises(common.Refusal):
                with common.locked(self.root):
                    pass
        (self.root / '.bf2-egg.lock').unlink()
        (self.root / '.bf2-egg.lock').symlink_to(self.root / 'elsewhere')
        with self.assertRaises(OSError):
            with common.locked(self.root):
                pass

    def test_lock_remains_openable_across_installer_runtime_uids(self):
        old = os.umask(0o077)
        try:
            with common.locked(self.root):
                pass
        finally:
            os.umask(old)
        self.assertEqual((self.root / '.bf2-egg.lock').stat().st_mode & 0o777, 0o666)
        # A later runtime UID can open the root-owned 0666 inode but cannot chmod
        # it. Correct permissions must therefore avoid a second fchmod entirely.
        with mock.patch.object(common.os, 'fchmod', side_effect=PermissionError) as chmod:
            with common.locked(self.root):
                pass
        chmod.assert_not_called()


class RuntimeChecks(Workspace):
    def setUp(self):
        super().setUp()
        fixture(self.root)
        self.hashes = {}
        for name in spec.BASE_HASHES:
            p = self.root / name
            p.write_bytes(('synthetic ' + name).encode())
            p.chmod(0o755)
            self.hashes[name] = common.digest(p)
        for name in ('readmes/eula.txt', 'readmes/readme-linux.txt', 'readmes/readmeserver.txt', 'pylib-2.3.4.zip', 'admin/default.py'):
            (self.root / name).write_text('synthetic fixture')

    def test_library_file_fault_matrix(self):
        with mock.patch.object(runtime, 'BASE_HASHES', self.hashes):
            runtime.verify_install(self.root)
            for name in self.hashes:
                p = self.root / name
                data = p.read_bytes()
                for fault in ('missing', 'empty', 'symlink', 'not_executable', 'wrong_hash'):
                    with self.subTest(name=name, fault=fault):
                        p.unlink()
                        if fault == 'empty': p.touch()
                        elif fault == 'symlink': p.symlink_to(self.root / 'mods/bf2/init.con')
                        elif fault == 'not_executable': p.write_bytes(data); p.chmod(0o600)
                        elif fault == 'wrong_hash': p.write_bytes(b'corrupt'); p.chmod(0o755)
                        with self.assertRaises((common.Refusal, OSError)):
                            runtime.verify_install(self.root)
                        if p.exists() or p.is_symlink(): p.unlink()
                        p.write_bytes(data); p.chmod(0o755)

    def test_hub_enabled_without_files_fails(self):
        with mock.patch.object(runtime, 'BASE_HASHES', self.hashes), self.assertRaises(OSError):
            runtime.verify_install(self.root, True)

    def test_punkbuster_injection_refused(self):
        (self.root / 'pb/unwanted').write_text('fixture')
        with mock.patch.object(runtime, 'BASE_HASHES', self.hashes), self.assertRaises(common.Refusal):
            runtime.verify_install(self.root)

    def test_ncurses6_alias_refused(self):
        b = self.root / 'bin/amd-64/bf2'
        b.write_bytes(b'\x7fELF\x02\x01' + b'\0'*12 + b'\x3e\x00')
        lib = self.root / 'libncurses.so.5'
        lib.write_text('fixture')
        def run(cmd, **kwargs):
            text = f'libncurses.so.5 => {lib}\n' if cmd[0] == 'ldd' else '(SONAME) [libncurses.so.6]'
            return subprocess.CompletedProcess(cmd, 0, text, '')
        with mock.patch.object(runtime.subprocess, 'run', side_effect=run), self.assertRaisesRegex(common.Refusal, 'Wrong ncurses ABI'):
            runtime.runtime_preflight(self.root, False)

    def test_missing_library_refused(self):
        b = self.root / 'bin/amd-64/bf2'
        b.write_bytes(b'\x7fELF\x02\x01' + b'\0'*12 + b'\x3e\x00')
        result = subprocess.CompletedProcess([], 0, 'libncurses.so.5 => not found', '')
        with mock.patch.object(runtime.subprocess, 'run', return_value=result), self.assertRaises(common.Refusal):
            runtime.runtime_preflight(self.root, False)

    def test_architecture_refused(self):
        with mock.patch.object(runtime.platform, 'machine', return_value='aarch64'), self.assertRaises(common.Refusal):
            runtime.runtime_preflight(self.root, False)

    def test_preflight_before_config_rewrites(self):
        with mock.patch.object(runtime, 'verify_install'), mock.patch.object(runtime, 'runtime_preflight', side_effect=common.Refusal('missing lib')):
            with self.assertRaises(common.Refusal):
                runtime.launch(self.root, env())
        self.assertFalse((self.root / 'egg-config').exists())

    def test_original_and_hub_launch_argv(self):
        for hub in (False, True):
            old = Path.cwd()
            try:
                with mock.patch.object(runtime, 'verify_install'), mock.patch.object(runtime, 'runtime_preflight'), mock.patch.object(runtime.os, 'execve') as execute:
                    runtime.launch(self.root, env(BF2HUB_ENABLED=str(int(hub)), INTERNET=str(int(hub)), LD_PRELOAD='untrusted'))
                args = execute.call_args.args
                self.assertEqual(args[0], './start_bf2hub.sh' if hub else './start_original.sh')
                self.assertEqual(args[1][1:3], ['+modPath', 'mods/bf2'])
                self.assertNotIn('LD_PRELOAD', args[2])
            finally:
                os.chdir(old)


class Artifacts(Workspace):
    def test_ptdl_strings_and_defaults(self):
        egg = json.loads(render.render())
        self.assertEqual(egg['meta']['version'], 'PTDL_v2')
        for key in ('files', 'startup', 'logs'):
            self.assertIsInstance(egg['config'][key], str)
            json.loads(egg['config'][key])
        self.assertEqual(egg['config']['stop'], '^C')
        self.assertEqual(egg['author'], 'community@example.invalid')
        self.assertEqual({x['env_variable']: x['default_value'] for x in egg['variables']}, spec.DEFAULTS)
        for var in egg['variables']:
            self.assertNotIn('regex:', var['rules'])
            if var['default_value'] in ('0', '1') and 'in:0,1' in var['rules']:
                self.assertIn('integer', var['rules'])

    def test_panel_reserved_environment_names_are_not_variables(self):
        reserved = {'SERVER_MEMORY', 'SERVER_IP', 'SERVER_PORT', 'ENV', 'HOME', 'USER',
                    'STARTUP', 'SERVER_UUID', 'UUID'}
        variables = {x['env_variable'] for x in json.loads(render.render())['variables']}
        self.assertFalse(variables & reserved)
        self.assertEqual(common.value({}, 'SERVER_PORT'), '16567')
        self.assertEqual(common.value({'SERVER_PORT': '17777'}, 'SERVER_PORT'), '17777')

    def test_container_image_install_and_runtime_user_contract(self):
        dockerfile = (ROOT / 'container/Dockerfile').read_text()
        entrypoint = (ROOT / 'container/entrypoint.sh').read_text()
        smoke = (ROOT / 'scripts/container_smoke.sh').read_text()
        directives = [line.strip() for line in dockerfile.splitlines()
                      if line.strip() and not line.lstrip().startswith('#')]
        self.assertFalse(any(line.startswith('USER ') for line in directives))
        self.assertIn('exec "$@"', entrypoint)
        self.assertIn('test "$(id -u)" = 0', smoke)
        self.assertNotIn('--user 0:0', smoke)
        self.assertNotIn('docker run --rm --network none --entrypoint /bin/bash', smoke)
        self.assertIn('"$image" bash /mnt/install/install.sh', smoke)
        self.assertIn('--user 1000:1000', smoke)
        self.assertIn('container_id=$(docker run -dit', smoke)
        self.assertIn('docker rm -f "$container_id"', smoke)
        self.assertNotIn('docker rm -f "$name"', smoke)

    def test_container_name_collision_never_removes_existing_container(self):
        fakebin = self.root / 'bin'
        fakebin.mkdir()
        log = self.root / 'docker.log'
        docker = fakebin / 'docker'
        docker.write_text(
            '#!/bin/bash\n'
            'printf "%s\\n" "$*" >> "$DOCKER_LOG"\n'
            'if [[ $1 == volume && $2 == create ]]; then echo fixture-volume; fi\n'
            'if [[ " $* " == *" -dit "* ]]; then exit 125; fi\n'
        )
        docker.chmod(0o755)
        archive = self.root / 'archive.tgz'
        archive.write_bytes(b'fixture')
        environment = dict(os.environ, PATH=str(fakebin) + ':/usr/bin:/bin',
                           DOCKER_LOG=str(log), BF2_ARCHIVE=str(archive),
                           EA_EULA_ACCEPT='YES', NONCOMMERCIAL_USE='YES')
        result = subprocess.run(['bash', str(ROOT / 'scripts/container_smoke.sh'), '--payload'],
                                env=environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 125)
        calls = log.read_text().splitlines()
        self.assertFalse(any(call.startswith('rm -f ') for call in calls))
        self.assertIn('volume rm fixture-volume', calls)

    def test_release_outputs_replace_symlinks_without_touching_targets(self):
        repo = self.root / 'repo'
        outside = self.root / 'outside'
        (repo / 'dist').mkdir(parents=True)
        outside.mkdir()
        (repo / 'notes.md').write_text('fixture\n')
        generated = [repo / render.EGG, repo / 'SHA256SUMS',
                     repo / 'dist/bf2-native-linux-egg.zip', repo / 'dist/SHA256SUMS']
        targets = []
        for number, path in enumerate(generated):
            target = outside / str(number)
            target.write_bytes(b'outside unchanged')
            path.symlink_to(target)
            targets.append(target)
        files = [render.EGG, 'SHA256SUMS', 'notes.md']
        with mock.patch.object(build_release, 'ROOT', repo), \
             mock.patch.object(build_release, 'render', return_value=b'{"fixture": true}\n'), \
             mock.patch.object(build_release, 'candidate_files', return_value=files), \
             mock.patch.object(build_release, 'check_text'), \
             mock.patch.object(build_release, 'scan_git'), \
             mock.patch.object(build_release, 'scan'):
            build_release.build()
        self.assertTrue(all(path.is_file() and not path.is_symlink() for path in generated))
        self.assertTrue(all(path.read_bytes() == b'outside unchanged' for path in targets))

    def test_release_rejects_unsafe_dist_before_writing(self):
        for kind in ('symlink', 'file'):
            with self.subTest(kind=kind):
                repo = self.root / kind
                repo.mkdir()
                egg = repo / render.EGG
                egg.write_bytes(b'original')
                if kind == 'symlink':
                    outside = self.root / 'outside-dist'
                    outside.mkdir(exist_ok=True)
                    (repo / 'dist').symlink_to(outside, target_is_directory=True)
                else:
                    (repo / 'dist').write_text('not a directory')
                with mock.patch.object(build_release, 'ROOT', repo), \
                     mock.patch.object(build_release, 'render', side_effect=AssertionError('wrote first')), \
                     self.assertRaisesRegex(ValueError, 'real directory'):
                    build_release.build()
                self.assertEqual(egg.read_bytes(), b'original')

    def test_git_index_must_exactly_match_public_manifest(self):
        fake = b'100644 ' + b'0' * 40 + b' 0\tEXTRA.md\0'
        with mock.patch.object(scan_public, 'git_output', return_value=fake), self.assertRaisesRegex(
                ValueError, 'exactly match PUBLIC_FILES'):
            scan_public.scan_index(['PUBLIC_FILES'])

    def test_annotated_tag_identity_and_message_are_scanned(self):
        tag_sha = '1' * 40
        target_sha = '2' * 40
        base = (f'object {target_sha}\ntype commit\ntag v1\n'
                'tagger grimreapper <10205216+grimreapper@users.noreply.github.com> 1 +0000\n\n')

        def output_for(data):
            def output(*args):
                if args[0] == 'for-each-ref':
                    return (tag_sha + '\n').encode()
                if args[:2] == ('cat-file', '-t'):
                    return b'tag\n' if args[2] == tag_sha else b'commit\n'
                if args[:2] == ('cat-file', 'tag'):
                    return data
                raise AssertionError(args)
            return output

        with mock.patch.object(scan_public, 'git_output', side_effect=output_for((base + 'release\n').encode())):
            scan_public.scan_annotated_tags()
        bad_identity = base.replace('grimreapper <', 'Someone Else <').encode() + b'release\n'
        with mock.patch.object(scan_public, 'git_output', side_effect=output_for(bad_identity)), \
             self.assertRaisesRegex(ValueError, 'tagger metadata'):
            scan_public.scan_annotated_tags()
        bad_message = (base + '/ho' + 'me/operator/private\n').encode()
        with mock.patch.object(scan_public, 'git_output', side_effect=output_for(bad_message)), \
             self.assertRaisesRegex(ValueError, 'private path'):
            scan_public.scan_annotated_tags()

    def test_renderer_exact_and_embedded_sources(self):
        self.assertEqual((ROOT / render.EGG).read_bytes(), render.render())
        self.assertEqual(render.render(), render.render())
        script = json.loads(render.render())['scripts']['installation']['script']
        for name in render.EMBEDDED:
            delimiter = 'BF2_SOURCE_' + name.replace('.', '_').upper()
            actual = script.split("<<'"+delimiter+"'\n", 1)[1].split('\n'+delimiter+'\n', 1)[0] + '\n'
            self.assertEqual(actual.encode(), (ROOT / 'scripts' / name).read_bytes())
        self.assertNotIn('\r', script)

    def test_embedded_installer_shell_syntax_and_denial(self):
        script = self.root / 'install.sh'
        script.write_text(json.loads(render.render())['scripts']['installation']['script'])
        subprocess.run(['bash', '-n', str(script)], check=True)
        result = subprocess.run(['bash', str(script)], env={'PATH': '/usr/bin:/bin', 'BF2_ROOT': str(self.root)}, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('EA_EULA_ACCEPT=YES', result.stderr)
        self.assertFalse((self.root / 'server').exists())

    def test_embedded_runtime_validator_executed_independently(self):
        code = self.root / 'code'
        code.mkdir()
        script = json.loads(render.render())['scripts']['installation']['script']
        for name in render.EMBEDDED:
            delimiter = 'BF2_SOURCE_' + name.replace('.', '_').upper()
            content = script.split("<<'"+delimiter+"'\n", 1)[1].split('\n'+delimiter+'\n', 1)[0] + '\n'
            (code / name).write_text(content)
        fixture(self.root / 'server')
        probe = "import runtime,os; from pathlib import Path; runtime.settings(Path(os.environ['FIXTURE']),os.environ)"
        for changes, success in [({}, True), ({'MAP_ROTATION': 'wake_island_2007 gpm_coop 16'}, False),
                                 ({'EA_EULA_ACCEPT': 'yes'}, False), ({'SERVER_NAME': 'x\n'}, False),
                                 ({'RCON_ENABLED': '1'}, False), ({'MOD': '../bf2'}, False)]:
            result = subprocess.run([sys.executable, '-B', '-c', probe], cwd=code,
                                    env=env(FIXTURE=str(self.root/'server'), **changes), capture_output=True, timeout=10)
            self.assertEqual(result.returncode == 0, success)

    def test_pin_values_not_configurable(self):
        self.assertEqual(spec.ARCHIVE_SIZE, 330688322)
        self.assertEqual(spec.ARCHIVE_SHA256, '4d849218c1725e7bd6a7e7f164e27b036248f8ded2e30340dd0722c1dfffbab6')
        self.assertEqual(spec.HUB_SIZE, 38980)
        self.assertEqual(spec.HUB_SHA256, 'c4b3d583741c500e930502e96c6a43a40f223868c9ca1111c70d80c7e6d2cd2b')
        self.assertFalse(any('HASH' in key or 'SHA' in key for key in spec.VARIABLES))

    def test_manifest_document_equality(self):
        manifest = json.loads((ROOT / 'data/vanilla-maps.json').read_text())
        rows = re.findall(r'^\| ([a-z0-9_]+) \| ([0-9, -]+) \| ([0-9, -]+) \|$', (ROOT / 'docs/MAPS.md').read_text(), re.M)
        found = {name: sorted([['gpm_cq', int(x)] for x in cq.split(',') if x.strip() != '-'] +
                              [['gpm_coop', int(x)] for x in coop.split(',') if x.strip() != '-']) for name, cq, coop in rows}
        self.assertEqual(len(rows), len(found))
        self.assertEqual(found, manifest)

    def test_source_parsing(self):
        for p in ROOT.rglob('*.py'):
            if '.git' not in p.parts:
                compile(p.read_bytes(), p.name, 'exec')
        for p in list((ROOT/'scripts').glob('*.sh')) + list((ROOT/'container').glob('*.sh')):
            subprocess.run(['bash', '-n', str(p)], check=True)

    def test_privacy_scanner_rejects_sensitive_shapes(self):
        for content in ('/ho'+'me/operator/private', 'gh'+'p_'+'X'*35,
                        '192.168.'+'5.19', 'person'+'@private.invalid',
                        'https://'+'private.invalid/file', '-----BEGIN '+'RSA PRIVATE KEY-----'):
            with self.assertRaises(ValueError):
                scan_public.check_text(content.encode(), 'fixture')
        scan_public.check_text(
            b'community@example.invalid 10205216+grimreapper@users.noreply.github.com 0.0.0.0',
            'fixture',
        )
        self.assertEqual(
            scan_public.ALLOWED_GIT_IDENTITIES,
            {
                'BF2 Egg Contributors <community@example.invalid>',
                'grimreapper <10205216+grimreapper@users.noreply.github.com>',
            },
        )


if __name__ == '__main__':
    unittest.main()
