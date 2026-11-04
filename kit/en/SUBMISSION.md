# MolChat — submission copy and evidence

These texts are ready to adapt to the hackathon form. The live form's exact fields and character limits have not been inspected, and no form has been submitted.

## Project name

MolChat

## One-line description

From a molecular hypothesis to an auditable notebook with one approval.

## Short description

MolChat helps computational chemistry researchers coordinate a small docking campaign in MolDesign. Muse Spark Open resolves molecular identities and proposes a structured plan. The researcher reviews the candidates, receptor, stopping rule, time limits and outputs, then approves once. A deterministic harness executes the approved workflow, records failures and skipped candidates, and delivers a source-backed notebook, Preparation audit package and optional Molcy video in a verifiable ZIP.

## Project description

Running a small molecular hypothesis involves more than launching docking: researchers must resolve identities, preserve the candidate order, check when to stop, distinguish failures from results, and assemble evidence for someone else to inspect.

We built MolChat's agent workflow and MolDesign host integration around that handoff. Muse Spark Open, served by Baseten as `meta-models/muse-spark-open-1026`, selects structured tools such as `pubchem_lookup` and `propose_iteration`. Code validates its arguments and presents one approval card. Approval is tied to the plan's SHA-256 digest; a deterministic executor then coordinates MolDesign's existing scientific tools.

In the recorded six-candidate VMAT2 demo, the workflow stopped after the fifth candidate, ketanserin, met the approved Vina threshold and physical pose checks. Two subsequent browser campaigns independently reproduced the handoff with a shorter three-candidate list: aspirin was evaluated, ketanserin qualified, and valbenazine was skipped. Both delivered a real audit package and rendered video.

We publish 36 fixed live prompts with two initial trials each, every outcome and trace, separate follow-up corrections, a keyless regression benchmark, and original delivery ZIPs. The initial strict score was 68/72; two failures exposed an incorrect evaluator expectation and two exposed a missing model-facing time-budget field. Later verification also found an unwanted case creation before approval; that failed attempt and its correction are retained.

The contribution is agent coordination, approval enforcement and scientific provenance. MolDesign's Vina docking engine, molecular renderer, Moldex and Preparation existed already. Successful coordination does not establish biological activity, and Preparation's unresolved `REVIEW` verdict is preserved.

## Meta model usage

Muse Spark Open chooses tool calls and fills the proposed plan. MolChat returns actual tool results to the model, validates closed argument schemas, and controls side effects. The harness reads docking results from MolDesign and starts a proposed workflow through the approval endpoint. Model identifiers, requested calls, validated arguments, results and timings are published in the evaluation traces; credentials and hidden reasoning are excluded.

## Evidence links

| Field or reviewer question | Public link |
|---|---|
| Repository | [moldesign-molchat](https://github.com/srcacahuate619/moldesign-molchat) |
| Frozen submission snapshot | [meta-hackathon-2026-submission](https://github.com/srcacahuate619/moldesign-molchat/tree/meta-hackathon-2026-submission) |
| Demo | [Three-minute recording](https://www.youtube.com/watch?v=luRIXlqWy6I) |
| Evaluation | [Results and graphs](../../benchmarks/RESULTS.md) |
| Actual Meta provider invocation | [META_EXECUTION.md](../../docs/META_EXECUTION.md) |
| Final integration verification | [Release check](../../benchmarks/published/release-check/README.md) |
| Built during the event and reused components | [Contribution guide](HACKATHON.md#what-was-built-during-the-event-and-what-wasnt) |
| Known limitations and corrections | [Findings](../../benchmarks/FINDINGS.md) |

## Submission handoff

Use the frozen snapshot and links above in the form. Preserve the distinction between scripted regression checks, live model trials and real docking campaigns. The browser capsule emulates some desktop commands; native Tauri, WebView2 and a clean-machine installer remain unvalidated. No claim of drug efficacy or general model reliability is made from these fixed examples.
