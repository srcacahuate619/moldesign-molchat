# MolChat en español

> Traducción del [README principal](../../README.md) y del [kit en inglés](../en/), revisada el 2026-11-03. Si alguna vez no coinciden, manda la versión inglesa.

**Un agente que maneja por ti una aplicación de química computacional y enseña lo que hace.** Describe por texto o por voz una hipótesis sobre una lista de moléculas, revisa el plan que propone MolChat y apruébalo una sola vez. MolChat lo ejecuta en [MolDesign](https://github.com/srcacahuate619/moldesign-app) y entrega un cuaderno de laboratorio y un ZIP que dicen qué se ejecutó, qué se eligió y qué falta.

**▶ [Ver la demo de 3 minutos](https://www.youtube.com/watch?v=luRIXlqWy6I)** (en inglés)

## Por dónde empezar

| Si quieres… | Ve a |
|---|---|
| Saber qué se construyó en el hackathon de Meta y cómo usa Muse Spark | [El hackathon](HACKATHON.md) |
| Ver el flujo de una sola aprobación sin claves ni MolDesign | [Prueba sin claves](#prueba-sin-claves) |
| Usar MolDesign con MolChat en tu computadora, con docking real | [Primeros pasos](GETTING_STARTED.md) |
| Añadir una herramienta a MolChat o adaptarlo a otra plataforma | [Extender MolChat](EXTENDING.md) |

## Prueba sin claves

Con Python 3.11 o 3.12, desde un clon nuevo:

```sh
git clone https://github.com/srcacahuate619/moldesign-molchat.git
cd moldesign-molchat
python -m venv .venv
```

Activa el entorno (`.\.venv\Scripts\Activate.ps1` en PowerShell, `source .venv/bin/activate` en macOS o Linux) y ejecuta:

```sh
python -m pip install -e ".[dev]"
python -c "from pathlib import Path; Path('reports').mkdir(exist_ok=True)"
python -m pytest -q --basetemp=reports/judge-demo tests/server/test_workflow_chat.py
```

Las pruebas conducen el chat con un modelo guionizado y un MolDesign simulado. Comprueban que una huella equivocada se rechaza, que una aprobación válida ejecuta el plan una sola vez, que el fallo de una molécula queda registrado y que el plan se detiene antes del tercer candidato. Busca `entrega.zip` dentro de `reports/judge-demo/`. En `cuaderno/cuaderno.md` aparecen los tres candidatos: el primero falla, el segundo cumple y el tercero se omite por la regla de parada. En `MANIFEST.json` están la huella de cada archivo y el motivo por el que falta el paquete de Preparación. El modelo, los resultados del docking y el vídeo son simulados.

También puedes [abrir la interfaz local](../../README.md#build-and-open-the-ui) con el proveedor determinista y pedir «Lista los receptores» en la pestaña de planes.

## La corrida del vídeo

El ZIP real que produjo MolChat en la corrida del vídeo está en [`kit/vmat2-run/`](../vmat2-run/), byte a byte, con su cuaderno a la vista y la forma de comprobar cada huella.

## Qué es nuevo y qué es previo

La contribución del hackathon es la integración del agente y el flujo que convierte una petición en una corrida aprobada, ejecutada y trazable, junto con la parte de MolDesign de esa integración (arrancar MolChat, sus acciones de anfitrión y la vista del piloto automático). El docking, Moldex, Molcy y Preparación de MolDesign ya existían, igual que el código reutilizado que declara [`PROVENANCE.md`](../../PROVENANCE.md), como la consulta original a PubChem. Los commits fechados están en [El hackathon](HACKATHON.md#qué-se-construyó-durante-el-evento-y-qué-no).

## Documentación técnica

Los contratos de detalle están en español, en [`docs/`](../../docs/):

- [Iteración de moléculas](../../docs/ITERACION_DE_MOLECULAS.md): el plan, la regla de parada, el cuaderno y el ZIP.
- [Contrato de acciones de host](../../docs/HOST_CONTRACT.md): lo que MolChat pide a la ventana de la plataforma y lo que acepta de vuelta.
- [Contrato con MolDesign](../../docs/CONTRATO_MOLDESIGN.md) y [protocolo](../../docs/PROTOCOLO_MOLDESIGN.md): las rutas HTTP, la sesión y la negociación.
- [La llave y la cerradura](../../docs/LLAVE_Y_CERRADURA.md): cómo MolDesign comprueba y fija la copia de MolChat.
- [Creación de herramientas](../../docs/CREACION_DE_HERRAMIENTAS.md): cada herramienta que existe y cómo se mantiene honesta.
