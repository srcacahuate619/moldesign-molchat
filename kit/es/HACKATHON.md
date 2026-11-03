# MolChat en el hackathon de Meta

> Traducción de [`kit/en/HACKATHON.md`](../en/HACKATHON.md), revisada el 2026-11-03. Si alguna vez no coinciden, manda la versión inglesa.

**▶ [Ver la demo de 3 minutos](https://www.youtube.com/watch?v=luRIXlqWy6I)** (en inglés)

MolChat es un agente que maneja por ti una aplicación de docking de escritorio y enseña lo que hace. Describes una hipótesis en un solo mensaje, por ejemplo «acopla estas seis moléculas contra VMAT2 y detente en la primera que dé menos de −10,5 kcal/mol con una pose válida». MolChat busca cada molécula en PubChem y escribe el plan completo en una tarjeta. Lo apruebas una vez y lo ejecuta en MolDesign mientras miras. Al final, un cuaderno y un ZIP dicen qué se ejecutó, qué es cada número, de dónde sale y qué falta.

## Cómo usa los modelos de Meta

- **La demo corre con Muse Spark Open** (`meta-models/muse-spark-open-1026`), servido por Baseten. MolChat también tiene un adaptador para la Meta Model API, cuyo modelo por defecto es `muse-spark-1.3` ([`providers/meta.py`](../../src/molchat_agent/providers/meta.py)).
- **El modelo convierte la petición en llamadas a herramientas.** Decide qué buscar (`pubchem_lookup`), rellena el plan (`propose_iteration`) y contesta las preguntas siguientes leyendo los resultados de MolDesign.
- **El código comprueba todo lo que rellena el modelo.** Los argumentos deben encajar en esquemas cerrados y el plan se valida antes de que exista la tarjeta. La aprobación queda ligada al SHA-256 del plan y un bucle determinista lo ejecuta, así que el modelo no puede cambiar las reglas a mitad.
- **El modelo no tiene la última palabra sobre los números.** Una cifra de la respuesta que ninguna herramienta devolvió se oculta, y la respuesta lo dice. En la demo, MolChat ocultó valores que no podía verificar en vez de adivinarlos.

## Qué se construyó durante el evento y qué no

Las reglas piden enseñar sólo lo construido durante el hackathon. La línea está aquí.

| Construido durante el evento | Anterior |
|---|---|
| **Todo este repositorio**, por declaración del autor. Su historial empieza en `d37cc70`, el 2026-10-26 (UTC−6), y `git log --reverse` lista cada cambio con su hora. | **MolDesign**, la plataforma: docking con AutoDock Vina, Moldex, Molcy (vídeo), Preparación y su paquete, y el asistente que vivía dentro. |
| **La parte de MolDesign de la integración**, desde el 2026-10-27: arrancar y comprobar MolChat, las acciones de anfitrión, el marco y el cursor del piloto automático y la burbuja del panel minimizado. Vive en [moldesign-app](https://github.com/srcacahuate619/moldesign-app), en `frontend/components/ai-host/` y `backend/services/molchat_host/`. | **El código traído de MolDesign**, declarado archivo por archivo en [`PROVENANCE.md`](../../PROVENANCE.md), como la consulta original a PubChem. |

Qué cambió durante el evento: antes, MolChat **sugería y esperaba** a una persona en cada paso. Ahora **un plan aprobado una vez se ejecuta solo**, se recupera de los fallos de cada molécula y declara lo que no pudo hacer. La ciencia, la identidad y las decisiones de Preparación siguen siendo de MolDesign: MolChat no calcula ninguna energía ni toma ninguna decisión humana.

## Cómo comprobarlo

| Qué | Dónde |
|---|---|
| La demo, de principio a fin | [Vídeo de 3 minutos](https://www.youtube.com/watch?v=luRIXlqWy6I) |
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
- **Algunos textos de la demo salen tal como los escribe MolDesign**, como un código de aviso (`ESTEREOQUIMICA_NO_DECLARADA`) y el estado del trabajo de Molcy.
