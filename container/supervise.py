"""Supervise one process group and forward bounded console input."""
import os
import selectors
import signal
import subprocess
import sys
import time


def run(argv, grace=5.0):
    pending = [None]
    child = None
    selector = selectors.DefaultSelector()
    old = {}

    def request(signum, _frame):
        if pending[0] is None:
            pending[0] = signum

    for signum in (signal.SIGINT, signal.SIGTERM):
        old[signum] = signal.signal(signum, request)
    deadline = None
    phase = 0
    leader_status = None
    buffer = b''
    output = bytearray()

    def group_signal(signum):
        # Popen returns only after setsid and exec; child.pid is now a safe PGID.
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass

    def group_alive():
        try:
            os.killpg(child.pid, 0)
            return True
        except ProcessLookupError:
            return False

    try:
        if pending[0] is not None:
            return 128 + pending[0]
        child = subprocess.Popen(argv, stdin=subprocess.PIPE, start_new_session=True)
        os.set_blocking(child.stdin.fileno(), False)
        # Handlers were active throughout spawn. Honor any signal received during Popen.
        try:
            selector.register(sys.stdin, selectors.EVENT_READ)
        except (OSError, ValueError):
            pass
        while True:
            status = child.poll()  # Reap the leader before checking residual descendants.
            if status is not None and leader_status is None:
                leader_status = status
                if pending[0] is None:
                    pending[0] = signal.SIGTERM
            if pending[0] is not None and deadline is None:
                group_signal(pending[0])
                deadline = time.monotonic() + grace
            if leader_status is not None and not group_alive():
                return leader_status if leader_status >= 0 else 128 - leader_status
            if deadline is not None and time.monotonic() >= deadline:
                if phase == 0:
                    group_signal(signal.SIGTERM)
                    phase = 1
                    deadline = time.monotonic() + grace
                else:
                    group_signal(signal.SIGKILL)
                    # Bounded cleanup even if container PID 1 has not reaped orphan zombies.
                    status = child.wait(timeout=grace)
                    code = leader_status if leader_status is not None else status
                    return code if code >= 0 else 128 - code
            if output and pending[0] is None:
                try:
                    sent = os.write(child.stdin.fileno(), output)
                    del output[:sent]
                except BlockingIOError:
                    pass
                except BrokenPipeError:
                    output.clear()
            for key, _ in selector.select(0.05):
                data = os.read(key.fd, 4096)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                buffer += data
                if len(buffer) > 8192:
                    buffer = b''
                    continue
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    if line.strip() == b'^C':
                        request(signal.SIGINT, None)
                    elif pending[0] is None and child.poll() is None:
                        # Only bounded console lines; no shell evaluation.
                        if len(output) + len(line) < 65536:
                            output.extend(line + b'\n')
    finally:
        selector.close()
        if child is not None:
            if child.poll() is None:
                group_signal(signal.SIGKILL)
                child.wait(timeout=grace)
            child.stdin.close()
        for signum, handler in old.items():
            signal.signal(signum, handler)


if __name__ == '__main__':
    os.chdir('/home/container')
    sys.exit(run(['/bin/bash', 'server/egg/start.sh']))
