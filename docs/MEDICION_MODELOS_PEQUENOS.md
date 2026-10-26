# Medición de modelos pequeños — línea base (F2-C5)

Por qué existe este documento: los modelos pequeños planifican con fluidez
y se equivocan con fluidez. Esta medición formal es la línea base que
justifica la capa determinista (código construye números, el modelo explica)
en vez de confiarle planificación libre a un LLM local.

## Métrica: "válido y sin inventados y sin pasos extra"

Por objetivo de planificación, limpio ⟺ las tres:

1. **Válido**: `Plan.from_dict` acepta y todos los pasos son `risk == read`.
2. **Sin inventados**: todo valor string de argumentos (len ≥ 2) aparece
   verbatim en el objetivo (insensible a mayúsculas). `rationale` excluido.
3. **Sin pasos extra**: `len(steps) <= max_steps` del objetivo.

Corredor: `scripts/measure_small_models.py --model <nombre>` (usa el puerto
`LLMProvider` contra un servidor local; objetivos en
`tests/quality/small_model_goals.json`).

## Objetivos (4)

| ID | Objetivo | max_steps |
|---|---|---|
| G1 | Lista los receptores disponibles | 1 |
| G2 | Audita el ligando CCO contra el receptor 1HSG sin docking | 2 |
| G3 | Muestra mi historial de evaluaciones | 1 |
| G4 | Revisa el estado de la evaluación en curso | 2 |

G4 no da ningún identificador: emitir `task_id`/`proposal_id` ahí es inventar.

## Resultados

| Modelo (cuant.) | G1 | G2 | G3 | G4 | Limpios |
|---|---|---|---|---|---|
| Qwen2.5-1.5B-Instruct Q4_K_M | ✗ | ✗ | ✗ | ✗ | **0/4** |
| Bonsai-8B Q1_0 | ✗ | ✗ | ✗ | ✗ | **0/4** |

### Qwen2.5-1.5B-Instruct Q4_K_M (2026-10-26, llama-server CUDA, este repo)

0/4, los cuatro **rechazados por el validador** (modo de fallo: eco de
esquema — emite fragmentos del JSON Schema como argumentos):

- G1/G2/G4: `list_targets: parámetros sobrantes ['type']` (G4 también
  `additionalProperties/properties/required`).
- G3: `target_pdb_id: demasiado largo` (alucinó un valor largo).

Latencias ~2.5–3.6 s por objetivo. El validador local sostiene: ningún plan
malformado llega a ejecución.

### Bonsai-8B Q1_0 (2026-10-26, llama-server CUDA, este corredor)

0/4 limpios, los cuatro **formalmente válidos pero con identificadores
inventados en pasos extra** (5 pasos por objetivo; reproduce la sonda del
supervisor, que vio 2+2 por varianza de muestreo — mismo veredicto):

- G1: `Smiel`, `1ABC`, `AutoDock`, `TASK123456`, `PROPOSAL789012`.
- G2: `None`, `COCO-1HSG-001`, `PROPOSAL-1HSG-001`.
- G3: (`123456789012345678901234567890` como SMILES), `1ABC`, `AutoDock`,
  `EVAL-123456`, `PROPOSAL-789012`.
- G4: `PDB123456`, `TASK123456`, `PROPOSAL789012` (G4 no da ningún
  identificador: cada uno es invención pura).

Modo de fallo: plan "todo incluido" que toca cada capacidad con argumentos
fabricados. Sin la regla "sin inventados", estos planes parecerían buenos.

## Lectura

- Ningún modelo pequeño medido planifica limpio: o rompe el contrato (Qwen)
  o lo cumple con datos inventados (Bonsai). La planificación libre no es
  fiable en este rango; la capa determinista no es opcional.
- El validador local (`Plan.from_dict` + allowlist) es el freno que
  convierte esos fallos en abstención en vez de ejecución.
