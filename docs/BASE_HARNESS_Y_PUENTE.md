# Base del harness y frontera con MolDesign

## Punto de partida

La validación manual de creación de casos corresponde al flujo incorporado en
MolChat `5401be2` y al receptor local de MolDesign. Esta copia parte de
`f3ae12f`: conserva ese flujo y añade las correcciones posteriores para casos
existentes y errores de voz. El receptor de MolDesign estaba sin commit en
su repositorio de desarrollo; el commit de MolChat por sí solo no reconstruye el
recorrido completo. No debe sustituirse el receptor probado sin comparar y
probar sus cambios locales.

En el momento de preparar esta base, el último `master` público de MolChat era `b88a72d`; la `main` pública
de MolDesign consultada es `e89e2939`. Ninguno de los nueve commits locales de
MolChat posteriores a `b88a72d` estaba publicado cuando se consultó. La marca
`oficial: true` de una fijación local no demuestra que ese commit sea público.

Se preserva por separado la línea posterior que añadió PubChem, el selector de
rutas y el experimento de herramientas. Esta rama no reinicia ni borra esa línea.

## Propiedad de las herramientas

- MolChat: catálogo para el modelo, esquemas, ciclo, contexto, adaptadores de
  proveedores, consultas a fuentes públicas y presentación de resultados.
- MolDesign: identidad, permisos de cuenta y estado del producto; ejecuta sus
  operaciones reales, por ejemplo crear un caso y actualizar la lista.
- Puente: transporte y contrato autenticado. MolChat consulta la autorización
  de un destino y solicita operaciones del producto; el host devuelve estados
  verificables. El host no implementa la consulta PubChem para el agente.

El permiso se consulta con la sesión autenticada antes de cada solicitud de
PubChem. El adaptador de red de MolChat debe usar un cliente HTTP sin proxies
del entorno y con redirecciones desactivadas. Revocar el permiso o activar el
modo sin red bloquea las peticiones posteriores. Evitar cambios en el host
hasta verificar la transición: retirar el endpoint anterior también requiere
ajustar su contrato y sus pruebas, sin eliminar el control de permisos.

## Estado de esta rama

MolChat dispone de consulta PubChem autorizada, un ciclo de llamadas
estructuradas, creación de casos, consulta de propiedades, exploración de
receptores, carga de SMILES, comparación de estructuras y solicitud de asignación
de receptor. Las operaciones sobre casos requieren un host de MolDesign con
los receptores correspondientes. La selección de referencias se persiste por
conversación y cuenta. Hay pruebas automatizadas con proveedores y transportes
simulados y pruebas manuales de varias funciones con Baseten; la asignación
del receptor necesita aún una prueba manual completa en Tauri.

Para probarlo con el backend de desarrollo existente, generar primero el
paquete de prueba con `stage_molchat.py --destino` y lanzar Tauri con
`MOLDESIGN_MOLCHAT_DIR` apuntando al paquete y `MOLCHAT_PERMITIR_EXTERNO=1`.
La consulta de PubChem es informativa; cargar un SMILES o asignar un receptor
son operaciones separadas que solicitan una acción al host y necesitan su
confirmación. La publicación de MolChat no incluye ni actualiza los receptores
de MolDesign, que deben probarse y publicarse en su propio repositorio.
