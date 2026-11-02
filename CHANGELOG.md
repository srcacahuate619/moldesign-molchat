# Historial de cambios

## No publicado

- Herramienta de solo lectura `compare_poses`: compara dos poses de una evaluación terminada con la evidencia estructural que
  MolDesign declara (energía de Vina y su diferencia, controles físicos de PoseBusters —solo `passed` es válida—, lo que dijo
  el selector y las incertidumbres de la corrida) y con los contactos de cada pose, cuya diferencia calcula el código. No
  declara ganadora, no da por buena una pose sin controles y, tras la respuesta, el host añade el estado físico de cada pose
  tal como lo declara MolDesign (`docs/CREACION_DE_HERRAMIENTAS.md`). Necesita un MolDesign con
  `GET /evaluation/pose-comparison/{task_id}`.
- `compare_poses` ya no dice que las cotas de RMSD de Vina «no son una distancia entre estas dos poses» cuando una de las dos es la
  mejor pose de Vina (entonces sí lo son): MolDesign devuelve `difference.vina_rmsd_between_poses` solo cuando valen para ese par
  (búsqueda de un solo conformador y una de las dos es la mejor), el host las redacta como cotas —no un intervalo de confianza, y
  no dicen cuál pose es la correcta— y, si no valen, dice por qué y no estima nada.
- Una lista con cero contactos tipificados en una pose deja de leerse como ausencia de interacción: `contacts.conclusive` es falso,
  `contacts.caution` la explica según la química del receptor que MolDesign declara (`receptor_chemistry`) y el host la añade a la
  respuesta.
- `compare_poses` entrega la distancia entre las dos poses medida desde sus coordenadas (`difference.pose_rmsd_between_poses`,
  que calcula MolDesign): sirve para cualquier par, también 2 contra 3, donde las cotas de Vina no valen. El host la redacta con su
  correspondencia atómica (átomos pesados, sin superponer, simétrica y por orden de átomo) y, cuando está, la prefiere a las cotas.
  Si MolDesign no pudo medirla, lo dice y no la estima.
- Los controles físicos de cada pose llegan con nombre y resultado (`checks_detail`) y aparecen como filas de evidencia («controles
  que fallan», «controles superados»); si la corrida solo guardó el recuento, la fila dice que el detalle no está guardado en vez de
  resumirlo como «22 controles pasados».
- Las cifras ya verificadas de un turno se conservan en los siguientes de la misma conversación: cada mensaje del asistente guarda
  sus `verified_numbers` y el turno siguiente las recupera de ahí, de modo que al rechazar un intervalo de confianza que no existe
  no se pierden las energías ni el RMSD que ya se habían citado. No conservan ningún número que ninguna herramienta devolvió ni
  cruzan de una conversación a otra.
- Las frases que escribe el host al final de una respuesta (controles físicos, RMSD, cero contactos) se añaden una sola vez, aunque
  se lea el mismo par dos veces en el turno.
- `compare_poses` distingue dos cuentas que una respuesta mezcló («tres contactos compartidos» y «cuatro residuos en común»): el
  contacto compartido es el mismo tipo en el mismo residuo, y un residuo puede estar en las dos poses con otro tipo en cada una.
  El resultado trae `residues_in_both_count` y `residues_with_different_types` (con los tipos de cada pose) y el host escribe las
  dos cifras y los residuos que difieren, solo cuando hay algo que reconciliar.
- Cada contacto lleva, cuando MolDesign los reporta, los átomos que usó el detector (`atoms`, con sus índices) y sus ángulos
  (`angles_degrees`: `DHA_angle`, `AXD_angle`, `XAR_angle`...), para que una persona pueda comprobarlo a mano. Dos tipos de
  contacto que se apoyan en los mismos átomos (`overlapping_criteria`) se cuentan como un solo contacto con dos criterios; para un
  puente salino y un enlace de hidrógeno, el host lo dice en la respuesta. Sin índices atómicos (un MolDesign anterior) no se
  afirma ningún átomo ni solapamiento.
- Un contacto iónico (puente salino, catión–π) se declara válido solo para la especie que se acopló: MolDesign entrega
  `ligand_species` (si la protonación cambió la entrada, con qué motor, a qué pH y cuántas alternativas quedaron sin evaluar) y,
  cuando cambió, el host lo añade a la respuesta. No dice cuál especie predomina.
- Una diferencia con PubChem en TPSA o aceptores de hidrógeno se explica automáticamente, pero solo si un cálculo de MolDesign la
  reproduce: `POST /molchat-host/properties` devuelve ahora `variants` (los mismos descriptores con la definición alternativa y
  su método), y el host escribe la nota cuando la variante redondeada a lo que imprime PubChem da su cifra. Si ninguna la
  reproduce, dice que la diferencia no queda explicada; sin variantes (un MolDesign anterior), no añade nada.
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
