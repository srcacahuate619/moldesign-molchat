# Seguridad y privacidad — MolChat Agent (v1, Fase 2)

## Modelo de amenazas (4 frentes del gate)

1. **Inyección.** En Fase 2 no hay tool-loop del modelo: el motor rutea
   determinísticamente y `ToolBackend.properties` ni siquiera acepta
   identidad como parámetro (test estructural). El texto de terceros
   (PubChem/ChEMBL/PDB) no existe aún en el turno (Fase 5); cuando llegue,
   nunca será instrucción: las herramientas se eligen del catálogo.
2. **Fuga entre usuarios.** Toda fila lleva dueño; leer/escribir/borrar/buscar
   filtran por `user_id` y lo ajeno responde igual que lo inexistente.
   Suite: `tests/adversarial/test_gate.py` + `tests/conversation/test_memory.py`.
3. **Tool-calls inválidos.** Herramienta desconocida, argumento inválido o
   SMILES no registrado → `ToolError` → abstención sin números. Un SMILES
   alucinado no llega a la herramienta (intento `invalid_smiles`).
4. **Alucinación.** Los números los construye código desde valores de
   herramientas. El texto del LLM conceptual se verifica número a número;
   lo no respaldado se retiene con `Nota de verificación:`. Clases
   epistémicas en cada bloque de evidencia; errores como abstención.

## Fronteras

- **Red**: loopback por defecto; remoto solo HTTPS + consentimiento por
  destino `proveedor@host` (otorgado antes del primer byte, revocable,
  sin herencia); `MOLCHAT_OFFLINE=1` manda sobre todo permiso.
- **Datos por llamada** (consentimiento de destino ≠ de contenido):
  - `plan()` remoto: objetivo + catálogo. Nunca resultados ni historial.
  - `chat()` remoto: sistema + consulta. Historial, resúmenes y resultados
    científicos solo con consentimiento de contenido (`huella+history`,
    `doctor --grant-content`, revocable con `--revoke`). Sin él, el motor
    los omite; el modo offline bloquea igual con ambos otorgados.
  - Proveedores locales: contexto completo (nada sale de la máquina).
- **Secretos**: solo entorno/memoria; redactados en `doctor`, planes y
  reportes; `check_secrets.py` en cada fase y (Fase 7) en CI.
- **Datos científicos**: el planificador remoto recibe objetivo+catálogo,
  nunca resultados ni historial. Enviar resultados a la nube exige
  consentimiento específico con vista previa (Fase 5).
- **Negativos fabricados**: prohibidos. "Sin alertas" solo con catálogo
  cargado/registro evaluado; si no, "no evaluado" explícito (PAINS).
- **Persistencia**: los fallos de SQLite son ruidosos
  (`PersistenciaFallida`); un turno que no se guarda lo declara, no lo
  esconde; nunca se declara creado lo que no está en disco.

## Riesgos residuales (declarados, no escondidos)

- La heurística SMILES es estructural, no química: la validez real la da el
  servidor (CR-01). Un falso positivo llega a la herramienta y vuelve como
  error tipado, nunca como número.
- Fixtures grabados: datos reales pero congelados; el runner local
  (`MOLCHAT_QUALITY_PROVIDER`) y la suite de contrato cubren lo vivo.
- Sinrate-limit ni sandbox de sidecar todavía: llegan con `server/` (Fase 4).
