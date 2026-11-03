# Usar MolDesign con MolChat

> Traducción de [`kit/en/GETTING_STARTED.md`](../en/GETTING_STARTED.md), revisada el 2026-11-03. Si alguna vez no coinciden, manda la versión inglesa.

Esta guía es para quien quiera usar el sistema completo en su computadora: **MolDesign**, la aplicación de docking de escritorio, con **MolChat**, el agente que la maneja. Usa el código más reciente de los dos proyectos. Como los dos cambian a menudo, la guía dice contra qué se comprobó por última vez, y la [sección de cambios](#cambios-de-esta-guía) registra cada actualización.

| Última comprobación | |
|---|---|
| Fecha | 2026-11-03 |
| MolDesign | [`main`](https://github.com/srcacahuate619/moldesign-app) en `ece0208` (versión 1.0.4, compilada desde el código fuente) |
| MolChat | [`master`](https://github.com/srcacahuate619/moldesign-molchat) en `945c4d7` (v0.1.0), la copia que fija MolDesign |
| Equipo | Windows 11 x64 con una NVIDIA GTX 1660 SUPER |

Si tus clones son más nuevos, los pasos siguen valiendo salvo que una entrada más reciente de [Cambios de esta guía](#cambios-de-esta-guía) diga otra cosa. Los comandos exactos que ejecuta la CI de MolDesign están en su [CONTRIBUTING.md](https://github.com/srcacahuate619/moldesign-app/blob/main/CONTRIBUTING.md). Si esta guía y esos archivos no coinciden, mandan esos archivos.

> **¿Por qué desde el código fuente?** La versión de MolDesign en Microsoft Store (1.0.3, del 22 de octubre de 2026) se construyó antes de que existiera MolChat, así que no trae el agente. Hasta que una versión publicada lo incluya, MolDesign se ejecuta desde su repositorio, como se explica abajo.

## 1. Qué necesitas

- **Windows 10 u 11, x64.** La aplicación de escritorio de MolDesign sólo funciona en Windows.
- **Git**, **Python 3** para el script de preparación, **Node.js** en la versión del [`.nvmrc`](https://github.com/srcacahuate619/moldesign-app/blob/main/.nvmrc) de MolDesign (24.20 en la fecha de arriba) y **Rust** estable con los [requisitos de Tauri para Windows](https://tauri.app/start/prerequisites/): las herramientas de compilación de C++ y WebView2.
- **Espacio en disco.** Sólo el runtime científico es una descarga de 2,2 GB. La caché de compilación de Rust y los módulos de Node ocupan varios GB más.
- **Un modelo.** La demo usa Muse Spark Open (`meta-models/muse-spark-open-1026`) servido por Baseten, con tu propia clave de Baseten. El [catálogo de proveedores](../../src/molchat_agent/providers/catalogo.json) de MolChat lista las alternativas, incluidas la Meta Model API y servidores locales (llama-server, Ollama) que no necesitan clave.
- **Opcional: una GPU** que pueda usar EEVEE de Blender, para los vídeos de Molcy. El docking, el cuaderno y el ZIP funcionan sin ella.

## 2. Descargar MolDesign y su runtime

```powershell
git clone https://github.com/srcacahuate619/moldesign-app.git
cd moldesign-app
python scripts/bootstrap_dev_tree.py --check
python scripts/bootstrap_dev_tree.py --fetch
```

`--check` lista lo que le falta a un clon nuevo y no escribe nada. `--fetch` descarga el Python embebido, AutoDock Vina y las demás herramientas nativas desde un archivo fijado por revisión y SHA-256, y lo verifica antes de extraerlo.

## 3. Comprobar la copia de MolChat dentro de MolDesign

MolDesign ya trae una copia de MolChat en `tools/molchat/`, fijada a un commit de MolChat en `backend/data/molchat_fijacion.json`. Compruébala:

```powershell
.\python-embed\python.exe scripts\stage_molchat.py --check
```

La salida nombra el commit, por ejemplo `master@945c4d7a`. Para usar un **MolChat más nuevo** que el fijado, ve a [Usar un MolChat más nuevo](#usar-un-molchat-más-nuevo).

## 4. Arrancar la aplicación

```powershell
cd frontend
npm ci
npx tauri dev
```

El primer arranque compila en Rust el contenedor de escritorio y tarda varios minutos; los siguientes son rápidos. La aplicación te abre sola una sesión local, y tus datos se quedan en esta máquina.

## 5. Conectar un modelo

1. Abre **OPCIONES** en la barra superior y después **Modelos y motores** → **Proveedores de IA**.
2. Elige **Baseten (Muse Spark Hackathon)**, u otro proveedor, y pulsa **Usar este proveedor**.
3. Pega tu clave y pulsa **Guardar y autorizar envío a …**. MolDesign guarda la clave cifrada para tu cuenta. MolChat la recibe en cada respuesta y nunca la muestra.

## 6. Abrir MolChat y autorizar PubChem

El botón redondo de MolChat está abajo a la derecha de la ventana. Haz clic para abrir el panel, o arrástralo para moverlo. En el panel, abre **Ajustes** y pulsa **Autorizar búsquedas en PubChem**: MolChat busca cada molécula en PubChem en vez de inventarse la estructura, y para eso envía los nombres a `pubchem.ncbi.nlm.nih.gov`.

## 7. Probar el mensaje de la demo

Es la petición de la [demo de 3 minutos](https://www.youtube.com/watch?v=luRIXlqWy6I). El receptor 8T69 (VMAT2) está en la sección **Verificados** del catálogo de MolDesign. Puedes escribirla en inglés, como en el vídeo, o en español; los nombres de las moléculas van en inglés, como los indexa PubChem.

> Crea un caso llamado «VMAT2 ligands» con el receptor 8T69. Busca en PubChem caffeine, tetrabenazine, deutetrabenazine, (+)-alpha-dihydrotetrabenazine, ketanserin y valbenazine, en ese orden, y acóplalas una a una con el protocolo por defecto. Detente en la primera que dé -10.5 kcal/mol o menos con una pose físicamente válida. Después haz un vídeo corto de prueba en Molcy, audítala en Preparación y dame todo en un ZIP con tu cuaderno.

MolChat contesta con una tarjeta del plan. Léela antes de aprobar: el receptor, las moléculas en orden, la regla de parada, el límite de tiempo y lo que viene después. Un clic en **Aprobar y ejecutar** arranca el plan. Deja abierta la ventana de MolDesign: las acciones del plan se ejecutan desde ella. Mientras maneja MolDesign, un marco violeta y un cursor «MolChat» indican que el agente, y no tú, lleva los controles. Puedes minimizar el panel: la burbuja conserva el plan y el score de Vina de cada molécula.

En el equipo de arriba, el plan acopló cinco moléculas, se detuvo en la ketanserina (−11,2 kcal/mol, controles físicos superados) y nunca acopló la valbenazina. Esas cifras son scores de Vina sobre un receptor, no prueban que una molécula sea mejor fármaco.

## 8. Obtener los resultados

Cuando el plan termina, la tarjeta ofrece **Descargar la entrega (ZIP)**. MolChat también la escribe en una carpeta con el nombre del caso y la hora, dentro de `%USERPROFILE%\MolDesign\MolChat\entregas` (`entrega.zip` si el plan es en español, `delivery.zip` si es en inglés). Para usar otra carpeta, define `MOLCHAT_OUTPUT_DIR` antes de arrancar la aplicación. Dentro hay:

- el cuaderno del agente en PDF, Markdown y JSON, con la fuente y las condiciones de cada número;
- el paquete de Preparación de MolDesign, sin cambios;
- el vídeo de Molcy, si el plan lo pidió y la GPU lo renderizó;
- `MANIFEST.json`, con la huella SHA-256 de cada archivo y el motivo de cada pieza que falta.

El vídeo se renderiza en segundo plano. **Descargar ahora (sin el vídeo)** te da el ZIP en el acto, con el vídeo declarado como ausente; vuelve a descargar cuando la tarjeta diga que el vídeo ya está.

## Usar un MolChat más nuevo

Para usar el `master` más reciente de MolChat, o tu propio fork, prepáralo en una carpeta aparte y apunta MolDesign a ella. La copia fijada de tu clon no cambia. Ejecuta esto desde la carpeta que contiene `moldesign-app`.

```powershell
git clone https://github.com/srcacahuate619/moldesign-molchat.git
npm --prefix moldesign-molchat\ui ci
npm --prefix moldesign-molchat\ui run build
cd moldesign-app
.\python-embed\python.exe scripts\stage_molchat.py --fuente ..\moldesign-molchat --write --destino ..\molchat-staged
$env:MOLDESIGN_MOLCHAT_DIR = (Resolve-Path ..\molchat-staged).Path
$env:MOLCHAT_PERMITIR_EXTERNO = "1"
cd frontend
npx tauri dev
```

Sólo se prepara código commiteado, y la interfaz construida debe ser más nueva que sus fuentes. MolDesign marca entonces la copia como externa, no oficial. Para sustituir la copia fijada, ejecuta `stage_molchat.py --fuente <clon> --write` sin `--destino` y después `--check`. Ver [Extender MolChat](EXTENDING.md#6-meter-tu-versión-dentro-de-moldesign).

## Cuando algo falla

| Qué ves | Qué hacer |
|---|---|
| `bootstrap_dev_tree.py --check` sigue diciendo que faltan piezas después de `--fetch` | Vuelve a ejecutar `--fetch`. En nuestra propia prueba desde un clon nuevo, una descarga se cortó a mitad y funcionó al reintentar. |
| «MolChat no está incluido en esta instalación» | Falta `tools/molchat/` o no supera su comprobación. Ejecuta el paso 3 y lee su mensaje. |
| «MolChat no pudo arrancar» | La copia no coincide con su fijación, o su contrato no es `moldesign.molchat/1`. Ejecuta el paso 3, o el `--check` de [Usar un MolChat más nuevo](#usar-un-molchat-más-nuevo). |
| La tarjeta dice que una molécula no se encontró | PubChem no está autorizado (paso 6) o el nombre es ambiguo. Usa un nombre más preciso o da el SMILES. |
| «Vina insufficient memory» en una molécula | Cierra los programas que gastan mucha memoria. MolChat reintenta esa molécula una vez y anota el resultado en el cuaderno. |
| No hay vídeo en el ZIP | Molcy necesita una GPU que EEVEE pueda usar, y Blender con Molecular Nodes, que su pestaña ofrece descargar la primera vez. El manifiesto dice qué pieza falta y por qué. |

## Cambios de esta guía

Añade una entrada cada vez que cambie un paso, una etiqueta o una versión, y actualiza la tabla de arriba. Cambia primero la versión inglesa y después esta.

- **2026-11-03.** Primera versión, comprobada contra MolDesign `ece0208` y MolChat `945c4d7`.

Cuando una versión de Microsoft Store incluya MolChat, sustituye los apartados 2 a 4 por «instala MolDesign desde Microsoft Store» y conserva la ruta del código fuente para quien quiera lo más nuevo.
