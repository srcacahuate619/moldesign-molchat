"""The Fase 0 gates must prove they can see (supervisor probes, PLAN §26.3).

These tests scaffold a miniature repo in ``tmp_path``, copy the real checker
scripts into it, and run them as subprocesses — the same way CI will.
Fixture payloads are assembled at runtime so that this file itself stays
clean under ``scripts/check_secrets.py``.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
REFERENCE_COMMIT = "66ff524334267c56558b7a3cce94cb919edbad2e"
BS = chr(92)  # backslash, kept out of literals on purpose

_ENTRY = """### {path}

- Origen: código nuevo en este repositorio
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo
- Licencia resultante: GPL-3.0-or-later
- Tests: suite general
"""

LEDGER = "# Procedencia\n\nCommit de referencia: `" + REFERENCE_COMMIT + "`\n\n" + "".join(
    _ENTRY.format(path=p)
    for p in ("src/pkg/mod.py", "scripts/check_secrets.py", "scripts/check_provenance.py")
)


def _assign(name: str, value: str) -> str:
    return f"{name} = '{value}'\n"


def _scaffold(tmp_path: Path, files: dict[str, str]) -> Path:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("check_secrets.py", "check_provenance.py"):
        shutil.copy(SCRIPTS / name, scripts / name)
    for rel, content in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return tmp_path


def _run(base: Path, script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(base / "scripts" / script)],
        capture_output=True, text=True, check=False,
    )


def test_secrets_accepts_clean_tree(tmp_path):
    base = _scaffold(tmp_path, {"src/pkg/mod.py": "VALUE = 1\n"})
    result = _run(base, "check_secrets.py")
    assert result.returncode == 0, result.stdout


def test_secrets_allows_dummy_prefixed_fixture(tmp_path):
    base = _scaffold(tmp_path, {"src/pkg/mod.py": _assign("token", "test" + "-key")})
    result = _run(base, "check_secrets.py")
    assert result.returncode == 0, result.stdout


def test_secrets_flags_buried_dummy_marker(tmp_path):
    buried = "a1b2c3" + "secret" + "value99"
    base = _scaffold(tmp_path, {"src/pkg/mod.py": _assign("token", buried)})
    result = _run(base, "check_secrets.py")
    assert result.returncode == 1
    assert "credential-like assignment" in result.stdout


def test_secrets_flags_known_prefix_and_private_key(tmp_path):
    content = _assign("api_key", "sk" + "-live-abcdef1234567890")
    content += _assign("KEY", "-----BEGIN PRIVATE " + "KEY-----")
    base = _scaffold(tmp_path, {"src/pkg/mod.py": content})
    result = _run(base, "check_secrets.py")
    assert result.returncode == 1
    assert "known credential prefix" in result.stdout
    assert "private key block" in result.stdout


def test_secrets_flags_drive_paths_and_unc(tmp_path):
    lines = [
        _assign("A", "D" + ":/moldesign-build/backend"),
        _assign("B", "D:" + BS + "moldesign-build" + BS + "backend"),
        _assign("C", BS * 4 + "server" + BS * 2 + "share" + BS * 2 + "x"),
        _assign("D", BS * 2 + "server" + BS + "share" + BS + "x"),
    ]
    base = _scaffold(tmp_path, {"src/pkg/mod.py": "".join(lines)})
    result = _run(base, "check_secrets.py")
    assert result.returncode == 1
    assert result.stdout.count("machine-local path") == 4, result.stdout


def test_secrets_ignores_js_unicode_escapes(tmp_path):
    escapes = BS * 2 + "u00C0-" + BS * 2 + "u00D6" + BS * 2 + "u00D8"
    tail = BS * 2 + "uFFFD" + BS * 2 + "-.0-9" + BS * 2 + "u00B7"
    base = _scaffold(tmp_path, {"src/pkg/mod.py": f"var r='{escapes}{tail}';\n"})
    result = _run(base, "check_secrets.py")
    assert result.returncode == 0, result.stdout


def test_secrets_scans_nested_plan_but_not_root_plan(tmp_path):
    payload = _assign("password", "correcthorsebatterystaple1")
    base = _scaffold(tmp_path, {"PLAN.md": payload, "sub/PLAN.md": payload})
    result = _run(base, "check_secrets.py")
    assert result.returncode == 1
    assert "sub/PLAN.md" in result.stdout
    assert "\n  - PLAN.md:" not in result.stdout


def test_provenance_accepts_covered_tree(tmp_path):
    base = _scaffold(tmp_path, {
        "PROVENANCE.md": LEDGER,
        "src/pkg/mod.py": "VALUE = 1\n",
    })
    result = _run(base, "check_provenance.py")
    assert result.returncode == 0, result.stdout


def test_provenance_flags_uncovered_file(tmp_path):
    base = _scaffold(tmp_path, {
        "PROVENANCE.md": LEDGER,
        "src/pkg/mod.py": "VALUE = 1\n",
        "src/pkg/extra.py": "VALUE = 2\n",
    })
    result = _run(base, "check_provenance.py")
    assert result.returncode == 1
    assert "uncovered file: src/pkg/extra.py" in result.stdout


def test_provenance_flags_uncovered_conformance_file(tmp_path):
    base = _scaffold(tmp_path, {
        "PROVENANCE.md": LEDGER,
        "src/pkg/mod.py": "VALUE = 1\n",
        "conformance/runner.py": "VALUE = 2\n",
    })
    result = _run(base, "check_provenance.py")
    assert result.returncode == 1
    assert "uncovered file: conformance/runner.py" in result.stdout


def test_provenance_flags_wrong_license(tmp_path):
    ledger = LEDGER.replace("-or-later", "-only")
    base = _scaffold(tmp_path, {
        "PROVENANCE.md": ledger,
        "src/pkg/mod.py": "VALUE = 1\n",
    })
    result = _run(base, "check_provenance.py")
    assert result.returncode == 1
    assert "unexpected license" in result.stdout


def _scaffold_ui(tmp_path: Path, *, built: bool, stale: bool) -> Path:
    import time

    scripts = tmp_path / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy(SCRIPTS / "check_ui_build.py", scripts / "check_ui_build.py")
    src = tmp_path / "ui" / "src"
    src.mkdir(parents=True)
    (src / "app.tsx").write_text("export {}\n", encoding="utf-8")
    if built:
        dist = tmp_path / "ui" / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html></html>", encoding="utf-8")
        if stale:
            old = (dist / "index.html").stat().st_mtime - 60
            import os

            os.utime(dist / "index.html", (old, old))
            time.sleep(0.01)
    return tmp_path


def test_ui_build_accepts_fresh_dist(tmp_path):
    base = _scaffold_ui(tmp_path, built=True, stale=False)
    result = _run(base, "check_ui_build.py")
    assert result.returncode == 0, result.stdout


def test_ui_build_flags_missing_and_stale(tmp_path):
    base = _scaffold_ui(tmp_path, built=False, stale=False)
    result = _run(base, "check_ui_build.py")
    assert result.returncode == 1
    assert "MISSING" in result.stdout
    base = _scaffold_ui(tmp_path / "stale", built=True, stale=True)
    result = _run(base, "check_ui_build.py")
    assert result.returncode == 1
    assert "STALE" in result.stdout
