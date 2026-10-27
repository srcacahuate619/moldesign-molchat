"""Vendored entry point: ``python -m molchat_agent`` must work (6.1)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_module_entry_exposes_the_cli():
    import os

    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    completed = subprocess.run(
        [sys.executable, "-m", "molchat_agent", "--help"],
        capture_output=True, text=True, check=False, cwd=ROOT, env=env)
    assert completed.returncode == 0, completed.stderr
    assert "molchat-agent" in completed.stdout or "usage" in completed.stdout.lower()
