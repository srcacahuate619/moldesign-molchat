# Base del harness y frontera con MolDesign

## Punto de partida

La validación manual de creación de casos corresponde al flujo incorporado en
MolChat `5401be2` y al receptor local de MolDesign. Esta copia parte de
`f3ae12f`: conserva ese flujo y añade las correcciones posteriores para casos
existentes y errores de voz. El receptor de MolDesign estaba sin commit en
`D:\moldesign-build`; el commit de MolChat por sí solo no reconstruye el
recorrido completo. No debe sustituirse el receptor probado sin comparar y
probar sus cambios locales.

El último `master` público de MolChat consultado es `b88a72d`; la `main` pública
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

Se han preparado el cliente PubChem de MolChat, el control de permiso por
cuenta, un ciclo de llamadas estructuradas y herramientas con ejecutores
inyectados. La copia aislada conecta al chat PubChem, casos y propiedades para
proveedores que implementen el protocolo de herramientas compatible con OpenAI;
los demás conservan el flujo previo. La selección de referencias se persiste
por conversación y cuenta. Se han probado con transportes y modelo simulados;
no se han probado con Baseten real y esta rama no está instalada en MolDesign.
El paquete aislado pasó una prueba con dos procesos reales y un modelo local
simulado. El receptor de casos de MolDesign también pasó sus pruebas propias;
eso no sustituye la prueba completa del usuario en Tauri.

Para probarlo con el backend de desarrollo existente, generar primero el
paquete de prueba con `stage_molchat.py --destino` y lanzar Tauri con
`MOLDESIGN_MOLCHAT_DIR` apuntando al paquete y `MOLCHAT_PERMITIR_EXTERNO=1`.
El backend actual aún contiene el endpoint antiguo de PubChem, pero la
herramienta de esta rama no lo llama. Al incorporar la rama, retirar ese
endpoint antiguo junto a su implementación y pruebas, conservando permisos,
receptor de casos y cambios locales del host.

Antes de integrar en el host: probar el recorrido real en Tauri con el receptor
de casos y validar el contrato de Baseten, incluyendo fallos del proveedor. La
consulta sigue siendo informativa: puede mostrar propiedades y SMILES devueltos
por PubChem, pero no modifica el editor ni el campo SMILES de MolDesign.
Las demás herramientas no están conectadas al nuevo ciclo y deben añadirse sin
regresar a una clasificación determinista anterior al modelo.
