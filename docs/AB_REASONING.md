# A/B de `reasoning_effort` — informe (tarea 2.9, 2026-10-26)

## Método

- Modelo: `muse-spark-1.3` (Standard) vía Meta Model API, clave temporal del
  propietario, solo para este experimento. Variante a confirmar por el
  propietario en el portal de créditos; ningún dato privado salió en la
  corrida (las metas son consultas públicas de la quality suite).
- Metas: las 30 consultas tool-facing de la quality suite (B/C/A/D/R/H/L/V),
  como objetivos de planificación. Corredor: `scripts/ab_reasoning.py`, por
  el gate de consentimiento (`meta@api.meta.ai` otorgado en fichero temporal).
- Niveles: `medium`, `high`, `xhigh` (90 llamadas en total).
- Métrica: plan formalmente válido (`Plan.from_dict` OK + todos los pasos
  `read`). No mide ajuste semántico (eso lo cubre la quality suite conversacional).

## Resultado

| Nivel | Válidos | p50 | max | Pasos |
|---|---|---|---|---|
| medium | 30/30 | 4048 ms | 6381 ms | 1–2 |
| high | 30/30 | 4739 ms | 6325 ms | 1–2 |
| xhigh | 30/30 | 12540 ms (max) / 7090 ms (p50) | 12540 ms | 1–2 |

Datos crudos: `docs/ab_reasoning_20261026.json`.

## Decisión

**El default `medium` se mantiene.** Más razonamiento no aporta validez
(90/90 en los tres niveles, cero errores) y cuesta latencia monótona
(+17% high, +75% xhigh en p50). Revisar si cambian el modelo, el catálogo
o la métrica (p. ej. validez semántica), o si `high` demuestra valor como
segundo intento tras error de validación (§6.1.1).
