"""Manifest producer (6.1): what ships, from which commit, and its integrity.

Pure-function tests import the real script; git integration scaffolds a
miniature repo in ``tmp_path`` (skipped where git is missing). Payloads that
must trip the detectors are assembled at runtime so this file itself stays
clean under ``scripts/check_secrets.py``.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BS = chr(92)  # backslash, kept out of literals on purpose


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "make_manifest_under_test", ROOT / "scripts" / "make_manifest.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


mm = _load_script()
NEEDS_GIT = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(repo), *args],
                               capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def _leak(value: str) -> str:
    """A credential-like assignment assembled at runtime (keeps this file clean)."""
    name = "api" + "_key"
    return f"{name} = '{value}'\n"


def _scaffold_repo(base: Path, *, version="0.1.0", extra=None) -> Path:
    """A miniature committable source repo with a fresh UI build."""
    repo = base / "source"
    (repo / "src" / "molchat_agent" / "server").mkdir(parents=True)
    (repo / "LICENSE").write_bytes(
        (ROOT / "LICENSE").read_bytes().replace(b"\r\n", b"\n"))
    (repo / "NOTICE.md").write_text("# Notice\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        f"[project]\nname = 'mini'\nversion = '{version}'\n"
        "requires-python = '>=3.11'\ndependencies = ['httpx>=0.27,<1']\n"
        "[project.optional-dependencies]\nserver = ['uvicorn>=0.29,<1']\n",
        encoding="utf-8")
    pkg = repo / "src" / "molchat_agent"
    (pkg / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    (pkg / "__main__.py").write_text("print('sidecar')\n", encoding="utf-8")
    (pkg / "cli.py").write_text("VALUE = 1\n", encoding="utf-8")
    (pkg / "server" / "serve.py").write_text("VALUE = 2\n", encoding="utf-8")
    (pkg / "server" / "app.py").write_text("VALUE = 3\n", encoding="utf-8")
    (repo / "ui" / "src").mkdir(parents=True)
    (repo / "ui" / "src" / "app.ts").write_text("export {}\n", encoding="utf-8")
    (repo / "ui" / "dist").mkdir(parents=True)
    (repo / "ui" / "dist" / "index.html").write_text("<html></html>",
                                                    encoding="utf-8")
    for rel, content in (extra or {}).items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "mini")
    return repo


# --- pure functions: no git needed ------------------------------------------------


def test_set_fingerprint_moves_with_bytes_names_and_list():
    base = {"b.py": {"bytes": 1, "sha256": "a" * 64},
            "a.py": {"bytes": 2, "sha256": "b" * 64}}
    assert mm.sha256_conjunto(base) == mm.sha256_conjunto(
        {"a.py": base["a.py"], "b.py": base["b.py"]})  # order-free
    tampered = dict(base, **{"a.py": {"bytes": 2, "sha256": "c" * 64}})
    assert mm.sha256_conjunto(tampered) != mm.sha256_conjunto(base)
    assert mm.sha256_conjunto({**base, "c.py": base["a.py"]}) != \
        mm.sha256_conjunto(base)


def test_manifest_shape_carries_contract_and_exclusions():
    content = {"LICENSE": b"x", "src/molchat_agent/__init__.py": b"y"}
    manifest = mm.construir_manifiesto(
        content, {"commit": "c" * 40, "rama": "main"}, "0.1.0",
        {"python": ">=3.11", "dependencias": ["httpx"]})
    assert manifest["schema"] == "moldesign.molchat/1"
    assert manifest["version"] == "0.1.0"
    assert manifest["contrato"] == {"agente_plataforma": "moldesign.molchat/1"}
    assert "min_moldesign" not in manifest["contrato"]  # none released yet
    assert any("conformance" in e for e in manifest["excluidos"])
    assert manifest["archivos"]["LICENSE"]["bytes"] == 1
    assert manifest["sha256_conjunto"] == mm.sha256_conjunto(manifest["archivos"])
    with_minimum = mm.construir_manifiesto(
        content, {"commit": "c" * 40, "rama": "main"}, "0.1.0",
        {"python": ">=3.11", "dependencias": []}, "9.9.9")
    assert with_minimum["contrato"]["min_moldesign"] == "9.9.9"


def test_verify_lists_every_integrity_break(tmp_path):
    staged = tmp_path / "copy"
    (staged / "src").mkdir(parents=True)
    assert mm.verificar(staged) == [
        "falta molchat-manifest.json: no es una copia MolChat vendorizada"]
    (staged / "molchat-manifest.json").write_text("no json", encoding="utf-8")
    assert mm.verificar(staged)[0].startswith("manifiesto ilegible")
    (staged / "molchat-manifest.json").write_text("[]", encoding="utf-8")
    assert mm.verificar(staged) == ["el manifiesto no es un objeto JSON"]


def test_verify_catches_missing_extra_and_tampered(tmp_path):
    staged = tmp_path / "copy"
    (staged / "src").mkdir(parents=True)
    payload = b"VALUE = 1\n"
    archivos = {"src/a.py": {"bytes": len(payload),
                             "sha256": mm.sha256_bytes(payload)}}
    manifest = {"schema": mm.ESQUEMA, "programa": "p", "version": "0.1.0",
                "licencia_spdx": mm.LICENCIA_SPDX, "licencia_texto": "LICENSE",
                "fuente": {"proyecto": "moldesign-molchat", "commit": "c" * 40,
                           "rama": "main"},
                "invocacion": "i", "no_se_enlaza": "n",
                "contrato": {"agente_plataforma": mm.CONTRATO},
                "requisitos": {"python": ">=3.11", "dependencias": []},
                "excluidos": [], "archivos": archivos,
                "sha256_conjunto": mm.sha256_conjunto(archivos)}
    (staged / "molchat-manifest.json").write_text(json.dumps(manifest),
                                                  encoding="utf-8")
    assert mm.verificar(staged) == ["falta src/a.py"]
    (staged / "src" / "a.py").write_bytes(payload)
    (staged / "src" / "stowaway.py").write_bytes(b"x\n")
    assert mm.verificar(staged) == ["sobra src/stowaway.py"]
    (staged / "src" / "stowaway.py").unlink()
    (staged / "src" / "a.py").write_bytes(b"VALUE = 2\n")
    assert mm.verificar(staged) == ["src/a.py: no coincide con su manifiesto"]


def test_verify_ignores_interpreter_bytecode_only(tmp_path):
    staged = tmp_path / "copy"
    (staged / "src" / "__pycache__").mkdir(parents=True)
    manifest = {"schema": mm.ESQUEMA, "programa": "p", "version": "0.1.0",
                "licencia_spdx": mm.LICENCIA_SPDX, "licencia_texto": "LICENSE",
                "fuente": {"proyecto": "moldesign-molchat", "commit": "c" * 40,
                           "rama": "main"},
                "invocacion": "i", "no_se_enlaza": "n",
                "contrato": {"agente_plataforma": mm.CONTRATO},
                "requisitos": {"python": ">=3.11", "dependencias": []},
                "excluidos": [], "archivos": {},
                "sha256_conjunto": mm.sha256_conjunto({})}
    manifest["archivos"] = {"src/a.py": {"bytes": 10, "sha256": "d" * 64}}
    manifest["sha256_conjunto"] = mm.sha256_conjunto(manifest["archivos"])
    (staged / "molchat-manifest.json").write_text(json.dumps(manifest),
                                                  encoding="utf-8")
    (staged / "src" / "__pycache__" / "a.pyc").write_bytes(b"bytecode")
    assert mm.verificar(staged) == ["falta src/a.py"]  # the .pyc never counts


def test_verify_rejects_edited_manifest(tmp_path):
    staged = tmp_path / "copy"
    payload = b"VALUE = 1\n"
    archivos = {"a.py": {"bytes": len(payload), "sha256": mm.sha256_bytes(payload)}}
    (staged).mkdir()
    (staged / "a.py").write_bytes(payload)
    manifest = {"schema": mm.ESQUEMA, "programa": "p", "version": "0.1.0",
                "licencia_spdx": mm.LICENCIA_SPDX, "licencia_texto": "LICENSE",
                "fuente": {"proyecto": "moldesign-molchat", "commit": "c" * 40,
                           "rama": "main"},
                "invocacion": "i", "no_se_enlaza": "n",
                "contrato": {"agente_plataforma": mm.CONTRATO},
                "requisitos": {"python": ">=3.11", "dependencias": []},
                "excluidos": [], "archivos": archivos,
                "sha256_conjunto": "0" * 64}  # hand-edited
    (staged / "molchat-manifest.json").write_text(json.dumps(manifest),
                                                  encoding="utf-8")
    assert mm.verificar(staged) == [
        "sha256_conjunto no recomputa: el manifiesto fue editado"]


def test_content_problems_see_license_paths_and_secrets(tmp_path):
    gpl = (ROOT / "LICENSE").read_bytes().replace(b"\r\n", b"\n")
    assert mm.problemas_de_contenido({"LICENSE": gpl}) == [
        f"falta {p}" for p in mm.INDISPENSABLES if p != "LICENSE"]
    assert any("GPL-3.0-or-later" in p for p in mm.problemas_de_contenido(
        {"LICENSE": b"not the license"}))
    drive = "C" + ":/tools/blender.exe"
    unc = BS * 2 + "server" + BS + "share"
    errors = mm.problemas_de_contenido(
        {"LICENSE": gpl, "src/molchat_agent/x.py":
            f"a = '{drive}'\nb = '{unc}'\n".encode("utf-8")})
    assert sum("concreta" in e for e in errors) == 2, errors
    leaked = "sk" + "-live-abcdef1234567890"
    errors = mm.problemas_de_contenido(
        {"LICENSE": gpl, "src/molchat_agent/y.py":
            _leak(leaked).encode("utf-8")})
    assert any("known credential prefix" in e for e in errors), errors
    assert not [e for e in mm.problemas_de_contenido(
        {"LICENSE": gpl, "src/molchat_agent/z.py":
            b"api_key = 'test-key'\n"}) if "credential" in e or "prefix" in e]


def test_schema_file_matches_script_shape():
    schema = json.loads((ROOT / "packaging" / "molchat-manifest.schema.json")
                        .read_text(encoding="utf-8"))
    assert tuple(schema["required"]) == mm.MANIFIESTO_REQUERIDO
    assert schema["properties"]["schema"]["const"] == mm.ESQUEMA
    assert schema["properties"]["licencia_spdx"]["const"] == mm.LICENCIA_SPDX
    assert schema["properties"]["contrato"]["properties"][
        "agente_plataforma"]["const"] == mm.CONTRATO


# --- git integration -----------------------------------------------------------------


@NEEDS_GIT
def test_write_then_check_roundtrip(tmp_path):
    repo = _scaffold_repo(tmp_path)
    out = tmp_path / "vendored"
    manifest = mm.escribir(repo, out)
    assert manifest["version"] == "0.1.0"
    assert manifest["fuente"]["commit"] == _git(repo, "rev-parse", "HEAD")
    assert "repositorio" not in manifest["fuente"]  # no origin in scaffold
    assert manifest["requisitos"]["dependencias"] == [
        "httpx>=0.27,<1", "uvicorn>=0.29,<1 (extra server)"]
    assert "src/molchat_agent/cli.py" in manifest["archivos"]
    assert "ui/dist/index.html" in manifest["archivos"]
    assert "ui/src/app.ts" not in manifest["archivos"]  # sources never ship
    assert mm.verificar(out) == []
    assert mm.main(["--check", str(out)]) == 0


@NEEDS_GIT
def test_write_refuses_dirty_tree(tmp_path):
    repo = _scaffold_repo(tmp_path)
    with (repo / "src" / "molchat_agent" / "cli.py").open("a", encoding="utf-8") as fh:
        fh.write("# uncommitted\n")
    with pytest.raises(SystemExit, match="sin commitear"):
        mm.escribir(repo, tmp_path / "out")


@NEEDS_GIT
def test_write_refuses_dirty_ui_sources(tmp_path):
    repo = _scaffold_repo(tmp_path)
    with (repo / "ui" / "src" / "app.ts").open("a", encoding="utf-8") as fh:
        fh.write("// uncommitted\n")
    with pytest.raises(SystemExit, match="sin commitear"):
        mm.escribir(repo, tmp_path / "out")


@NEEDS_GIT
def test_write_refuses_stale_and_missing_build(tmp_path):
    repo = _scaffold_repo(tmp_path)
    index = repo / "ui" / "dist" / "index.html"
    old = index.stat().st_mtime - 60
    os.utime(index, (old, old))
    with pytest.raises(SystemExit, match="anterior a sus fuentes"):
        mm.escribir(repo, tmp_path / "out")
    shutil.rmtree(repo / "ui" / "dist")
    with pytest.raises(SystemExit, match="falta ui/dist/index.html"):
        mm.escribir(repo, tmp_path / "out2")


@NEEDS_GIT
def test_write_refuses_machine_path_secret_and_version_split(tmp_path):
    drive = "D" + ":/moldesign-build/backend"
    repo = _scaffold_repo(tmp_path, extra={
        "src/molchat_agent/leak.py": f"path = '{drive}'\n"})
    with pytest.raises(SystemExit, match="concreta"):
        mm.escribir(repo, tmp_path / "out")
    leaked = "sk" + "-live-abcdef1234567890"
    repo = _scaffold_repo(tmp_path / "s2", extra={
        "src/molchat_agent/leak.py": _leak(leaked)})
    with pytest.raises(SystemExit, match="known credential prefix"):
        mm.escribir(repo, tmp_path / "out2")
    repo = _scaffold_repo(tmp_path / "s3")
    (repo / "src" / "molchat_agent" / "__init__.py").write_text(
        '__version__ = "9.9.9"\n', encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "split")
    with pytest.raises(SystemExit, match="no coincide"):
        mm.escribir(repo, tmp_path / "out3")


@NEEDS_GIT
def test_write_refuses_foreign_target_dir(tmp_path):
    repo = _scaffold_repo(tmp_path)
    foreign = tmp_path / "out"
    foreign.mkdir()
    (foreign / "notes.txt").write_text("mine\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="no la borro"):
        mm.escribir(repo, foreign)
