# Agent notebook — benchmark-vmat2-20261103

- Receptor: 8T69
- Approved: 2026-11-04T04:00:20+00:00
- Finished: 2026-11-04T04:04:22+00:00
- Plan digest: `sha256:3311033a4ea32b262214035136eb7f6e0eba401606a6199c0d8deb9fe7cd180a`

## What was asked

Prepare an approved-once iteration in a NEW case called benchmark-vmat2-20261103. Resolve aspirin, ketanserin and valbenazine through PubChem in exactly that order. Receptor VMAT2, PDB 8T69. Stop at the FIRST candidate with Vina energy <= -10.5 kcal/mol AND passed physical pose checks. Save the selected run in Moldex, make a short preview search video, audit it in Preparation, and deliver the notebook, original Preparation package and video in a single ZIP. First show the approval card and wait; do not start docking yet.

## What was approved

- Case “benchmark-vmat2-20261103” · receptor 8T69
- 3 molecules, one after another in this same case: aspirin, ketanserin, valbenazine
- Stops at the first one that meets it: Vina ≤ -10.5 kcal/mol and the best pose passes the physical checks
- If a molecule fails, it is noted and the next one goes on.
- The one that meets it is saved to Moldex.
- Molcy video (GPU only): scene Search, format test (short preview); MolDesign's closing is always added.
- Presentation: Molcy's automatic one.
- The run is audited in Preparation; if it needs review, that is declared, not decided.
- At the end everything goes into a single ZIP.
- Limit: 7 min per molecule and 40 min in total.

## What happened

Finished: one molecule meets the rule.

| # | Molecule | Status | Vina (kcal/mol) | Physical checks | Reading |
|---|---|---|---|---|---|
| 1 | aspirin | docked | -6.867 | passed | does not reach the threshold |
| 2 | ketanserin | docked | -11.2 | passed | meets the rule |
| 3 | valbenazine | not docked | — | — | The stop rule was already met. |

- Molecule 3 (valbenazine): The stop rule was already met.

### Measured times

Case wait: until the window said the previous run had closed. Result: from the start of the run until the backend declared it finished with its energy.

- Molecule 1 (aspirin): case wait 0.1 s (“idle”), start 7.5 s, result 42.3 s, total 49.9 s.
- Molecule 2 (ketanserin): case wait 5.1 s (“idle”), start 2.8 s, result 27.2 s, total 35.1 s.

## Run conditions

Across the 2 docked runs:
- The same in all: prepared receptor 8fc027cae876631f30518b27823ce175e844bbe9e7bc10554653a7766e21468d; Vina version 1.2.7; engine vina; exhaustiveness 8; poses 9; seed 42; box center [127.862, 123.474, 104.225]; box size [30.0, 30.0, 30.0].

## Record per molecule

What MolDesign recorded about each run and where each SMILES came from, as is; nothing is interpreted here.

### 1. aspirin

- SMILES in the plan: `CC(=O)OC1=CC=CC=C1C(=O)O`
- Source: PubChem CID 2244 (“Aspirin”, search “aspirin”); the SMILES matches PubChem's. https://pubchem.ncbi.nlm.nih.gov/compound/2244
- Input SMILES (canonical): CC(=O)Oc1ccccc1C(=O)O; docked species (from the 3D): CC(=O)Oc1ccccc1C(=O)[O-].
- Protonation: at pH 7.4, 1 alternative.
- Tautomer: the input one.
- Unassigned stereochemistry in the input: 0 centers and 0 double bonds.
- Protocol run: vina 1.2.7, exhaustiveness 8, poses 9, seed 42, box center [127.862, 123.474, 104.225] size [30.0, 30.0, 30.0] Å.
- Run warnings (4):
  - [caution] Meeko-assigned histidine templates: A:353=HIE, A:414=HIE. The assignment is template-based and does not validate the experimental microstate or a specific pH. (RECEPTOR_PROTONACION_DECLARADA)
  - [info] Desolvated preparation: the deposited structure had no crystallographic waters inside the docking box, so none were removed from the site during preparation. (SITIO_DESOLVATADO)
  - [legacy] Ligand efficiency LE=0.53. With 13 heavy atoms, the 0.45 threshold is crossed by any affinity better than -5.9 kcal/mol, so exceeding it does not distinguish good binding from mediocre binding. In this mass range (< 300 Da, Rule of Three), efficiency per atom is high by construction: it can compare molecules of the same size, but cannot serve as a verdict.
  - [caution] The docked species differs from the input: CC(=O)Oc1ccccc1C(=O)O → CC(=O)Oc1ccccc1C(=O)[O-]. Unevaluated alternatives remain a source of chemical uncertainty. (ESPECIE_ACOPLADA_DISTINTA)
- Task: ef2b29c1-e734-4cf9-ad72-c6ec54fc2f63

### 2. ketanserin

- SMILES in the plan: `C1CN(CCC1C(=O)C2=CC=C(C=C2)F)CCN3C(=O)C4=CC=CC=C4NC3=O`
- Source: PubChem CID 3822 (“Ketanserin”, search “ketanserin”); the SMILES matches PubChem's. https://pubchem.ncbi.nlm.nih.gov/compound/3822
- Input SMILES (canonical): O=C(c1ccc(F)cc1)C1CCN(CCn2c(=O)[nH]c3ccccc3c2=O)CC1; docked species (from the 3D): O=c1[nH]c2ccccc2c(=O)n1CC[N@H+]1CC[C@@H](C(=O)c2ccc(F)cc2)CC1.
- Protonation: at pH 7.4, 4 alternatives.
- Tautomer: the input one.
- Unassigned stereochemistry in the input: 0 centers and 0 double bonds.
- Protocol run: vina 1.2.7, exhaustiveness 8, poses 9, seed 42, box center [127.862, 123.474, 104.225] size [30.0, 30.0, 30.0] Å.
- Run warnings (4):
  - [caution] Meeko-assigned histidine templates: A:353=HIE, A:414=HIE. The assignment is template-based and does not validate the experimental microstate or a specific pH. (RECEPTOR_PROTONACION_DECLARADA)
  - [info] Desolvated preparation: the deposited structure had no crystallographic waters inside the docking box, so none were removed from the site during preparation. (SITIO_DESOLVATADO)
  - [legacy] ⚠️ Molecule with 29 heavy atoms and 5 rotatable bonds — docking may take longer than usual. To reduce run time, review the box and Vina exhaustiveness; a smaller search may change the poses.
  - [caution] The docked species differs from the input: O=C(c1ccc(F)cc1)C1CCN(CCn2c(=O)[nH]c3ccccc3c2=O)CC1 → O=C(c1ccc(F)cc1)C1CC[NH+](CCn2c(=O)[nH]c3ccccc3c2=O)CC1. Unevaluated alternatives remain a source of chemical uncertainty. (ESPECIE_ACOPLADA_DISTINTA)
- Task: 7967d611-9b2c-41e3-81ef-62c872aa0bec

### 3. valbenazine

- SMILES in the plan: `CC(C)C[C@@H]1CN2CCC3=CC(=C(C=C3[C@H]2C[C@H]1OC(=O)[C@H](C(C)C)N)OC)OC`
- Source: PubChem CID 24795069 (“Valbenazine”, search “valbenazine”); the SMILES matches PubChem's. https://pubchem.ncbi.nlm.nih.gov/compound/24795069

## What was done with the chosen one

ketanserin (task 7967d611-9b2c-41e3-81ef-62c872aa0bec): Vina -11.2 kcal/mol, physical checks passed.
- Moldex: saved · message: Run saved to Moldex.
- Molcy video: started · message: Video queued in Molcy (started from its tab). · job_id: 96ee39c3-4526-4049-a3a5-7f3cb262b558 · file: molcy_96ee39c3.mp4
- Preparation: exported · message: Preparation: REVIEW. 0 blockers and 6 requirements under review; MolChat did not decide them. · readiness: REVISION
- Delivery: building · message: This notebook is part of the delivery.

## Limits and provenance

The Vina energy is that of Vina's best pose: it is not a free energy, nor a Ki, nor a measure of activity. An iteration over a few molecules does not rank drugs. The physical checks are PoseBusters' as MolDesign declares them.

The energies, the physical checks, the protocol, the warnings and the docked species came from MolDesign; each molecule's identity, from the PubChem lookup of this conversation whose SMILES matches literally. MolChat ordered the calls, recorded what happened and wrote this notebook without the model.
