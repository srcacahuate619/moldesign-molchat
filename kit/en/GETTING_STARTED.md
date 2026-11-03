# Run MolDesign with MolChat

This guide is for anyone who wants to use the whole system on their own computer: **MolDesign**, the desktop docking app, with **MolChat**, the agent that drives it. It uses the newest code of both projects. Both change often, so the guide says what it was last checked against, and the [changes section](#changes-to-this-guide) records each update.

| Last checked | |
|---|---|
| Date | 2026-11-03 |
| MolDesign | [`main`](https://github.com/srcacahuate619/moldesign-app) at `ece0208` (version 1.0.4, built from source) |
| MolChat | [`master`](https://github.com/srcacahuate619/moldesign-molchat) at `945c4d7` (v0.1.0), the copy MolDesign pins |
| Machine | Windows 11 x64 with an NVIDIA GTX 1660 SUPER |

If your checkouts are newer than this, the steps still apply unless a newer entry in [Changes to this guide](#changes-to-this-guide) says otherwise. The exact commands that MolDesign's CI runs live in its [CONTRIBUTING.md](https://github.com/srcacahuate619/moldesign-app/blob/main/CONTRIBUTING.md). When this guide and those files disagree, those files are right.

> **Why from source?** The Microsoft Store version of MolDesign (1.0.3, October 22, 2026) was built before MolChat existed, so it doesn't include the agent. Until a release ships with MolChat, you run MolDesign from its repository, as below.

## 1. What you need

- **Windows 10 or 11, x64.** MolDesign's desktop app is Windows only.
- **Git**, **Python 3** to run the setup script, **Node.js** at the version in MolDesign's [`.nvmrc`](https://github.com/srcacahuate619/moldesign-app/blob/main/.nvmrc) (24.20 on the date above), and **Rust** (stable) with the [Tauri prerequisites for Windows](https://tauri.app/start/prerequisites/): the C++ build tools and WebView2.
- **Disk space.** The scientific runtime alone is a 2.2 GB download. The Rust build cache and the Node modules add several more GB.
- **A model.** The demo uses Muse Spark Open (`meta-models/muse-spark-open-1026`) served by Baseten, with your own Baseten key. MolChat's [provider catalogue](../../src/molchat_agent/providers/catalogo.json) lists the alternatives, including the Meta Model API and local servers (llama-server, Ollama) that need no key.
- **Optional: a GPU** that Blender's EEVEE can use, for Molcy videos. Docking, the notebook and the ZIP work without one.

## 2. Get MolDesign and its runtime

```powershell
git clone https://github.com/srcacahuate619/moldesign-app.git
cd moldesign-app
python scripts/bootstrap_dev_tree.py --check
python scripts/bootstrap_dev_tree.py --fetch
```

`--check` lists what a fresh clone is missing and writes nothing. `--fetch` downloads the embedded Python, AutoDock Vina and the other native tools from an archive pinned by revision and SHA-256, and verifies it before extracting.

## 3. Check the MolChat copy inside MolDesign

MolDesign already carries a copy of MolChat in `tools/molchat/`, pinned to one MolChat commit in `backend/data/molchat_fijacion.json`. Verify it:

```powershell
.\python-embed\python.exe scripts\stage_molchat.py --check
```

The output names the commit, for example `master@945c4d7a`. To run a **newer MolChat** than the pinned one, see [Use a newer MolChat](#use-a-newer-molchat).

## 4. Start the app

```powershell
cd frontend
npm ci
npx tauri dev
```

The first start compiles the desktop shell in Rust and takes several minutes; later starts are quick. The app signs you in to a local account by itself, and your data stays on this machine.

## 5. Connect a model

1. Open **OPTIONS** in the top bar, then **Models and engines** → **AI providers**.
2. Pick **Baseten (Muse Spark Hackathon)**, or another provider, and choose **Use this provider**.
3. Paste your API key and press **Save and authorize sending to …**. MolDesign stores the key encrypted for your account. MolChat receives it for each answer and never shows it.

## 6. Open MolChat and allow PubChem

The round MolChat button sits at the bottom right of the window. Click it to open the panel, or drag it to move it. In the panel, open **Settings** and choose **Allow PubChem searches**: MolChat looks every molecule up in PubChem instead of inventing a structure, and this sends the molecule names to `pubchem.ncbi.nlm.nih.gov`.

## 7. Try the demo prompt

This is the request from the [3-minute demo](https://www.youtube.com/watch?v=luRIXlqWy6I). Receptor 8T69 (VMAT2) is in MolDesign's **Verified** catalogue section.

> Create a case called "VMAT2 ligands" on receptor 8T69. Look up caffeine, tetrabenazine, deutetrabenazine, (+)-alpha-dihydrotetrabenazine, ketanserin and valbenazine in PubChem, in that order, and dock them one by one with the default protocol. Stop at the first one that scores -10.5 kcal/mol or better with a physically valid pose. Then make a short preview video of it in Molcy, audit it in Preparation, and give me everything in one ZIP with your notebook.

MolChat answers with a plan card. Read it before you approve: the receptor, the molecules in order, the stopping rule, the time limit and what happens afterwards. One click on **Approve and run** starts the plan. Keep the MolDesign window open: the plan's actions run from it. While it drives MolDesign, a violet frame and a "MolChat" cursor show that the agent, not you, is at the controls. You can minimize the panel: the bubble keeps the plan and each molecule's Vina score.

On the machine above, the plan docked five molecules, stopped at ketanserin (−11.2 kcal/mol, physical checks passed) and never docked valbenazine. These numbers are Vina scores on one receptor, not evidence that a molecule is a better drug.

## 8. Get the results

When the plan ends, the card offers **Download the delivery (ZIP)**. MolChat also writes it to a folder named after the case and the time, under `%USERPROFILE%\MolDesign\MolChat\entregas` (`delivery.zip` for a plan in English, `entrega.zip` for one in Spanish). Set `MOLCHAT_OUTPUT_DIR` before starting the app to use another folder. Inside are:

- the agent's notebook as PDF, Markdown and JSON, with every number's source and run conditions;
- MolDesign's Preparation package, unchanged;
- the Molcy video, if the plan asked for one and the GPU rendered it;
- `MANIFEST.json`, with a SHA-256 hash for every file and a reason for every missing piece.

The video renders in the background. **Download now (without the video)** gives you the ZIP at once, with the video declared missing; download again when the card says the video is in.

## Use a newer MolChat

To run MolChat's latest `master`, or your own fork, stage it into a separate folder and point MolDesign at it. Your checkout's pinned copy stays as it is. Run this from the folder that contains `moldesign-app`.

```powershell
git clone https://github.com/srcacahuate619/moldesign-molchat.git
npm --prefix moldesign-molchat\ui ci
npm --prefix moldesign-molchat\ui run build
cd moldesign-app
.\python-embed\python.exe scripts\stage_molchat.py --fuente ..\moldesign-molchat --write --destino ..\molchat-staged
$env:MOLDESIGN_MOLCHAT_DIR = (Resolve-Path ..\molchat-staged).Path
$env:MOLCHAT_PERMITIR_EXTERNO = "1"
cd frontend
npx tauri dev
```

Only committed code is staged, and the built UI must be newer than its sources. MolDesign then marks the copy as external, not official. To replace the pinned copy instead, run `stage_molchat.py --fuente <clone> --write` without `--destino`, then `--check`. See [Extending MolChat](EXTENDING.md#6-ship-your-version-inside-moldesign).

## When something fails

| What you see | What to do |
|---|---|
| `bootstrap_dev_tree.py --check` reports missing pieces after `--fetch` | Run `--fetch` again. In our own test from a fresh clone, one download broke halfway and worked on retry. |
| "MolChat is not included in this installation" | `tools/molchat/` is missing or fails its check. Run step 3 and read its message. |
| "MolChat could not start" | The copy doesn't match its pin, or its contract is not `moldesign.molchat/1`. Run step 3, or the `--check` in [Use a newer MolChat](#use-a-newer-molchat). |
| The plan card lists molecules as "not found" | PubChem is not allowed (step 6), or the name is ambiguous. Use a more specific name or give the SMILES. |
| "Vina insufficient memory" for one molecule | Close memory-heavy programs. MolChat retries that molecule once and records the outcome in the notebook. |
| No video in the ZIP | Molcy needs a GPU that EEVEE can use, and Blender with Molecular Nodes, which its tab offers to download the first time. The manifest says which piece is missing and why. |

## Changes to this guide

Add an entry whenever a step, a label or a version changes, and update the table at the top.

- **2026-11-03.** First version, checked against MolDesign `ece0208` and MolChat `945c4d7`.

When a Microsoft Store release includes MolChat, replace sections 2 to 4 with "install MolDesign from the Microsoft Store" and keep the source route for anyone who wants the newest code.
