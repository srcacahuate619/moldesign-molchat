# The real delivery from the demo · La entrega real de la demo

This is the ZIP MolChat produced in the run shown in the [3-minute demo](https://www.youtube.com/watch?v=luRIXlqWy6I), byte for byte as it came out. Nothing was redacted or rebuilt.

Es el ZIP que produjo MolChat en la corrida del [vídeo de 3 minutos](https://www.youtube.com/watch?v=luRIXlqWy6I), byte a byte tal como salió. No se tachó ni se rehízo nada.

| File · Archivo | What it is · Qué es |
|---|---|
| [`delivery.zip`](delivery.zip) | The delivery, SHA-256 `277e1a99c9a523e124adc6099e13ad440733b771cb7d6e028c411f9e14483573`. · La entrega. |
| [`notebook.md`](notebook.md) · [`notebook.pdf`](notebook.pdf) | The agent's notebook, copied out of the ZIP so you can read it here. · El cuaderno del agente, copiado del ZIP para leerlo aquí. |
| [`MANIFEST.json`](MANIFEST.json) | Every piece in the ZIP with its SHA-256 and origin. · Cada pieza del ZIP con su SHA-256 y su origen. |

**The run · La corrida.** 2026-11-03, approved at 18:22:38 UTC, finished at 18:28:54 UTC. Receptor 8T69 (VMAT2), six molecules in order, stop at the first with Vina ≤ −10.5 kcal/mol and a pose that passes the physical checks. MolChat docked five and stopped at ketanserin (−11.2 kcal/mol, checks passed); valbenazine was never docked. Inside the ZIP: the notebook as JSON, Markdown and PDF, MolDesign's Preparation package unchanged (verdict REVIEW, 0 blockers, 6 points under review) and Molcy's video. Model: Muse Spark Open (`meta-models/muse-spark-open-1026`) on Baseten.

**What produced it · Qué lo produjo.** MolChat at commit `5b2a3bd`, now part of `master`'s history. MolDesign from source, with the host work published in `moldesign-app` at `ece0208`. A few identifiers appear as MolDesign writes them: the Molcy scene `resultado`, and the readiness code `REVISION`, which is MolDesign's code for the REVIEW verdict spelled out on the same line.

**Check it yourself · Compruébalo.** Each piece must match the hash in `MANIFEST.json`. From the repository root, this prints `True`:

```sh
python -c "import hashlib,json,zipfile; z=zipfile.ZipFile('kit/vmat2-run/delivery.zip'); m=json.loads(z.read('MANIFEST.json')); print(all(hashlib.sha256(z.read(p['path'])).hexdigest()==p['sha256'] for p in m['pieces']))"
```

The CI checks the same thing on every push ([`tests/workflows/test_recorded_delivery.py`](../../tests/workflows/test_recorded_delivery.py)). The Vina energy ranks hypotheses on one receptor; it is not a free energy, a Ki or a measure of activity.
