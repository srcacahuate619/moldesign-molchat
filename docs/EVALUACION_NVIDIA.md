# Prueba del proveedor NVIDIA

Prueba diagnóstica del 28 de octubre de 2026 con ejemplos públicos, perfil
`default` y consentimiento temporal para `openai-compatible@integrate.api.nvidia.com`.
Se usó `nvidia/nemotron-3.5-lightning-30b-a3b` mediante el endpoint
`https://integrate.api.nvidia.com/v1`. La clave se introdujo en memoria y no
se guardó en el repositorio. El coste no se midió.

El catálogo respondió HTTP 200. Otros modelos listados no estaban disponibles
en la prueba: uno respondió 404 y otro 410. Esto no demuestra disponibilidad
futura. La configuración inicial basada en JSON Schema no produjo un plan
válido en esta prueba. La documentación de NVIDIA recomienda modo JSON y
desactivar razonamiento para respuestas estructuradas; la implementación
permite ambas opciones de forma explícita y sigue validando localmente cada
capacidad, argumento e identificador. [Documentación NVIDIA NIM](https://docs.nvidia.com/nim/large-language-models/2.0.10/get-started/advanced/get-started-nemotron-3.5-lightning.html).

## Última ejecución

Una petición por objetivo, sin repetición estadística; temperaturas, catálogo
y prompts son los de la implementación actual, con modo `object` y
razonamiento desactivado. Las latencias observadas fueron 1.06–1.39 s para
los planes. Son mediciones puntuales, no una garantía de servicio.

| Objetivo | Resultado formal | Revisión semántica |
|---|---|---|
| Listar receptores | Válido | Adecuado: `list_targets` |
| Auditar CCO en 1HSG sin docking | Válido | Adecuado: `check_preflight` con los identificadores solicitados |
| Mostrar historial de evaluaciones | Válido | Adecuado: `list_evaluations` con paginación |
| Revisar estado de evaluación en curso sin identificador | Válido | Fallo: lista evaluaciones **y receptores**, paso ajeno al objetivo; no inventó un ID de trabajo |

Se observó respuesta de chat no vacía, sin evaluación semántica independiente.
Además, un plan del modelo con catálogo limitado a `reference_status` se
ejecutó contra el servidor sintético local y devolvió `example-1` con estado
`completed`. No es una prueba de ejecución científica real ni sustituye las
pruebas pendientes con MolDesign, proveedores locales o instalación limpia.

La evaluación simple basada solo en validez y máximo de pasos no detectaría
necesariamente el paso adicional del último caso. Por ello se conserva la
revisión semántica y no se declara completada la tarea 2.10 del plan.

## Configuración optativa

Configura `MOLCHAT_PROFILE=default`, `MOLCHAT_PROVIDER=openai-compatible`,
`OPENAI_COMPAT_BASE_URL=https://integrate.api.nvidia.com/v1`,
`OPENAI_COMPAT_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b`,
`OPENAI_COMPAT_JSON_MODE=object` y `OPENAI_COMPAT_DISABLE_THINKING=1`.
Proporciona `OPENAI_COMPAT_API_KEY` de forma privada en el entorno del proceso.
Después autoriza explícitamente el destino con `molchat-agent doctor
--grant-consent openai-compatible@integrate.api.nvidia.com`. El perfil
`hackathon` no habilita este proveedor remoto; la prueba no cambió esa regla.
No envíes datos privados sin los consentimientos correspondientes y revisa
todo plan antes de ejecutarlo.
