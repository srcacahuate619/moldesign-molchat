# Crear un adaptador

El ejemplo conecta el ejecutor de MolChat a un servidor HTTP sintético, sin
datos ni cálculos científicos. Requiere Python 3.11+, el repositorio fuente y
`python -m pip install -e '.[dev]'`. Los comandos siguientes se ejecutan desde
la raíz; en Windows PowerShell configura `$env:PYTHONPATH='src;.'` y en shells
Unix ejecuta `export PYTHONPATH=src:.`.

1. En una terminal ejecuta `python examples/reference_backend/server.py`.
   El servicio solo escucha en `127.0.0.1:8099`.
2. En otra terminal configura `MOLDESIGN_TOKEN` con cualquier texto de prueba
   (PowerShell: `$env:MOLDESIGN_TOKEN='example-session'`; Unix:
   `export MOLDESIGN_TOKEN=example-session`). El nombre es heredado del
   transporte; el servidor de ejemplo no autentica ese valor.
3. Ejecuta:

   ```text
   python -m conformance.runner --adapter generic --register molchat_agent.tools.reference --cases examples/reference_backend/cases --live --base-url http://127.0.0.1:8099
   ```

Comprueba que no haya fallos y que las comprobaciones `1b`, `3b` y `5b`
pasen. El kit también lista como omitidas las capacidades de MolDesign que
no están en los casos de este ejemplo: esos skips no certifican ese catálogo.
Para detener el servidor usa Ctrl+C. El test `tests/test_reference_backend.py`
levanta el servicio en un puerto libre y verifica las tres patas en vivo.

## Construir el propio

1. Define capacidades con nombres únicos mediante `Capability` y `register`,
   como en `src/molchat_agent/tools/reference.py`: método y ruta fijos,
   campos con tipo y límites, riesgo, clase epistémica, procedencia y salidas
   permitidas para bindings. No registres destinos o rutas dados por el modelo.
   El registro es global y actualmente una colisión reemplaza la entrada
   previa: evita reutilizar nombres de otros paquetes.
2. Implementa el contrato HTTP y crea un JSON de casos como el del ejemplo,
   con argumentos válidos para cada capacidad, lectura segura (`live_read`),
   entidad inexistente (`bogus_args`) y un oráculo estable de estado. Las
   rutas de OpenAPI deben declarar los métodos realmente servidos.
3. Importa el módulo con `--register`, apunta `--cases` a tu directorio y
   ejecuta primero sin `--live` y después con él. Selecciona explícitamente
   `--adapter generic` para una API ajena a MolDesign: este modo no negocia el
   contrato de MolDesign ni lo declara compatible. El modo predeterminado
   `moldesign` exige la negociación, incluso con packs registrados; si es
   incompatible, la prueba falla en vez de ocultarlo como un skip. El transporte
   `MolDesignBridge` también sirve otros contratos HTTP al configurarlo
   explícitamente con `require_contract=False`, con Bearer y política
   de URL: loopback por defecto; remoto solo HTTPS y con autorización explícita
   `MOLDESIGN_ALLOW_REMOTE=1`. La integración actual no ofrece aún un selector
   general de adaptador en la CLI o la UI: registra el pack en tu proceso e
   inyecta el bridge al `AgentExecutor`. La conversación y las herramientas de
   dominio siguen teniendo partes específicas de MolDesign.
4. Revisa cada PASS, FAIL y SKIP. Las patas offline usan un doble de transporte:
   prueban validación y control del ejecutor, no el servidor real. En vivo,
   OpenAPI comprueba rutas; el oráculo compara estado antes y después de las
   lecturas declaradas; el caso inexistente comprueba la abstención. Un oráculo
   incompleto, una ruta omitida o un skip no demuestran conformidad. El kit no
   prueba por sí solo autorización, aislamiento, idempotencia ni ausencia de
   efectos en todas las condiciones.

Las operaciones reales con efectos requieren autorización y revalidación en
el servidor, idempotencia y reconciliación ante respuestas perdidas. El ejemplo
mantiene solo un contador en memoria y no implementa esas garantías: úsalo
únicamente en loopback para aprender el contrato. No publiques credenciales ni
resultados privados en los casos de prueba.
