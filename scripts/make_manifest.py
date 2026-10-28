#!/usr/bin/env python3
r"""Produce the vendorizable MolChat copy and its manifest (PLAN Fase 6, 6.1).

# What travels and why

MolChat is an independent program (GPL-3.0-or-later) that MolDesign runs as a
sidecar process, never imports: the exact Molcy pattern
(``stage_molcy_motor.py`` + ``motor.py`` + ``molcy-manifest.json`` in
MolDesign, used here as the compass). This script is the producer side: it
materializes, from a clean commit, the directory the MolDesign host stages
under ``tools/molchat/``.

SHIPS: the ``molchat_agent`` package (the sidecar), the built UI
(``ui/dist/``), ``LICENSE``, ``NOTICE.md`` and ``pyproject.toml`` (so the
host knows the interpreter and dependency requirements).
NEVER SHIPS: tests, ``conformance/``, ``examples/``, development docs and
scripts, the internal plan, credentials, or local model weights (downloaded,
not vendored). The manifest documents every exclusion with its reason.

# Where the bytes come from

Tracked files are read as git BLOBS from a commit (``git show
<commit>:<path>``), never from the worktree: line endings and stray edits
must not leak into what is distributed. The tree must be clean in everything
that ships (tracked sources and UI sources alike); the commit is vendored,
not the working tree.

``ui/dist/`` is the honest exception: it is a build artifact, git-ignored by
design, so no commit carries it. Its bytes are taken from disk only when the
build is present and FRESH (no UI source newer than the bundle, the same
rule as ``check_ui_build.py``) and the UI sources are committed. A stale or
uncommitted UI refuses to ship instead of shipping a silent mismatch.

# What is verified

On ``--write`` and on ``--check`` alike: every indispensable file is
present, ``LICENSE`` is exactly the GPL-3.0-or-later text (hash over
LF-normalized bytes), no shipped code carries a machine-local path or a
secret (the single detector implementation in ``check_secrets.py``, loaded
by path), and the package version is one value in both places it is
declared (``pyproject.toml`` and ``__init__.py``).

On ``--check`` additionally: the directory holds EXACTLY the files the
manifest declares (no more, no fewer), each with its byte count and
SHA-256, the set fingerprint recomputes, and the manifest carries every key
that ``packaging/molchat-manifest.schema.json`` requires.

# Usage

    python scripts/make_manifest.py --write [--out dist/molchat-vendorizable]
    python scripts/make_manifest.py --check dist/molchat-vendorizable
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOMBRE_MANIFIESTO = "molchat-manifest.json"
ESQUEMA = "moldesign.molchat/1"
CONTRATO = "moldesign.molchat/1"
LICENCIA_SPDX = "GPL-3.0-or-later"
#: SHA-256 of the GPL-3.0-or-later text with LF endings (same reference text
#: the Molcy staging script pins; a fact about the license, not our bytes).
SHA256_GPL3_LF = "8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903"

#: Tracked files that ship, read as blobs from the commit.
INCLUIR_ARCHIVOS = ("LICENSE", "NOTICE.md", "pyproject.toml")
#: Tracked folders that ship whole (every tracked file under them).
INCLUIR_CARPETAS = ("src/molchat_agent/",)
#: Build output that ships from disk (git-ignored): verified fresh, never stale.
UI_DIST = "ui/dist/"
#: UI sources: must be committed AND older than the bundle, or nothing ships.
UI_FUENTES = ("src", "index.html", "package.json", "vite.config.ts", "tsconfig.json")
#: What the MolDesign host requires to launch and mount the sidecar.
INDISPENSABLES = (
    "LICENSE", "NOTICE.md", "pyproject.toml",
    "src/molchat_agent/__init__.py",
    "src/molchat_agent/__main__.py",
    "src/molchat_agent/cli.py",
    "src/molchat_agent/server/serve.py",
    "src/molchat_agent/server/app.py",
    "ui/dist/index.html",
)
EXCLUIDOS_DOCUMENTADOS = (
    "tests/ (the repo suite travels in the source repo, not in the product)",
    "conformance/ (the adapter kit lives in the source repo)",
    "examples/ (third-party guides, not runtime)",
    "docs/, scripts/, packaging/ (development material, not runtime)",
    "PLAN.md (internal planning, git-ignored)",
    "ui/ sources (only the built bundle ships)",
    "local model weights (downloaded by the operator, never vendored)",
)
#: Suffixes scanned for machine-local paths and secrets.
SUFIJOS_DE_CODIGO = {".py", ".ps1", ".sh", ".js", ".html", ".css", ".json", ".toml", ".md"}

#: Top-level manifest keys (mirrors packaging/molchat-manifest.schema.json;
#: a test keeps both in sync).
MANIFIESTO_REQUERIDO = (
    "schema", "programa", "version", "licencia_spdx", "licencia_texto",
    "fuente", "invocacion", "no_se_enlaza", "contrato", "requisitos",
    "excluidos", "archivos", "sha256_conjunto",
)


def _cargar_detectores():
    """``check_secrets.py`` by path, without importing the scripts package.

    The ONLY implementation of "what a secret or machine path looks like":
    the repo gate and the manifest producer share it so they cannot drift.
    Missing detectors are fatal: shipping without the secret scan is not an
    option that fails open.
    """
    ruta = Path(__file__).resolve().parent / "check_secrets.py"
    if not ruta.is_file():
        raise SystemExit(f"sin {ruta.name} no hay escaneo de secretos; no se distribuye")
    spec = importlib.util.spec_from_file_location("molchat_check_secrets", ruta)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


_detectores = _cargar_detectores()


def sha256_bytes(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def sha256_conjunto(archivos: dict[str, dict]) -> str:
    """Set fingerprint over sorted paths and hashes (same construction the
    Molcy verifier uses, so both manifests mean the same thing)."""
    cuerpo = "".join(f"{ruta}\0{archivos[ruta]['sha256']}\n" for ruta in sorted(archivos))
    return sha256_bytes(cuerpo.encode("utf-8"))


def _git(fuente: Path, *args: str, texto: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(fuente), *args],
                          capture_output=True, text=texto, check=False)


def _es_vendorizado(ruta: str) -> bool:
    return ruta in INCLUIR_ARCHIVOS or ruta.startswith(INCLUIR_CARPETAS)


def repositorio_publico(fuente: Path) -> str | None:
    """``origin`` URL WITHOUT credentials (the GPL asks that the source be
    obtainable: the manifest says where). Local paths and ssh remotes are
    not a public source offer, so they yield None."""
    import urllib.parse

    salida = _git(fuente, "remote", "get-url", "origin")
    if salida.returncode != 0 or not salida.stdout.strip():
        return None
    partes = urllib.parse.urlsplit(salida.stdout.strip())
    if partes.scheme not in {"http", "https"} or not partes.hostname:
        return None
    anfitrion = partes.hostname + (f":{partes.port}" if partes.port else "")
    return urllib.parse.urlunsplit(
        (partes.scheme, anfitrion, partes.path.removesuffix(".git"), "", ""))


def leer_del_commit(fuente: Path) -> tuple[dict[str, bytes], dict[str, str]]:
    """Blobs at HEAD of ``fuente`` (only what ships) and where they come from.

    Aborts when the tree is dirty in anything that ships: the COMMIT is
    vendored, and a dirty tree would hide what the owner sees on disk.
    """
    commit = _git(fuente, "rev-parse", "HEAD")
    if commit.returncode != 0:
        raise SystemExit(f"{fuente} no es un repositorio git: {commit.stderr.strip()}")
    rama = _git(fuente, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    listado = _git(fuente, "ls-tree", "-r", "-z", "--name-only", "HEAD",
                   texto=False).stdout.decode("utf-8")
    rutas = sorted(r for r in listado.split("\0") if r and _es_vendorizado(r))
    faltan = [r for r in INDISPENSABLES
              if not r.startswith(UI_DIST) and r not in rutas]
    if faltan:
        raise SystemExit(f"El commit no trae lo indispensable: {faltan}")
    vigiladas = (*INCLUIR_ARCHIVOS, *INCLUIR_CARPETAS,
                 *(f"ui/{nombre}" for nombre in UI_FUENTES))
    sucio = _git(fuente, "status", "--porcelain", "--", *vigiladas).stdout.strip()
    if sucio:
        raise SystemExit(
            "El árbol de origen tiene cambios sin commitear en lo que se copia; "
            f"se vendoriza el COMMIT, no el árbol de trabajo. Commitea o descarta:\n{sucio}")
    contenido = {}
    for ruta in rutas:
        blob = _git(fuente, "show", f"HEAD:{ruta}", texto=False)
        if blob.returncode != 0:
            raise SystemExit(
                f"No se pudo leer {ruta} del commit: "
                f"{blob.stderr.decode('utf-8', 'replace')}")
        contenido[ruta] = blob.stdout
    origen = {"commit": commit.stdout.strip(), "rama": rama}
    url = repositorio_publico(fuente)
    if url:
        origen["repositorio"] = url
    return contenido, origen


def leer_ui_dist(fuente: Path) -> dict[str, bytes]:
    """The built UI from disk: present, fresh, and from committed sources.

    Sources being committed is enforced by ``leer_del_commit`` (it watches
    the UI source paths); here the bundle must exist and no source may be
    newer than it. Anything else aborts: a stale bundle next to newer
    sources is exactly the silent mismatch the UI gate refuses.
    """
    dist = fuente / UI_DIST
    indice = dist / "index.html"
    if not indice.is_file():
        raise SystemExit(
            f"falta {UI_DIST}index.html: construye la UI (cd ui && npm run build) "
            "sobre fuentes commiteadas antes de vendorizar")
    construido = indice.stat().st_mtime
    rancias: list[str] = []
    for nombre in UI_FUENTES:
        objetivo = fuente / "ui" / nombre
        if not objetivo.exists():
            continue
        candidatas = objetivo.rglob("*") if objetivo.is_dir() else (objetivo,)
        for ruta in candidatas:
            if ruta.is_file() and ruta.stat().st_mtime > construido:
                rancias.append(ruta.relative_to(fuente).as_posix())
    if rancias:
        detalle = "\n".join(f"  - {r}" for r in sorted(rancias)[:10])
        raise SystemExit(
            f"el build de la UI es anterior a sus fuentes; reconstruye:\n{detalle}")
    return {ruta.relative_to(fuente).as_posix(): ruta.read_bytes()
            for ruta in sorted(dist.rglob("*")) if ruta.is_file()}


def version_y_requisitos(contenido: dict[str, bytes]) -> tuple[str, dict]:
    """One version in both declarations; interpreter and deps for the host."""
    import re

    try:
        proyecto = tomllib.loads(contenido["pyproject.toml"].decode("utf-8"))["project"]
    except (tomllib.TOMLDecodeError, KeyError, UnicodeDecodeError) as exc:
        raise SystemExit(f"pyproject.toml ilegible en el commit: {exc}") from exc
    version = proyecto.get("version", "")
    if not version:
        raise SystemExit("pyproject.toml del commit no declara version")
    iniciador = contenido["src/molchat_agent/__init__.py"].decode("utf-8", "replace")
    coincidencia = re.search(r'^__version__\s*=\s*"([^"]+)"', iniciador, re.M)
    if coincidencia is None or coincidencia.group(1) != version:
        declarada = coincidencia.group(1) if coincidencia else "ausente"
        raise SystemExit(
            f"la versión no coincide: pyproject dice {version}, "
            f"__init__.py dice {declarada}")
    dependencias = list(proyecto.get("dependencies", []))
    extras = proyecto.get("optional-dependencies", {})
    dependencias.extend(f"{d} (extra server)" for d in extras.get("server", []))
    return version, {"python": proyecto.get("requires-python", ""),
                     "dependencias": dependencias}


def problemas_de_contenido(contenido: dict[str, bytes]) -> list[str]:
    """Missing indispensables, wrong license, machine paths or secrets."""
    problemas = []
    for ruta in INDISPENSABLES:
        if ruta not in contenido:
            problemas.append(f"falta {ruta}")
    licencia = contenido.get("LICENSE")
    if licencia is not None and \
            sha256_bytes(licencia.replace(b"\r\n", b"\n")) != SHA256_GPL3_LF:
        problemas.append("LICENSE no es el texto de la GPL-3.0-or-later")
    for ruta, datos in sorted(contenido.items()):
        if Path(ruta).suffix not in SUFIJOS_DE_CODIGO:
            continue
        try:
            texto = datos.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for numero, linea in enumerate(texto.splitlines(), 1):
            for patron, etiqueta in _detectores.SECRET_PATTERNS:
                for coincidencia in patron.finditer(linea):
                    if etiqueta == "credential-like assignment" and not \
                            _detectores.check_assignment(coincidencia.group(2)):
                        continue
                    problemas.append(
                        f"{ruta}:{numero}: {etiqueta}: {linea.strip()[:80]}")
            if _detectores.MACHINE_PATH.search(linea):
                problemas.append(
                    f"{ruta}:{numero}: ruta de una máquina concreta: "
                    f"{linea.strip()[:80]}")
    return problemas


def construir_manifiesto(contenido: dict[str, bytes], origen: dict[str, str],
                         version: str, requisitos: dict,
                         min_moldesign: str = "") -> dict:
    archivos = {ruta: {"bytes": len(datos), "sha256": sha256_bytes(datos)}
                for ruta, datos in sorted(contenido.items())}
    contrato: dict[str, str] = {"agente_plataforma": CONTRATO}
    if min_moldesign:
        contrato["min_moldesign"] = min_moldesign
    return {
        "schema": ESQUEMA,
        "programa": "MolChat (asistente de laboratorio de MolDesign)",
        "version": version,
        "licencia_spdx": LICENCIA_SPDX,
        "licencia_texto": "LICENSE",
        "fuente": {"proyecto": "moldesign-molchat", **origen},
        "invocacion": ("sidecar: proceso Python en loopback con paquete src "
                       "vendorizado; el host resuelve el paquete en el intérprete, "
                       "usa puerto efímero y token con scopes"),
        "no_se_enlaza": ("MolDesign no importa molchat_agent ni MolChat importa "
                         "MolDesign; se comunican por HTTP versionado "
                         f"({CONTRATO})."),
        "contrato": contrato,
        "requisitos": requisitos,
        "excluidos": list(EXCLUIDOS_DOCUMENTADOS),
        "archivos": archivos,
        "sha256_conjunto": sha256_conjunto(archivos),
    }


def escribir(fuente: Path, salida: Path, min_moldesign: str = "") -> dict:
    """Materialize the vendorizable copy of HEAD at ``salida`` + manifest."""
    contenido, origen = leer_del_commit(fuente)
    contenido.update(leer_ui_dist(fuente))
    problemas = problemas_de_contenido(contenido)
    if problemas:
        raise SystemExit("El commit de origen no se puede distribuir:\n  "
                         + "\n  ".join(problemas))
    version, requisitos = version_y_requisitos(contenido)
    if salida.exists():
        if not (salida / NOMBRE_MANIFIESTO).is_file():
            raise SystemExit(
                f"{salida} existe y no es una copia MolChat vendorizada; no la borro.")
        shutil.rmtree(salida)
    for ruta, datos in contenido.items():
        destino = salida / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)
    manifiesto = construir_manifiesto(contenido, origen, version, requisitos,
                                      min_moldesign)
    (salida / NOMBRE_MANIFIESTO).write_bytes(
        (json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return manifiesto


def _es_bytecode(ruta: Path, carpeta: Path) -> bool:
    """``__pycache__/*.pyc``: what the interpreter writes next to a vendored
    copy the first time it runs it. A derivative of the verified ``.py``
    files, not a shipped file (the same lesson the Molcy verifier learned
    with Blender). Only ``.pyc`` inside a ``__pycache__`` is ignored."""
    return ruta.suffix == ".pyc" and "__pycache__" in ruta.relative_to(carpeta).parts[:-1]


def verificar(carpeta: Path) -> list[str]:
    """Problems of ``carpeta`` (empty list = fit to ship): manifest shape,
    exact file set with bytes and hashes, set fingerprint, then what only
    matters when distributing (license, paths, secrets, indispensables)."""
    manifiesto_ruta = carpeta / NOMBRE_MANIFIESTO
    if not manifiesto_ruta.is_file():
        return [f"falta {NOMBRE_MANIFIESTO}: no es una copia MolChat vendorizada"]
    try:
        manifiesto = json.loads(manifiesto_ruta.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        return [f"manifiesto ilegible: {exc}"]
    problemas = _problemas_de_forma(manifiesto)
    if problemas:
        return problemas
    declarados: dict = manifiesto["archivos"]
    en_disco = {ruta.relative_to(carpeta).as_posix()
                for ruta in carpeta.rglob("*")
                if ruta.is_file() and ruta.name != NOMBRE_MANIFIESTO
                and not _es_bytecode(ruta, carpeta)}
    for ruta in sorted(set(declarados) - en_disco):
        problemas.append(f"falta {ruta}")
    for ruta in sorted(en_disco - set(declarados)):
        problemas.append(f"sobra {ruta}")
    for ruta in sorted(set(declarados) & en_disco):
        datos = (carpeta / ruta).read_bytes()
        esperado = declarados[ruta]
        if not isinstance(esperado, dict) or set(esperado) != {"bytes", "sha256"}:
            problemas.append(f"{ruta}: entrada de manifiesto malformada")
            continue
        if len(datos) != esperado["bytes"] or sha256_bytes(datos) != esperado["sha256"]:
            problemas.append(f"{ruta}: no coincide con su manifiesto")
    if not problemas and sha256_conjunto(declarados) != manifiesto["sha256_conjunto"]:
        problemas.append("sha256_conjunto no recomputa: el manifiesto fue editado")
    if problemas:
        return problemas
    return problemas_de_contenido(
        {ruta: (carpeta / ruta).read_bytes() for ruta in declarados})


def _problemas_de_forma(manifiesto: object) -> list[str]:
    """The manifest carries every key the shared schema requires, well-typed."""
    import re

    if not isinstance(manifiesto, dict):
        return ["el manifiesto no es un objeto JSON"]
    problemas = [f"el manifiesto no trae {clave}"
                 for clave in MANIFIESTO_REQUERIDO if clave not in manifiesto]
    if problemas:
        return problemas
    hexa40 = re.compile(r"^[0-9a-f]{40}$")
    hexa64 = re.compile(r"^[0-9a-f]{64}$")
    if manifiesto["schema"] != ESQUEMA:
        problemas.append(f"schema {manifiesto['schema']!r}: este verificador "
                         f"solo conoce {ESQUEMA}")
    if manifiesto["licencia_spdx"] != LICENCIA_SPDX:
        problemas.append("licencia_spdx distinta de GPL-3.0-or-later")
    fuente = manifiesto["fuente"]
    if not isinstance(fuente, dict) or \
            not {"proyecto", "commit", "rama"} <= set(fuente):
        problemas.append("fuente incompleta (proyecto, commit, rama)")
    elif fuente["proyecto"] != "moldesign-molchat" or \
            not hexa40.match(str(fuente["commit"])):
        problemas.append("fuente no apunta a un commit de moldesign-molchat")
    contrato = manifiesto["contrato"]
    if not isinstance(contrato, dict) or \
            contrato.get("agente_plataforma") != CONTRATO:
        problemas.append("contrato.agente_plataforma desconocido")
    requisitos = manifiesto["requisitos"]
    if not isinstance(requisitos, dict) or \
            not {"python", "dependencias"} <= set(requisitos):
        problemas.append("requisitos incompletos (python, dependencias)")
    if not isinstance(manifiesto["archivos"], dict) or not manifiesto["archivos"]:
        problemas.append("archivos vacío o malformado")
    if not hexa64.match(str(manifiesto["sha256_conjunto"])):
        problemas.append("sha256_conjunto malformado")
    return problemas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fuente", type=Path, default=ROOT,
                        help="árbol git del que vendorizar (por defecto, este repo)")
    parser.add_argument("--write", action="store_true",
                        help="materializa el HEAD de --fuente en --out + manifiesto")
    parser.add_argument("--out", type=Path, default=None,
                        help="destino de --write (por defecto dist/molchat-vendorizable)")
    parser.add_argument("--check", type=Path, default=None, metavar="COPIA",
                        help="verifica una copia vendorizada contra su manifiesto")
    parser.add_argument("--min-moldesign", default="",
                        help="MolDesign mínimo con superficie de host "
                             "(se omite si ninguno publicado la trae)")
    args = parser.parse_args(argv)
    if args.write:
        salida = args.out or args.fuente / "dist" / "molchat-vendorizable"
        manifiesto = escribir(args.fuente, salida, args.min_moldesign)
        fuente = manifiesto["fuente"]
        total = sum(f["bytes"] for f in manifiesto["archivos"].values())
        print(f"{salida}: {len(manifiesto['archivos'])} ficheros, "
              f"{manifiesto['version']}, "
              f"{fuente['rama']}@{fuente['commit'][:8]} ({total / 1e6:.1f} MB)")
        return 0
    if args.check is not None:
        problemas = verificar(args.check)
        if problemas:
            print(f"{args.check} NO es íntegro:\n  " + "\n  ".join(problemas),
                  file=sys.stderr)
            return 1
        manifiesto = json.loads((args.check / NOMBRE_MANIFIESTO).read_text(
            encoding="utf-8"))
        print(f"{args.check} íntegro: {len(manifiesto['archivos'])} ficheros, "
              f"v{manifiesto['version']}, "
              f"{manifiesto['fuente']['rama']}@{manifiesto['fuente']['commit'][:8]}, "
              f"{manifiesto['licencia_spdx']}")
        return 0
    parser.error("indica --write o --check")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
