"""Bounded process lifecycle tests using original synthetic children only."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent


class Supervisor(unittest.TestCase):
    def start(self, child, prefix=''):
        code = ("import sys;sys.path.insert(0," + repr(str(ROOT/'container')) + ");import supervise;" +
                prefix + "sys.exit(supervise.run([sys.executable,'-u','-c'," + repr(child) + "],grace=0.2))")
        p = subprocess.Popen([sys.executable, '-B', '-u', '-c', code], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: p.kill() if p.poll() is None else None)
        return p

    def finish(self, p, expected=None):
        out, err = p.communicate(timeout=5)
        if expected is not None:
            self.assertEqual(p.returncode, expected, err)
        return out, err

    def test_natural_status_preserved(self):
        p = self.start('raise SystemExit(7)')
        self.finish(p, 7)

    def test_console_stop(self):
        p = self.start("import signal,time;signal.signal(signal.SIGINT,lambda a,b:exit(0));print('ready',flush=True);time.sleep(30)")
        self.assertEqual(p.stdout.readline().strip(), 'ready')
        p.stdin.write('^C\n'); p.stdin.flush()
        self.finish(p, 0)

    def test_signal_after_ready(self):
        for signum in (signal.SIGINT, signal.SIGTERM):
            p = self.start("import signal,time;signal.signal(signal.SIGINT,lambda a,b:exit(0));signal.signal(signal.SIGTERM,lambda a,b:exit(0));print('ready',flush=True);time.sleep(30)")
            self.assertEqual(p.stdout.readline().strip(), 'ready')
            p.send_signal(signum)
            self.finish(p, 0)

    def test_console_forwarded_without_shell(self):
        p = self.start("import sys;print(sys.stdin.readline().strip(),flush=True)")
        p.stdin.write('plain command\n'); p.stdin.flush()
        out, _ = self.finish(p, 0)
        self.assertEqual(out.strip(), 'plain command')

    def test_ignored_signals_force_bounded_kill(self):
        p = self.start("import signal,time;signal.signal(signal.SIGINT,signal.SIG_IGN);signal.signal(signal.SIGTERM,signal.SIG_IGN);print('ready',flush=True);time.sleep(30)")
        p.stdout.readline()
        p.send_signal(signal.SIGINT)
        self.finish(p, 137)

    def test_descendants_outlive_leader(self):
        child = ("import subprocess,sys;subprocess.Popen([sys.executable,'-c',"
                 "'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)']);raise SystemExit(9)")
        p = self.start(child)
        self.finish(p, 9)

    def test_stop_not_blocked_by_child_ignoring_stdin(self):
        p = self.start("import signal,time;signal.signal(signal.SIGINT,lambda a,b:exit(0));print('ready',flush=True);time.sleep(30)")
        self.assertEqual(p.stdout.readline().strip(), 'ready')
        for _ in range(40):
            p.stdin.write('x' * 4000 + '\n')
            p.stdin.flush()
        p.stdin.write('^C\n'); p.stdin.flush()
        self.finish(p, 0)

    def test_signal_after_group_before_ready(self):
        # The marker precedes readiness and the signal handler is already installed.
        p = self.start("import signal,time;signal.signal(signal.SIGTERM,lambda a,b:exit(0));print('starting',flush=True);time.sleep(30);print('ready')")
        self.assertEqual(p.stdout.readline().strip(), 'starting')
        p.send_signal(signal.SIGTERM)
        out, _ = self.finish(p, 0)
        self.assertNotIn('ready', out)

    def test_signal_during_spawn(self):
        # Deliver SIGTERM while Popen waits for child exec (before the parent sees a PID).
        prefix = ("import os,signal,threading,time; original=supervise.subprocess.Popen;"
                  "supervise.subprocess.Popen=lambda *a,**k: original(*a,**k,preexec_fn=lambda:time.sleep(0.15));"
                  "threading.Timer(0.05,lambda:os.kill(os.getpid(),signal.SIGTERM)).start();")
        p = self.start('import time;time.sleep(30)', prefix)
        self.finish(p)
        self.assertNotEqual(p.returncode, 0)

    def test_signal_before_spawn(self):
        prefix = ("import signal; original=supervise.signal.signal; "
                  "supervise.signal.signal=lambda n,h: (original(n,h),h(signal.SIGTERM,None))[0] if getattr(h,'__name__','')=='request' else original(n,h);")
        p = self.start("raise RuntimeError('must not spawn')", prefix)
        out, err = self.finish(p, 143)
        self.assertNotIn('must not spawn', err)


if __name__ == '__main__':
    unittest.main()
