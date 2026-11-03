# MolChat at the Meta hackathon

**▶ [Watch the 3-minute demo](https://www.youtube.com/watch?v=luRIXlqWy6I)**

MolChat is an agent that drives a desktop docking app for you, and shows its work. You describe a hypothesis in one prompt, for example "dock these six molecules against VMAT2 and stop at the first that scores below −10.5 kcal/mol with a valid pose". MolChat looks each molecule up in PubChem and writes the whole plan on a card. You approve it once, and it runs the plan in MolDesign while you watch. At the end, a notebook and a ZIP say what ran, what each number is, where it came from, and what is missing.

## How it uses Meta's models

- **The demo runs on Muse Spark Open** (`meta-models/muse-spark-open-1026`), served by Baseten. MolChat also has an adapter for the Meta Model API, whose default model is `muse-spark-1.3` ([`providers/meta.py`](../../src/molchat_agent/providers/meta.py)).
- **The model turns a request into tool calls.** It decides what to look up (`pubchem_lookup`), fills in the plan (`propose_iteration`), and answers follow-up questions by reading results back from MolDesign.
- **Code checks everything the model fills in.** Arguments must fit closed schemas, and the plan is validated before a card exists. Approval is bound to the plan's SHA-256, and a deterministic loop runs it, so the model can't change the rules halfway.
- **The model doesn't get the last word on numbers.** A number in an answer that no tool returned is hidden, and the answer says so. In the demo, MolChat hid values it couldn't verify instead of guessing.

## What was built during the event, and what wasn't

The rules ask entrants to show only what was built during the hackathon. The line is drawn here.

| Built during the event | Built before |
|---|---|
| **All of this repository**, by the author's declaration. Its history starts at `d37cc70` on 2026-10-26 (UTC−6), and `git log --reverse` lists every change with its time. | **MolDesign**, the platform: docking with AutoDock Vina, Moldex, Molcy (video), Preparation and its package, and the assistant that lived inside it. |
| **MolDesign's side of the integration**, from 2026-10-27: launching and checking MolChat, the host actions, the autopilot frame and cursor, and the minimized-panel bubble. It lives in [moldesign-app](https://github.com/srcacahuate619/moldesign-app), in `frontend/components/ai-host/` and `backend/services/molchat_host/`. | **Code carried over from MolDesign**, declared file by file in [`PROVENANCE.md`](../../PROVENANCE.md), such as the original PubChem lookup. |

What changed during the event: MolChat used to **suggest and wait** for a person at every step. Now **a plan approved once runs by itself**, recovers from each molecule's failures, and declares what it couldn't do. The science, the identity and Preparation's decisions stay with MolDesign; MolChat computes no energy and makes no human decision.

## How to check it yourself

| What | Where |
|---|---|
| The demo, start to finish | [3-minute video](https://www.youtube.com/watch?v=luRIXlqWy6I) |
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
- **A few strings in the demo stay as MolDesign writes them**, such as a warning code (`ESTEREOQUIMICA_NO_DECLARADA`) and the Molcy job state.
