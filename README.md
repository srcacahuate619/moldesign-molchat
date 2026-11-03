# MolChat Agent

**An agent that drives a computational chemistry app for you, and shows its work.** Describe a hypothesis about a list of molecules in text or by voice, review the plan MolChat proposes, and approve it once. MolChat then runs the plan in [MolDesign](https://github.com/srcacahuate619/moldesign-app) and delivers a lab notebook and a ZIP that record what ran, what was selected, and what is missing.

**▶ [Watch the 3-minute demo](https://www.youtube.com/watch?v=luRIXlqWy6I)** · [English kit](kit/en/HACKATHON.md) · [Kit en español](kit/es/README.md) · [Architecture](docs/ARQUITECTURA.md) · [CI](https://github.com/srcacahuate619/moldesign-molchat/actions/workflows/ci.yml)

## Start here

| If you want to… | Go to |
|---|---|
| See what was built for the Meta hackathon and how it uses Muse Spark | [The hackathon kit](kit/en/HACKATHON.md) |
| Inspect the approved-once workflow without keys or MolDesign | [Run the keyless workflow demo](#run-the-keyless-workflow-demo) |
| Use MolDesign with MolChat on your computer, with real docking | [Getting started](kit/en/GETTING_STARTED.md) |
| Add a tool to MolChat or adapt it to another platform | [Extending MolChat](kit/en/EXTENDING.md) |
| Open the standalone chat UI | [Build and open the UI](#build-and-open-the-ui) |

## What we built for the Meta hackathon

**Muse Spark turns a request into structured tool calls.** In the demo, Muse Spark Open (served by Baseten) looks each molecule up in PubChem and fills in the plan. MolChat validates every argument, shows the molecules, the stopping rule and the follow-up actions on a card, and binds the approval to the plan's SHA-256 digest.

**MolChat runs the approved plan.** It evaluates up to 12 molecules in one case, one at a time, and stops when the rule is met; a typical rule combines a Vina score threshold with passing physical pose checks. It records failed attempts and the candidates it skipped. Depending on the plan, it asks MolDesign to save the selected run to Moldex, render a video in Molcy, and audit it in Preparation. The ZIP's manifest records a SHA-256 hash for every file, the provenance of each number, and every missing piece. A docking score is exploratory evidence; it doesn't establish biological activity. [Workflow and file formats](docs/ITERACION_DE_MOLECULAS.md)

**Project boundary.** This whole repository was written during the event, and so was MolDesign's side of the integration (launching MolChat, the host actions, the autopilot view). MolDesign itself, with docking, Moldex, Molcy and Preparation, predates the event, as does the code carried over from it, which [`PROVENANCE.md`](PROVENANCE.md) declares file by file. [The full line, with dates](kit/en/HACKATHON.md#what-was-built-during-the-event-and-what-wasnt)

## Run the keyless workflow demo

Use **Python 3.11 or 3.12**, the versions covered by the CI matrix. Run these commands from a fresh clone.

```sh
git clone https://github.com/srcacahuate619/moldesign-molchat.git
cd moldesign-molchat
python -m venv .venv
```

If your launcher is named differently, use `python3.12 -m venv .venv` on macOS/Linux or `py -3.12 -m venv .venv` on Windows. Activate with `source .venv/bin/activate` on macOS/Linux or `.\.venv\Scripts\Activate.ps1` in PowerShell. If activation is restricted, use `.\.venv\Scripts\python.exe` in place of `python` in the following commands.

```sh
python -m pip install -e ".[dev]"
python -c "from pathlib import Path; Path('reports').mkdir(exist_ok=True)"
python -m pytest -q --basetemp=reports/judge-demo tests/server/test_workflow_chat.py
```

The tests drive the hosted chat API with a scripted model response and a simulated MolDesign host. They check that a wrong digest is rejected, that a valid approval runs the workflow only once, that a failed molecule is recorded, and that the run stops before the third candidate. Look under `reports/judge-demo/` for `salida/**/entrega.zip` (this scenario runs in Spanish, so the names are Spanish). Open `cuaderno/cuaderno.md` for the plan and each candidate's outcome, and `MANIFEST.json` for the hashes and the reason the Preparation package is absent. The numbers are synthetic, and a placeholder MP4 exercises the packaging. [Demo source](tests/server/test_workflow_chat.py)

Pytest recreates `reports/judge-demo` on each run. The full local suite is `python -m pytest -q`. The HTTP adapter contract can also be exercised against a local synthetic backend: [Extending MolChat](kit/en/EXTENDING.md#4-build-your-own-lock).

## Build and open the UI

Use **Node.js 22.12 or later** and run from the repository root in the same virtual environment. If you only want the standalone UI, install `.[server]` in place of `.[dev]`.

```sh
npm --prefix ui ci
npm --prefix ui run build
```

On macOS/Linux:

```sh
MOLCHAT_PROVIDER=fake python -m molchat_agent serve --ui-dist ui/dist
```

In PowerShell:

```powershell
$env:MOLCHAT_PROVIDER = 'fake'
python -m molchat_agent serve --ui-dist ui/dist
```

Open <http://127.0.0.1:8771>, paste the session printed in your terminal, and try the goal **List receptors** in the Plans tab. The keyless provider generates a fixed read-only plan, so you can review it and explore the interface. Scientific runs need MolDesign: see [Getting started](kit/en/GETTING_STARTED.md). Use `npm.cmd` if PowerShell blocks the npm script. [Sidecar and API](docs/SIDECAR.md)

## Build and verify the distribution

```sh
python -m pip install build
python -m build
```

The wheel contains the Python agent; build the UI separately as shown above. To produce the bundle MolDesign stages, build the UI from a clean Git checkout and run:

```sh
python scripts/make_manifest.py --write
python scripts/make_manifest.py --check dist/molchat-vendorizable
```

[Release and compatibility guide](docs/RELEASES.md) · [Security](docs/SEGURIDAD.md) · [License](LICENSE) · [Citation](CITATION.cff)
