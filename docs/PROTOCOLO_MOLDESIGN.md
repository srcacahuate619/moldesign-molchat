# Protocolo MolChat ↔ MolDesign, versión 1

Estado: implementación preparada en ramas locales de ambos proyectos; no afirma que haya sido publicada ni validada en un instalador.

MolChat es un proceso independiente. MolDesign lo inicia bajo demanda con el intérprete incluido, tras comprobar el manifiesto y sus hashes. Ambos se hablan por HTTP local; ninguno importa código del otro. Una instancia remota sólo se admite por HTTPS y con autorización explícita del operador.

## Identidad y negociación

El backend de MolDesign entrega al proceso la URL loopback con el puerto real del socket de la API. El lado integrado no deriva ese puerto de la cabecera `Host`. El sidecar recibe un secreto de sesión por entorno y expone un puerto efímero. Antes de considerarlo sano, MolDesign exige `GET /v1/health` con `status: ok` y `contract: moldesign.molchat/1`.

La cuenta pide `POST /molchat-host/session` con su identidad de MolDesign. El host acuña un Bearer `mh1` de vida limitada, con identidad, audiencia, permisos y firma. El iframe recibe esa sesión por `postMessage`, nunca en la URL. El mensaje `molchat-host-session` lleva `token` y puede llevar `locale` (`es` o `en`); la ausencia de `locale` conserva la compatibilidad con hosts anteriores. Un host que declara idioma lo vuelve a enviar al cambiarlo, y el sidecar lo aplica a su interfaz. El host acepta mensajes únicamente de la ventana del iframe y de su origen exacto; la UI del sidecar acepta la sesión sólo de su ventana padre y de un origen local o de Tauri permitido. El token se reenvía por cada petición a MolDesign, sin reutilizar el de otra cuenta.

Antes de consultar propiedades o ejecutar acciones, MolChat consulta `GET /molchat-host/contract` con la sesión vigente. La respuesta declara `contract: moldesign.molchat/1` y una lista de capacidades versionadas. Un contrato desconocido, capacidad ausente, sesión inválida, respuesta inválida o conexión fallida detiene la operación; no se reemplaza por datos de demostración. `platform-actions/1` identifica la superficie de acciones existente, no garantiza que todos los motores y herramientas estén disponibles. Cada operación mantiene sus propias validaciones y condiciones.

Los adaptadores genéricos de terceros no son MolDesign. El kit de conformidad
usa la negociación anterior por defecto y sólo deja de exigirla con el modo
`--adapter generic` y un pack registrado explícitamente. Ese modo no certifica
compatibilidad con MolDesign ni añade autenticación al ejemplo sintético.

## Propiedades `properties/1`

`POST /molchat-host/properties` recibe `{ "smiles": "..." }` y requiere identidad. MolDesign valida y calcula con su implementación de RDKit, sin invocar ADMET-AI. La respuesta declara `contract`, `canonical_smiles`, `source`, `warnings` y `properties` (`mw`, `logp`, `tpsa`, `hbd`, `hba`, `rot_bonds`, `heavy_atoms`, `rings`). Los valores no son actividad biológica ni resultado de docking. Los avisos de validación acompañan la evidencia; un SMILES inválido se rechaza con 422 y no produce valores.

Los planes con efectos conservan la aprobación ligada a huella, idempotencia y reconciliación de CR-06/CR-07. Una respuesta perdida no autoriza reenviar automáticamente una operación de efecto ambiguo. La lista detallada de rutas y sus límites está en `CONTRATO_MOLDESIGN.md`.

## Evolución y verificación

La versión mayor de `moldesign.molchat/1` cambia cuando se rompe una regla existente. Una nueva capacidad se anuncia con su propio identificador versionado; ausencia significa no disponible. Nunca se asume compatibilidad por coincidencia de versiones del producto. Los cambios de ambos proyectos requieren pruebas de rechazo de versiones, identidad y respuestas inválidas, y una prueba entre procesos con el sidecar que se entrega. La compilación de MolDesign debe verificar la copia vendorizada, la CSP del iframe y el inventario del instalador. La publicación de cada commit y la prueba del instalador son pasos separados de estas pruebas locales.
