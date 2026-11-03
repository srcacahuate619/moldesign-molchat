# Historial de cambios

## No publicado

- MolChat habla inglés cuando MolDesign está en inglés. Antes la interfaz ya cambiaba de idioma, pero todo lo que escribe
  el servidor salía en castellano. Ahora cada mensaje del chat lleva el idioma de la interfaz (`lang`). Con él:
  - el modelo recibe la instrucción de contestar en inglés;
  - lo que escribe el anfitrión sale en ese idioma: la tarjeta del plan, los avisos y motivos de cada molécula, el resumen
    final, el cuaderno en Markdown y PDF, y el ZIP de entrega (carpetas `notebook/` y `preparation/`, `README.txt`);
  - un plan conserva el idioma en que se propuso, también si termina en segundo plano o se consulta desde otra petición.
  Sin `lang`, o con un idioma desconocido, todo sigue en castellano. Los avisos de cada corrida se copian tal como los da
  MolDesign, que hoy los escribe en castellano.

- El cuaderno de la iteración ya no tira lo que MolDesign y PubChem dijeron (revisión de la entrega de 12 ligandos de VMAT2):
  - **procedencia de cada SMILES**: cada consulta a PubChem borraba la anterior, así que un plan armado sobre doce consultas
    sólo conservaba la última. Ahora la conversación guarda todas (sólo la identidad: CID, nombre, página y los dos SMILES)
    y el plan enlaza cada molécula con la consulta cuyo SMILES coincide literalmente. Dice si coincide con la conectividad
    pero no con la estereoquímica, si es ambigua o si no hay ninguna; nunca la adivina;
  - **registro por molécula**: el protocolo ejecutado (motor, exhaustividad, poses, semilla, caja), los avisos científicos
    de la corrida, la especie acoplada (protonación, tautómero, estereoquímica perdida) y el receptor, copiados del resultado
    de `GET /evaluation/status` que antes sólo se leía para la energía;
  - **condiciones de las corridas**: qué fue igual en todas, qué cambió y qué no se registró, para saber si las energías se
    comparan en las mismas condiciones. Lo no registrado no se da por igual.

- La interfaz informa al anfitrión de lo que está haciendo en una línea (`molchat-ui-status`): un plan esperando aprobación,
  «Evaluando 2 de 3 · última Vina −7.2», el vídeo en curso o el resultado. Con el panel minimizado, MolDesign lo enseña en
  una burbuja. El cuadro de escribir vuelve a quedar abajo (el commit anterior le quitó el alto a la sección del chat).
- Cuarto ensayo en la app: una corrida fallida y rápida dejó que el editor volviera a la molécula anterior y se evaluó la
  equivocada; y Vina se quedó sin memoria porque el equipo estaba saturado. Ahora Vina sin memoria se repite una vez tras
  20 s (sólo ese fallo) y el anfitrión comprueba la molécula antes de pulsar. La sección del chat ya no tiene una segunda
  barra de scroll: sólo se desplaza la lista de mensajes, y «Mensajes nuevos» va pegado abajo dentro de ella.
- Tercer ensayo en la app, todo el flujo funcionó; ajustes:
  - el vídeo se puede personalizar desde el chat con todos los controles de Molcy (formato *prueba*, título, receptor,
    colores de receptor, residuos destacados y líneas, etiquetas, contactos, muestra anterior, movimiento del Ensamble);
    la tarjeta lo enseña y la pestaña de Molcy lo aplica a la vista;
  - la tarjeta muestra la línea de tiempo del plan (caso, receptor, moléculas, Moldex, vídeo con su avance, Preparación,
    entrega);
  - mientras el vídeo sigue, el botón dice «Descargar ahora (sin el vídeo)» y avisa; las descargas y «el vídeo ya está en
    la entrega» llegan al panel de actividad de MolDesign (acción `notify_download`);
  - el cuadro de texto crece con lo escrito (Enter envía, Shift+Enter salta de línea), la conversación sigue al último
    mensaje salvo si se está leyendo más arriba (con un botón «Mensajes nuevos») y su scroll no arrastra la página.
- Segundo ensayo en la app: el bucle funcionó (tres moléculas, parada en la que cumplía, guardado y vídeo encolado), pero
  Preparación respondió «la ventana no pudo atender» y el plan se quedó esperando al render. Cambios:
  - el vídeo se renderiza **en segundo plano**: Preparación, el cuaderno y el ZIP no lo esperan; `complete_video` sigue el
    render y rehace la entrega con el MP4 en la misma carpeta, y la tarjeta lo dice mientras espera;
  - el vídeo lo prepara **la pestaña de Molcy a la vista** (nueva acción de host `molcy_render`,
    `/v1/molcy-requests/{id}/result`): elige corrida, escena y formato y pulsa su propio botón; si no puede, dice por qué.
- La evaluación de cada molécula es una pieza propia (`workflows/evaluation.py`) con dos señales explícitas: el
  **backend** dice cuándo terminó la corrida y cuánto dio Vina (por `task_id`), y la iteración decide con ese número en el
  acto; la **ventana** dice si el caso puede recibir otra molécula con la nueva acción de host de sólo lectura
  `case_status` (`/v1/case-status-requests/{id}/result`), que sólo se pregunta si el bucle sigue. Sustituye a deducir el
  cierre de la corrida intentando cargar la siguiente. Cada molécula guarda los tiempos medidos (espera del caso, arranque,
  resultado) y el cuaderno los enseña.
- Iteración automática con una sola aprobación (`propose_iteration`, `docs/ITERACION_DE_MOLECULAS.md`): el modelo propone un plan
  cerrado (caso, receptor, hasta 12 moléculas, umbral de Vina, qué guardar) y la persona lo aprueba con un clic ligado al
  hash SHA-256 del plan. A partir de ahí un bucle determinista evalúa cada molécula como un intento aislado —un fallo se
  registra y el bucle sigue; `busy` se reintenta y `unknown` nunca—, y una molécula cumple solo si la energía de Vina de su
  mejor pose está en el umbral **y** los controles físicos de esa pose están en `passed`. Tras elegir, guarda en Moldex, pide
  un vídeo de búsqueda a Molcy y audita la corrida en Preparación en paralelo; el estado de Preparación es el que dicta
  MolDesign y nunca se convierte en una decisión humana. El cuaderno (JSON, Markdown y PDF determinista) y el ZIP de entrega
  (paquete de Preparación intacto, `MANIFEST.json` con SHA-256 y lo ausente declarado en `missing`) los escribe el código,
  no el modelo. Rutas `/v1/workflows/{id}` (`run` exige el hash, `cancel`, `files/{name}`) y
  `/v1/preparation-requests/{id}/result`; `MOLCHAT_OUTPUT_DIR` fija la carpeta de salida.
- La iteración espera a que la ventana de MolDesign cierre cada corrida: el primer ensayo en la app evaluó la primera molécula
  y dio por fallidas las demás, porque la interfaz seguía bloqueando el caso (`busy`) y sólo se reintentaba al evaluar, no al
  cargar la molécula. Ahora `busy` se espera en cada llamada al anfitrión (cada 5 s, hasta 240 s y sin pasar del tope del plan),
  la tarjeta lo dice mientras espera y, si no se libera, la molécula falla con ese motivo en vez de como molécula inválida.
  La tarjeta declara que las moléculas se evalúan una tras otra en el mismo caso. Sin el nombre «cribado», que en MolDesign es
  el módulo de lotes: `propose_screening` pasa a `propose_iteration`, `workflows/screening.py` a `workflows/iteration.py` y
  `docs/CRIBADO_AUTOMATICO.md` a `docs/ITERACION_DE_MOLECULAS.md`.
- Acción de host `audit_case_preparation`: la ventana del anfitrión construye la proyección del caso y devuelve el estado que
  su auditoría dictó; el sidecar la audita y exporta con la sesión de la cuenta. Las acciones de host se documentan por
  primera vez en `docs/HOST_CONTRACT.md`.
- `tool_loop` admite argumentos `boolean` y `number` (este último con rango obligatorio) en los esquemas cerrados.
- `README.md`: declaración de qué es previo al hackathon (MolDesign y lo portado, que `PROVENANCE.md` detalla) y qué se
  construyó durante él (este repositorio, desde `d37cc70`).

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
