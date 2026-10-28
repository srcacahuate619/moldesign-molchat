# La llave y la cerradura

MolChat es la **llave**. MolDesign tiene la **cerradura**: el código que decide si la llave encaja, la arranca y la muestra en la aplicación. Este documento describe el contrato entre ambos desde el lado de MolChat. Lo que MolDesign comprueba antes de arrancar está en su ADR 100 (`docs/100_ADR_MOLCHAT_EXTERNO.md` del repositorio de MolDesign).

## Qué es cada cosa

- **La llave** es este repositorio. Lo que se publica de ella es `src/molchat_agent/` (el sidecar), `ui/dist/` (la interfaz ya construida), `LICENSE`, `NOTICE.md`, `pyproject.toml` y `molchat-manifest.json`. El productor es `scripts/make_manifest.py` y trabaja sobre un commit limpio, nunca sobre el árbol de trabajo.
- **La cerradura** es MolDesign. Guarda dos cosas: la **copia** de la llave en `tools/molchat/` y la **fijación** en `backend/data/molchat_fijacion.json`, que dice qué commit y qué manifiesto debe tener esa copia.

La copia no es la fuente. La fuente es este repositorio y la copia sale de él con `scripts/stage_molchat.py` de MolDesign.

## Qué comprueba MolDesign antes de arrancar

1. La copia existe y trae `molchat-manifest.json`.
2. Cada fichero coincide con su SHA-256 y su tamaño, y no sobra ni falta ninguno.
3. El contrato que declara la llave es `moldesign.molchat/1`.
4. La fijación existe, su esquema es conocido, el SHA-256 del manifiesto es el fijado y el commit del manifiesto es el fijado.

Si algo falla, MolDesign no arranca el sidecar y dice por qué. MolDesign funciona igual sin MolChat: la llave es opcional.

Hay una excepción deliberada: con `MOLDESIGN_MOLCHAT_DIR` y `MOLCHAT_PERMITIR_EXTERNO=1`, MolDesign usa una copia externa sin fijación. Es para desarrollo y no está en la interfaz.

## La fijación

`backend/data/molchat_fijacion.json` (en MolDesign) tiene estos campos:

| Campo | Qué dice |
|---|---|
| `schema` | `moldesign.molchat-fijacion/1` |
| `repositorio` | De dónde sale la copia (URL pública, sin credenciales) |
| `oficial` | `true` sólo si `repositorio` es `https://github.com/srcacahuate619/moldesign-molchat` |
| `commit` | El commit de MolChat del que sale la copia |
| `rama` | La rama de ese commit en el momento de vendorizar |
| `version` | La versión declarada por la llave |
| `sha256_manifiesto` | El SHA-256 de `molchat-manifest.json` |

Una fijación `oficial` sólo es reproducible desde fuera si su commit está publicado en el repositorio oficial. Mientras no lo esté, la fijación es local.

## Qué no debe romper una llave

Una versión propia de MolChat entra en MolDesign si cumple el contrato. Para eso debe:

- Mantener `moldesign.molchat/1` y un manifiesto que describa sus ficheros con su esquema.
- Conservar `LICENSE` como texto íntegro de GPL-3.0-or-later y `NOTICE.md`.
- No dejar rutas absolutas de una máquina en el código que se distribuye.
- Conservar las entradas que el lanzador necesita: `molchat_agent/__main__.py`, `cli.py`, `server/serve.py`, `server/app.py` y `ui/dist/index.html`.
- Pasar `python -m conformance.runner` (sin `--live`) y `python -m pytest`.

Si cambias el contrato, MolDesign no arranca la llave hasta que su host lo soporte. Es un fallo deliberado: un sidecar que habla otro protocolo no debe ejecutarse en silencio.

## Cómo se integra

Desde MolDesign:

```bash
python scripts/stage_molchat.py --fuente <clon-de-moldesign-molchat> --write
python scripts/stage_molchat.py --check
```

El primer comando vendoriza el HEAD del clon en `tools/molchat/` y actualiza la fijación. El segundo verifica la copia y la fijación.

Sólo se integran commits. El productor se niega a empaquetar un árbol con cambios sin commitear en lo que se distribuye, para que lo que MolDesign ejecuta sea exactamente lo que este repositorio contiene en un commit.

Para el flujo de trabajo diario y para poner una versión propia, ver [DESARROLLO_Y_VERSION_PROPIA.md](DESARROLLO_Y_VERSION_PROPIA.md).
