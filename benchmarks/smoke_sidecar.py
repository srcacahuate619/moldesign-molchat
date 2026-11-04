"""Start the installed sidecar and verify its real loopback HTTP health endpoint.

The fake provider needs no credentials. The standalone session printed by the
child is discarded, never captured in a log or result artifact.
"""
from __future__ import annotations

import json
import os
import socket
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


def main() -> None:
    with tempfile.TemporaryDirectory(prefix='molchat-sidecar-smoke-') as temporary:
        root = Path(temporary)
        env = {**os.environ, 'MOLCHAT_PROVIDER': 'fake', 'MOLCHAT_HOST_SECRET': '',
               'MOLCHAT_MEMORY_FILE': str(root / 'memory.db'),
               'MOLCHAT_EXEC_STORE': str(root / 'executions.db'),
               'MOLCHAT_CONSENTS_FILE': str(root / 'consents.json')}
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        child = subprocess.Popen([sys.executable, '-m', 'molchat_agent', 'serve',
                                  '--host', '127.0.0.1', '--port', str(port)],
                                 env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if child.poll() is not None:
                    raise RuntimeError('The sidecar exited before becoming healthy.')
                try:
                    with opener.open(f'http://127.0.0.1:{port}/v1/health', timeout=1) as response:
                        health = json.load(response)
                    if health.get('status') != 'ok' or health.get('contract') != 'moldesign.molchat/1':
                        raise RuntimeError('Unexpected sidecar health contract.')
                    print(json.dumps({'passed': True, 'provider': 'fake', 'health': health,
                                      'host': '127.0.0.1', 'port': port, 'session_output_discarded': True}))
                    return
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(.1)
            raise RuntimeError('The sidecar did not become healthy within 20 seconds.')
        finally:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


if __name__ == '__main__':
    main()
