# Hoja de ruta pública

MolChat es un agente independiente que coordina herramientas externas con
planes revisables, aprobación humana para acciones con efectos y evidencia
procedente del sistema científico. MolDesign conserva la identidad, las
autorizaciones y los motores. El código y los resultados de otros proyectos
siguen sujetos a sus propios contratos y licencias.

## Estado y próximos pasos

- El núcleo, proveedores, conversación, orquestación, sidecar y UI cuentan con
  pruebas automatizadas. Se ha probado una integración con MolDesign, pero el
  corte definitivo y la instalación limpia aún requieren verificación.
- En la integración local, las propiedades proceden del contrato `properties/1`
  de MolDesign; sin una plataforma que lo declare, el agente se abstiene. Otras
  capacidades siguen pendientes de sus respectivos contratos y verificaciones.
- El kit y el ejemplo de adaptador muestran cómo probar un contrato HTTP;
  la integración de terceros aún requiere código de registro e inyección.
- La prioridad es completar la verificación de paridad, distribución y
  reversión antes de activar el nuevo sidecar por defecto en MolDesign.
  La fecha de publicación y las versiones compatibles dependen de esas puertas.

Consulta [adaptadores](ADAPTADORES.md), [seguridad](SEGURIDAD.md),
[contrato de MolDesign](CONTRATO_MOLDESIGN.md) y [paridad](PARIDAD.md).
