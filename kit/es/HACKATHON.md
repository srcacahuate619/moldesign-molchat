# MolChat en el hackathon de Meta

> Traducción de [`kit/en/HACKATHON.md`](../en/HACKATHON.md), revisada el 2026-11-03. Si alguna vez no coinciden, manda la versión inglesa.

**▶ [Ver la demo de 3 minutos](https://www.youtube.com/watch?v=luRIXlqWy6I)** (en inglés)

MolChat permite que un investigador de química computacional delegue una serie corta de acoplamientos desde un mensaje. Muse Spark Open busca los compuestos en PubChem y prepara un plan con el receptor, el orden de los candidatos, la regla de parada y lo que se pide al final. El investigador lo aprueba una vez. MolChat maneja la aplicación de escritorio y entrega la evidencia necesaria para revisar o compartir el resultado.

## La corrida grabada

La petición nombró seis moléculas y pidió detenerse ante la primera que diera **−10,5 kcal/mol o menos** contra VMAT2 (PDB 8T69) con los controles físicos superados. Con una aprobación, MolChat evaluó cinco, se detuvo en la ketanserina (**−11,2 kcal/mol**, controles superados) y registró que la valbenazina quedó sin evaluar. El plan tardó unos seis minutos desde la aprobación hasta el final; el vídeo se renderizó después y se sumó al ZIP. Son resultados de una corrida de Vina bajo las condiciones de la demo. [Petición y configuración](GETTING_STARTED.md#7-probar-el-mensaje-de-la-demo) · [El ZIP real que produjo](../vmat2-run/)

En el vídeo, fíjate en la tarjeta de aprobación, las acciones a la vista en la aplicación, la decisión de parar y el cuaderno. El trabajo del agente es coordinar esos pasos y dejar su rastro de evidencia. El motor de docking y el de render son componentes de MolDesign que ya existían. [Ver la grabación](https://www.youtube.com/watch?v=luRIXlqWy6I)

## Evidencia por criterio

| Criterio | Qué revisar |
|---|---|
| **Impacto · 30 %** | El investigador fija la regla una vez y recibe el registro de qué candidatos se probaron, se omitieron y se eligieron. En la corrida grabada no se lanzó el sexto candidato porque la regla ya se había cumplido. [Caso de la demo](GETTING_STARTED.md#7-probar-el-mensaje-de-la-demo) |
| **Uso de las herramientas de IA de Meta · 25 %** | Muse Spark Open elige las herramientas de consulta y convierte la petición en un plan estructurado. El plan aceptado se vuelve una secuencia real de acciones en la aplicación. [Modelo y herramientas](#cómo-usa-los-modelos-de-meta) |
| **Demo · 25 %** | Mira la corrida real y reproduce después, sin clave, la aprobación y la parada con el anfitrión simulado. [Vídeo](https://www.youtube.com/watch?v=luRIXlqWy6I) · [El ZIP real de la corrida](../vmat2-run/) · [Prueba sin claves](README.md#prueba-sin-claves) |
| **Profundidad técnica y ejecución · 20 %** | La prueba rechaza una huella de aprobación distinta, ejecuta una sola vez tras aprobar, se recupera de un candidato fallido y comprueba el ZIP exportado. [Prueba de integración](../../tests/server/test_workflow_chat.py) · [Contrato de anfitrión](../../docs/HOST_CONTRACT.md) |

El caso encaja en **Build for Your World**, la temática de Meta para aplicar sus modelos a un flujo de trabajo de un dominio concreto. Los pesos de arriba salen de la guía para participantes. [Evento de Meta](https://dev.meta.ai/events/global-hackathon) · [Página de Cerebral Valley](https://cerebralvalley.ai/e/meta-ai-developer-hackathon)

## Cómo usa los modelos de Meta

- **La demo corre con Muse Spark Open** (`meta-models/muse-spark-open-1026`), servido por Baseten. Es el modelo de pesos abiertos de la corrida grabada. El catálogo de proveedores incluye aparte la Meta Model API. [Catálogo de proveedores](../../src/molchat_agent/providers/catalogo.json) · [Anuncio del modelo en Baseten](https://www.baseten.co/blog/muse-spark-open-launch/)
- **El modelo convierte la petición en llamadas a herramientas.** Decide qué buscar (`pubchem_lookup`), rellena el plan (`propose_iteration`) y contesta las preguntas siguientes con resultados de MolDesign. [Herramienta de consulta](../../src/molchat_agent/conversation/harness_tools.py) · [Herramienta del plan](../../src/molchat_agent/workflows/tool.py)
- **El código comprueba todo lo que rellena el modelo.** Los argumentos deben encajar en esquemas cerrados y el plan se valida antes de que exista la tarjeta. La aprobación queda ligada al SHA-256 del plan y un bucle determinista lo ejecuta, así que el modelo no puede cambiar las reglas a mitad.
- **El modelo no tiene la última palabra sobre los números.** Una cifra de la respuesta que ninguna herramienta devolvió se oculta, y la respuesta lo dice. En la demo, MolChat ocultó valores que no podía verificar en vez de adivinarlos.

## Qué se construyó durante el evento y qué no

Las reglas piden enseñar sólo lo construido durante el hackathon. La línea está aquí.

| Construido durante el evento | Anterior |
|---|---|
| **Proveedor Muse Spark Open**, el 28 de octubre. [Commit del proveedor](https://github.com/srcacahuate619/moldesign-molchat/commit/74b8d96b3e389c44519dfb5441ca8249baef5808) | **La plataforma científica MolDesign**, con AutoDock Vina, Moldex, Molcy, Preparación y el asistente anterior que vivía dentro. |
| **Iteración con una sola aprobación y acciones de anfitrión**, el 2 de noviembre. [Commit de la iteración](https://github.com/srcacahuate619/moldesign-molchat/commit/2a0ca42a9f0f01013a4e8465cb11c9ef00e129ca) | **Código reutilizado**, como la consulta original a PubChem. [Registro de procedencia](../../PROVENANCE.md) |
| **Evidencia por corrida y ejecución visible del agente**, el 3 de noviembre. [Commit del registro](https://github.com/srcacahuate619/moldesign-molchat/commit/42fa3deb3e64f447ea29675ace2aa04ca21f0ea4) · [Commit del progreso](https://github.com/srcacahuate619/moldesign-molchat/commit/0c4d0a5d1edd9c0f8b97ab834893008177644538) | **Motores y datos de investigación existentes**, que aportan las entradas y salidas científicas. |

El historial del repositorio empieza el 26 de octubre, día de la apertura. La tabla ancla el trabajo que se enseña a commits de funciones posteriores. La parte de MolDesign de la integración, que arranca el agente, aplica sus acciones de anfitrión y muestra su progreso en la aplicación, también se escribió durante el evento: se añadió por primera vez el 27 de octubre y es pública en moldesign-app desde el 31 de octubre. [Historial del repositorio](https://github.com/srcacahuate619/moldesign-molchat/commits/master/) · [Integración en MolDesign](https://github.com/srcacahuate619/moldesign-app/tree/ece0208/frontend/components/ai-host)

Qué cambió durante el evento: antes, MolChat **sugería y esperaba** a una persona en cada paso. Ahora **un plan aprobado una vez se ejecuta solo**, se recupera de los fallos de cada molécula y declara lo que no pudo hacer. La ciencia, la identidad y las decisiones de Preparación siguen siendo de MolDesign: MolChat no calcula ninguna energía ni toma ninguna decisión humana.

## Cómo comprobarlo

| Qué | Dónde |
|---|---|
| La demo, de principio a fin | [Vídeo de 3 minutos](https://www.youtube.com/watch?v=luRIXlqWy6I) |
| Lo que entregó la corrida grabada, byte a byte | [`kit/vmat2-run/`](../vmat2-run/) |
| El bucle de una sola aprobación, sin claves ni MolDesign | [Prueba sin claves](README.md#prueba-sin-claves) |
| El sistema real en tu computadora | [Primeros pasos](GETTING_STARTED.md) |
| Cómo añadir una herramienta o adaptar MolChat a otra plataforma | [Extender MolChat](EXTENDING.md) |
| Quién escribió qué, archivo por archivo | [`PROVENANCE.md`](../../PROVENANCE.md) |
| Pruebas en cada push | [CI](https://github.com/srcacahuate619/moldesign-molchat/actions/workflows/ci.yml) |

## Límites conocidos

- **Sólo Windows y desde el código fuente.** La versión de MolDesign en Microsoft Store es anterior a MolChat. Para usar los dos hoy, se compila MolDesign desde su repositorio ([Primeros pasos](GETTING_STARTED.md)).
- **Sin probar desde el instalador en una máquina limpia.** La demo corrió en la computadora del desarrollador, desde el código fuente. La CI de MolDesign y un clon limpio pasan, pero todavía no se ha construido un instalador con MolChat.
- **Un score de docking no es un fármaco.** La energía de Vina ordena hipótesis sobre un receptor; no demuestra actividad. El receptor de la demo, 8T69, es el único del catálogo de MolDesign cuyo orden de Vina superó una prueba registrada de antemano contra valores de Ki publicados. Aun ahí, ordena una serie mejor que el azar; no predice el Ki de una molécula.
- **Números ocultos.** Cuando MolChat no puede ligar una cifra a una herramienta, la oculta. Así las respuestas son honestas, pero algunas salen con huecos.
- **Algunos textos de la demo salen tal como los escribe MolDesign**, como un código de aviso (`ESTEREOQUIMICA_NO_DECLARADA`), el estado del trabajo de Molcy y el nombre de escena `resultado` en el cuaderno de la corrida.
