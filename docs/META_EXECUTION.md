# Muse Spark execution: source, boundaries and evidence

MolChat uses Muse Spark Open to choose structured tool calls and propose a scientific workflow. Python and the MolDesign host validate and execute those calls. Once a workflow is approved, its execution and stopping decisions are deterministic; they do not ask the model to invent docking results.

## The actual provider call

| Stage | Real function and source | Responsibility |
|---|---|---|
| Account configuration | [`ServerState.registro_de_turno`](../src/molchat_agent/server/state.py), [`registro_del_turno`](../src/molchat_agent/providers/alojado.py) | Read the account's active provider and obtain its per-turn credential through the authorized MolDesign bridge. |
| Hosted conversation | [`chat` / `_harness_turn`](../src/molchat_agent/server/app.py) | Construct the authorized context, available tools and final evidence-backed answer. |
| Model/tool protocol | [`run_tool_loop`](../src/molchat_agent/conversation/tool_loop.py) | Call `provider.chat_with_tools`, validate tool names and arguments, execute allowed implementations, and return tool results to the model. |
| HTTP inference | [`OpenAICompatibleProvider.chat_with_tools`](../src/molchat_agent/providers/openai_compatible.py) | POST the model identifier, messages and function schemas to `/chat/completions`; return the assistant message or a provider error. |
| Destination | [`baseten-hackathon` catalogue entry](../src/molchat_agent/providers/catalogo.json) | `https://inference.baseten.co/v1`, model `meta-models/muse-spark-open-1026`. This is distinct from the separate Meta Model API entry. |

The measured live traces record the configured model, rather than inferring it from a product label. [`E01-r1.json`](../benchmarks/published/live/E01-r1.json) shows a genuine `compute_properties` call to MolDesign. [`H10-r1.json`](../benchmarks/published/live/H10-r1.json) shows PubChem resolution followed by a pending workflow proposal whose molecular identities are checked against returned SMILES.

## Tools actually observed

The [complete prompt suite](../benchmarks/prompts.json) contains 12 easy, 12 moderate and 12 hard tasks, each run twice against the real services. The published [per-trial table](../benchmarks/RESULTS.md) links every requested call, validated argument, result, latency and final harness answer.

| Tool | Implementation | Evidence |
|---|---|---|
| `compute_properties` | [`properties_tool`](../src/molchat_agent/conversation/harness_tools.py), using MolDesign's `PlatformBackend` | Real descriptors, source, methods, canonical identity, and honest invalid-input handling. |
| `pubchem_lookup` | [`pubchem_tool`](../src/molchat_agent/conversation/harness_tools.py), [`search_compounds`](../src/molchat_agent/conversation/pubchem.py) | Compound identity resolution and a deliberately nonexistent compound. Network permission is checked through MolDesign. |
| `search_receptors` | [`receptor_catalog_tool`](../src/molchat_agent/conversation/harness_tools.py) | Real account-scoped catalogue search, including an empty result. Availability is not scientific validation. |
| `propose_iteration` | [`propose_iteration_tool`](../src/molchat_agent/workflows/tool.py) | Exact candidate order, threshold, physical-check requirement, stop policy, outputs and time budgets in a pending approval card. |

Optional `suggest_next_actions` calls are preserved in traces. Other tools in the schema are available capabilities, not evidence that the model used them in a particular task. The browser campaign's [chat response](../benchmarks/published/capsule/execution.json) and [notebook](../benchmarks/published/capsule/notebook.md) connect resolved PubChem identities to the plan that actually ran.

## What the harness permits

1. **Closed arguments.** `_arguments` rejects unknown tools/fields, wrong types, missing required fields, unbounded numerical schemas and non-finite numbers. `IterationSpec.from_dict` checks the actual plan, including duplicate SMILES, negative threshold range, candidate count and supported time limits. This is contract validation; it does not establish chemical validity or the user's scientific intent.
2. **Bounded conversation.** The hosted path supplies a maximum of 10 model steps. The generic loop accepts a configured limit of 1–12 steps, executes at most 16 calls per step, and refuses a response containing more than 64 calls. Raw argument strings are bounded to 4,096 characters; serialized tool results to 100,000. It does not automatically repeat an operation with an uncertain outcome.
3. **Explicit approval.** A proposal creates a card, not a docking run. [`workflow_run`](../src/molchat_agent/server/app.py) checks the owning session, proposal state, expiry and exact plan digest before starting. A second click on a completed workflow returns its recorded state. These are checks at the application boundary, not authority granted by the model's wording.
4. **Approved rules stay fixed.** [`IterationSpec.digest`](../src/molchat_agent/workflows/iteration.py) binds the plan parameters. [`IterationRunner.run`](../src/molchat_agent/workflows/iteration.py) applies `first` or `all`, energy and physical-status requirements, deadlines, cancellation and failure handling. It takes scores from MolDesign. An absent or unevaluated physical check is not a pass.
5. **Honest delivery.** [`execute` / `complete_video`](../src/molchat_agent/workflows/service.py) retain Preparation's own verdict and rebuild the delivery when Molcy finishes. [`build_deliverable` / `verify_deliverable`](../src/molchat_agent/workflows/deliverable.py) record component hashes and declared omissions. Missing output is not replaced by invented scientific content.
6. **Evidence-backed answers.** `_harness_turn` substitutes deterministic pending/execution summaries where needed and applies the [numeric evidence guard](../src/molchat_agent/conversation/evidence.py). This is a practical safeguard with a finite test suite, not a proof that every possible natural-language claim is grounded.

## One execution you can inspect

The [new capsule campaign](../benchmarks/published/capsule/README.md) resolved aspirin, ketanserin and valbenazine, asked for one approval, and used Vina against 8T69. Aspirin returned −6.867 kcal/mol and did not reach the −10.5 threshold. Ketanserin returned −11.2 with physical checks passed; valbenazine was not docked. Preparation remained `REVIEW` with six requirements under review. Molcy rendered a real MP4. The original ZIP contains all five requested components with no declared missing pieces.

Before approval, the browser recorded zero dispatched host mutations. A deliberately wrong digest received HTTP 409. After completion, repeating the valid approval returned the result and did not dispatch another evaluation. The [execution trace](../benchmarks/published/capsule/execution.json), [ZIP](../benchmarks/published/capsule/delivery.zip), [manifest](../benchmarks/published/capsule/MANIFEST.json) and four screenshots are public evidence.

Hashes verify the published bytes and component consistency. These are client-recorded traces, not a provider-signed attestation of model identity. The model's raw hidden reasoning is neither needed nor published.

## Results and boundaries

The initial 72 live trials retain all four strict failures. Two were an incorrect evaluation expectation for an empty catalogue (`ok` plus zero results); two revealed a real missing time-budget field in the model-facing schema. The corrected follow-up is reported separately, not merged into the initial score. A separate end-to-end observation found that skipped candidates were not emitted to the live UI; source and regression tests now cover that notification. [Findings and corrections](../benchmarks/FINDINGS.md)

The live planning harness used the source checkout; the browser capsule used its pinned MolChat build. Exact revisions and source hashes are recorded in the evidence. The capsule uses real frontend/backend services but emulates several desktop commands, and its served frontend was built before its current source tree. This is not an installer or native Tauri validation.

Vina scores and physical-pose checks are computational observations under the recorded protocol. Neither successful tool use nor a favourable score proves pharmacological activity, predicts a patient's response, or establishes a molecule as a medicine.
