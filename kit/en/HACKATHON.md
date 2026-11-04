# MolChat at the Meta hackathon

**▶ [Watch the 3-minute demo](https://www.youtube.com/watch?v=luRIXlqWy6I)**

**[Reliability evidence: 36 live prompts, graphs, traces and a new complete campaign](../../benchmarks/README.md)** · [Real provider invocation and harness boundaries](../../docs/META_EXECUTION.md). Initial failures and targeted corrections are reported separately.

[Submission copy and final evidence links](SUBMISSION.md)

Computational chemistry researchers can hand off a short docking campaign from one prompt. Muse Spark Open resolves compound names through PubChem and prepares a plan with the target, candidate order, stopping rule, and requested outputs. A researcher approves it once. MolChat drives the desktop app and returns the evidence needed to review or hand off the result.

## The recorded run

The request named six molecules and asked for the first candidate against VMAT2 (PDB 8T69) to score **−10.5 kcal/mol or lower** with passing physical pose checks. After one approval, MolChat ran five candidates and stopped at ketanserin (**−11.2 kcal/mol**, pose checks passed). It left valbenazine unevaluated and recorded that decision. The plan took about six minutes from approval to its end; the video rendered afterwards and joined the ZIP. This is one recorded Vina run under the demo conditions. [Exact prompt and setup](GETTING_STARTED.md#7-try-the-demo-prompt) · [The real ZIP it produced](../vmat2-run/)

In the video, look for the approval card, the visible desktop actions, the stopping decision, and the notebook. The agent's work is the coordination and evidence trail across those steps. The docking engine and the molecular renderer are existing MolDesign components. [Watch the recording](https://www.youtube.com/watch?v=luRIXlqWy6I)

## Review by criterion

| Criterion | Evidence to inspect |
|---|---|
| **Impact · 30%** | A researcher sets the rule once and receives a record of candidates attempted, skipped, and selected. The recorded run avoided launching the sixth candidate once the stated rule was met. [Demo case](GETTING_STARTED.md#7-try-the-demo-prompt) |
| **Use of Meta AI tooling · 25%** | Muse Spark Open selects the lookup tools and turns the request into a structured plan. The accepted plan becomes a real sequence of desktop actions. [Model and tools](#how-it-uses-metas-models) |
| **Demo · 25%** | Watch the real run, then reproduce the approval and stopping behavior without a key using the synthetic host fixture. [Recording](https://www.youtube.com/watch?v=luRIXlqWy6I) · [The run's real ZIP](../vmat2-run/) · [Keyless reproduction](../../README.md#run-the-keyless-workflow-demo) |
| **Technical depth and execution · 20%** | The test rejects a mismatched approval digest, runs only once after approval, recovers from a failed candidate, and checks the exported ZIP. [Integration test](../../tests/server/test_workflow_chat.py) · [Host contract](../../docs/HOST_CONTRACT.md) |

The case fits **Build for Your World**, Meta's theme for applying its models to a workflow in a specific domain. The weights above come from the participant guide. [Meta event overview](https://dev.meta.ai/events/global-hackathon) · [Cerebral Valley event page](https://cerebralvalley.ai/e/meta-ai-developer-hackathon)

## How it uses Meta's models

- **The demo runs on Muse Spark Open** (`meta-models/muse-spark-open-1026`), served by Baseten. This is the open-weight model used for the recorded workflow. The provider catalog lists the separate Meta Model API option. [Provider catalog](../../src/molchat_agent/providers/catalogo.json) · [Baseten model announcement](https://www.baseten.co/blog/muse-spark-open-launch/)
- **The model turns a request into tool calls.** It decides what to look up (`pubchem_lookup`), fills in the plan (`propose_iteration`), and answers follow-up questions using results from MolDesign. [Lookup tool](../../src/molchat_agent/conversation/harness_tools.py) · [Plan tool](../../src/molchat_agent/workflows/tool.py)
- **Code checks everything the model fills in.** Arguments must fit closed schemas, and the plan is validated before a card exists. Approval is bound to the plan's SHA-256, and a deterministic loop runs it, so the model can't change the rules halfway.
- **The model doesn't get the last word on numbers.** A number in an answer that no tool returned is hidden, and the answer says so. In the demo, MolChat hid values it couldn't verify instead of guessing.

## What was built during the event, and what wasn't

The rules ask entrants to show only what was built during the hackathon. The line is drawn here.

| Built during the event | Built before |
|---|---|
| **Muse Spark Open provider entry** on Oct 28. [Provider commit](https://github.com/srcacahuate619/moldesign-molchat/commit/74b8d96b3e389c44519dfb5441ca8249baef5808) | **MolDesign's scientific platform**, including AutoDock Vina, Moldex, Molcy, Preparation, and the original in-app assistant. |
| **Approved-once iteration and host actions** on Nov 2. [Workflow commit](https://github.com/srcacahuate619/moldesign-molchat/commit/2a0ca42a9f0f01013a4e8465cb11c9ef00e129ca) | **Reused implementation**, including the original PubChem lookup. [Provenance ledger](../../PROVENANCE.md) |
| **Per-run evidence and visible agent execution** on Nov 3. [Run record commit](https://github.com/srcacahuate619/moldesign-molchat/commit/42fa3deb3e64f447ea29675ace2aa04ca21f0ea4) · [Agent progress commit](https://github.com/srcacahuate619/moldesign-molchat/commit/0c4d0a5d1edd9c0f8b97ab834893008177644538) | **Existing engines and research data** supply the scientific inputs and outputs. |

The repository history starts on Oct 26, the kickoff date. The table anchors the showcased work to later feature commits. MolDesign's side of the integration, which launches the agent, applies its host actions and shows its progress in the desktop app, was also written during the event: it was first added on Oct 27 and has been public in moldesign-app since Oct 31. [Repository history](https://github.com/srcacahuate619/moldesign-molchat/commits/master/) · [MolDesign integration](https://github.com/srcacahuate619/moldesign-app/tree/ece0208/frontend/components/ai-host)

What changed during the event: MolChat used to **suggest and wait** for a person at every step. Now **a plan approved once runs by itself**, recovers from each molecule's failures, and declares what it couldn't do. The science, the identity and Preparation's decisions stay with MolDesign; MolChat computes no energy and makes no human decision.

## How to check it yourself

| What | Where |
|---|---|
| The demo, start to finish | [3-minute video](https://www.youtube.com/watch?v=luRIXlqWy6I) |
| What the recorded run delivered, byte for byte | [`kit/vmat2-run/`](../vmat2-run/) |
| The approved-once loop, without keys or MolDesign | [Keyless workflow demo](../../README.md#run-the-keyless-workflow-demo) |
| The real thing on your computer | [Getting started](GETTING_STARTED.md) |
| How to add a tool or adapt MolChat to another platform | [Extending MolChat](EXTENDING.md) |
| Who wrote what, file by file | [`PROVENANCE.md`](../../PROVENANCE.md) |
| Tests on every push | [CI](https://github.com/srcacahuate619/moldesign-molchat/actions/workflows/ci.yml) |

## Limits we know about

- **Windows only, from source.** MolDesign's Microsoft Store version predates MolChat. To use both today, you build MolDesign from its repository ([Getting started](GETTING_STARTED.md)).
- **Not tested from a clean machine's installer.** The demo ran on the developer's computer, from source; MolDesign's CI and a clean clone pass, but no installer with MolChat has been built yet.
- **A docking score is not a drug.** Vina's energy ranks hypotheses on one receptor; it doesn't establish activity. Receptor 8T69, used in the demo, is the only receptor in MolDesign's catalogue whose Vina ranking passed a pre-registered check against published Ki values. Even there, it ranks a series better than chance; it doesn't predict one molecule's Ki.
- **Hidden numbers.** When MolChat can't tie a number to a tool result, it hides it. That keeps answers honest, but some answers come out with gaps.
- **A few strings in the demo stay as MolDesign writes them**, such as a warning code (`ESTEREOQUIMICA_NO_DECLARADA`), the Molcy job state, and the scene name `resultado` in the run's notebook.
