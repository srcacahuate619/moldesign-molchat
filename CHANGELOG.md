# Historial de cambios

## No publicado

- Acciones con confirmación: el chat puede proponer **guardar una corrida en Moldex** (`save_to_moldex`) y **pedir un vídeo a
  Molcy** (`request_molcy_video`, con título, colores, receptor visible u oculto, etiquetas y contactos), y seguir un vídeo ya
  pedido (`get_molcy_video_status`, solo lectura). Las herramientas no ejecutan nada: dejan una tarjeta, y solo el botón
  «Confirmar» llama a MolDesign con la sesión de la persona (`/v1/actions/{id}/confirm`; también `/cancel`). Una propuesta caduca a
  los 15 minutos, no sobrevive a un reinicio del sidecar y, tras confirmarla, un segundo clic devuelve el resultado en vez de
  repetirlo. La respuesta del turno la escribe el host («Todavía no se hizo nada») y una frase del modelo que diga «guardé» o
  «generé el vídeo» se corrige. El cierre de MolDesign es obligatorio y no tiene campo; sin GPU o sin Blender no se propone nada
  ni se instala nada desde el chat (`docs/CREACION_DE_HERRAMIENTAS.md`).
- Herramienta de solo lectura `explain_evaluation`: explica el resultado de una evaluación terminada con los hechos que
  MolDesign declara (afinidad de Vina y sus parámetros, calibración del receptor, avisos científicos y vigencia del
  protocolo), cada uno con su condición y su límite. Los hechos salen de una lista de campos permitidos; lo que MolDesign no
  declara se informa como ausente, nunca como bueno. Al final de la respuesta, el host añade la calibración tal como la
  declara MolDesign (`docs/CREACION_DE_HERRAMIENTAS.md`).
- El verificador de números lee el español: coma decimal (`-9,48`), signo menos tipográfico (`−9,5`) y rangos con guion
  (`0,22-0,54`). Antes partía `-9,48` en dos y lo ocultaba, perdía el signo de `−9.5` y leía el rango como un número negativo.
  Los valores de una evaluación se comparan a la precisión con que se citan (`0,4` respalda `0,39`; `0,3` no).
- Documentación de la llave y de la cerradura con MolDesign (`docs/LLAVE_Y_CERRADURA.md`) y del flujo de desarrollo y de versión propia (`docs/DESARROLLO_Y_VERSION_PROPIA.md`).

- Negociación versionada con MolDesign; modo explícito para adaptadores genéricos.

- Ejemplo de adaptador HTTP sintético con casos y comprobaciones en vivo.
- Guía pública de adaptadores, hoja de ruta, política de versiones y CI.
- La conformidad en vivo señala como fallo una lectura que no se completa.
- Los planificadores externos rechazan ciertos identificadores ausentes del
  objetivo; esto puede requerir que el usuario los indique explícitamente.
- El proveedor compatible informa correctamente errores HTTP y permite optar
  por modo JSON y desactivar razonamiento para servidores que lo requieran.

El historial anterior permanece en Git; no se declara aquí una release previa.
