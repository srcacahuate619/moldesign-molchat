# MolChat — texto de candidatura y evidencias

> Traducción de [la versión inglesa](../en/SUBMISSION.md), revisada el 2026-11-03. La referencia para los jueces es el inglés.

El texto está listo para adaptarlo al formulario. No se han inspeccionado sus campos ni límites de caracteres y no se ha enviado ninguna candidatura desde este chat.

## Nombre

MolChat

## Descripción en una línea

De una hipótesis molecular a un cuaderno auditable con una sola aprobación.

## Descripción breve

MolChat ayuda a investigadores de química computacional a coordinar una campaña corta de docking en MolDesign. Muse Spark Open resuelve identidades moleculares y propone un plan estructurado. El investigador revisa candidatos, receptor, condición de parada, límites de tiempo y entregables, y aprueba una vez. Un harness determinista ejecuta el flujo aprobado, registra fallos y candidatos omitidos, y entrega un cuaderno con fuentes, el paquete de auditoría de Preparation y un vídeo opcional de Molcy en un ZIP verificable.

## Descripción del proyecto

Una hipótesis molecular exige resolver identidades, conservar el orden de candidatos, reconocer cuándo detenerse, distinguir fallos de resultados y reunir evidencia para que otra persona pueda inspeccionarla.

Construimos el flujo del agente MolChat y su integración con MolDesign alrededor de esa transferencia. Muse Spark Open, servido por Baseten como `meta-models/muse-spark-open-1026`, elige herramientas estructuradas como `pubchem_lookup` y `propose_iteration`. El código valida argumentos y presenta una tarjeta de aprobación. Su SHA-256 vincula la aprobación al plan; después, un ejecutor determinista coordina las herramientas científicas existentes de MolDesign.

En la demo grabada de seis candidatos contra VMAT2, el flujo se detuvo cuando el quinto, ketanserina, cumplió el umbral de Vina y los controles físicos aprobados. Dos campañas posteriores reprodujeron la entrega con tres candidatos: se evaluó aspirina, ketanserina cumplió y valbenazina quedó sin evaluar. Ambas entregaron una auditoría real y un vídeo renderizado.

Publicamos 36 prompts reales con dos ensayos iniciales cada uno, todas sus trazas, correcciones verificadas por separado, un benchmark de regresión sin claves y los ZIP originales. El resultado estricto inicial fue 68/72: dos fallos revelaron un criterio incorrecto del evaluador y dos, un campo de presupuesto de tiempo ausente del esquema. La verificación posterior también detectó la creación anticipada de un caso; conservamos el intento fallido y su corrección.

La contribución es la coordinación del agente, el cumplimiento de la aprobación y la procedencia de los resultados. Vina, el renderizador, Moldex y Preparation ya existían en MolDesign. La coordinación correcta no demuestra actividad biológica y el dictamen `REVIEW` de Preparation permanece sin resolver.

## Uso del modelo de Meta

Muse Spark Open elige llamadas a herramientas y completa el plan propuesto. MolChat devuelve los resultados reales al modelo, valida esquemas cerrados y controla las acciones. El harness lee los resultados de docking de MolDesign y arranca un plan propuesto a través del endpoint de aprobación. Las trazas registran modelo, llamadas, argumentos validados, resultados y tiempos; excluyen credenciales y razonamiento interno.

## Enlaces para la entrega

| Campo | Enlace |
|---|---|
| Repositorio | [moldesign-molchat](https://github.com/srcacahuate619/moldesign-molchat) |
| Versión congelada | [meta-hackathon-2026-submission](https://github.com/srcacahuate619/moldesign-molchat/tree/meta-hackathon-2026-submission) |
| Demo | [Grabación de tres minutos](https://www.youtube.com/watch?v=luRIXlqWy6I) |
| Evaluación | [Resultados y gráficas](../../benchmarks/RESULTS.md) |
| Invocación real al proveedor | [META_EXECUTION.md](../../docs/META_EXECUTION.md) |
| Verificación final | [Release check](../../benchmarks/published/release-check/README.md) |
| Contribución y reutilización | [Guía del hackathon](HACKATHON.md) |
| Limitaciones y correcciones | [Hallazgos](../../benchmarks/FINDINGS.md) |

## Entrega

Usa la versión congelada y estos enlaces en el formulario. Conserva la distinción entre regresiones simuladas, ensayos reales del modelo y campañas de docking. La cápsula de navegador emula algunas funciones de escritorio; Tauri nativo, WebView2 y el instalador en una máquina limpia siguen sin validar. Estos ejemplos no establecen eficacia farmacológica ni una tasa general de fiabilidad del modelo.
