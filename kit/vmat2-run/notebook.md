# Agent notebook — VMAT2 ligands

- Receptor: 8T69
- Approved: 2026-11-03T18:22:38+00:00
- Finished: 2026-11-03T18:28:54+00:00
- Plan digest: `sha256:224e304cf61bb8341202e88b03cfbdcf674f648389c4dfc436b736292f05f207`

## What was asked

Create a case called "VMAT2 ligands" on receptor 8T69. Look up caffeine, tetrabenazine, deutetrabenazine, (+)-alpha-dihydrotetrabenazine, ketanserin and valbenazine in PubChem, in that order, and dock them one by one with the default protocol. Stop at the first one that scores -10.5 kcal/mol or better with a physically valid pose. Then make a short preview video of it in Molcy, audit it in Preparation, and give me everything in one ZIP with your notebook.

## What was approved

- Case “VMAT2 ligands” · receptor 8T69
- 6 molecules, one after another in this same case: caffeine, tetrabenazine, deutetrabenazine, (+)-alpha-dihydrotetrabenazine, ketanserin, valbenazine
- Stops at the first one that meets it: Vina ≤ -10.5 kcal/mol and the best pose passes the physical checks
- If a molecule fails, it is noted and the next one goes on.
- The one that meets it is saved to Moldex.
- Molcy video (GPU only): scene resultado, format test (short preview); MolDesign's closing is always added.
- Presentation: Molcy's automatic one.
- The run is audited in Preparation; if it needs review, that is declared, not decided.
- At the end everything goes into a single ZIP.
- Limit: 7 min per molecule and 40 min in total.

## What happened

Finished: one molecule meets the rule.

| # | Molecule | Status | Vina (kcal/mol) | Physical checks | Reading |
|---|---|---|---|---|---|
| 1 | caffeine | docked | -6.226 | passed | does not reach the threshold |
| 2 | tetrabenazine | docked | -9.566 | passed | does not reach the threshold |
| 3 | deutetrabenazine | docked | -9.587 | passed | does not reach the threshold |
| 4 | (+)-alpha-dihydrotetrabenazine | docked | -10.26 | passed | does not reach the threshold |
| 5 | ketanserin | docked | -11.2 | passed | meets the rule |
| 6 | valbenazine | not docked | — | — | The stop rule was already met. |

- Molecule 6 (valbenazine): The stop rule was already met.

### Measured times

Case wait: until the window said the previous run had closed. Result: from the start of the run until the backend declared it finished with its energy.

- Molecule 1 (caffeine): case wait 0.2 s (“idle”), start 10.9 s, result 65.5 s, total 76.6 s.
- Molecule 2 (tetrabenazine): case wait 0.1 s (“idle”), start 2.8 s, result 24.2 s, total 27.2 s.
- Molecule 3 (deutetrabenazine): case wait 5.1 s (“idle”), start 2.9 s, result 24.2 s, total 32.3 s.
- Molecule 4 ((+)-alpha-dihydrotetrabenazine): case wait 0 s (“idle”), start 3 s, result 30.6 s, total 33.6 s.
- Molecule 5 (ketanserin): case wait 0.1 s (“idle”), start 2.9 s, result 54.8 s, total 57.8 s.

## Run conditions

Across the 5 docked runs:
- The same in all: prepared receptor 8fc027cae876631f30518b27823ce175e844bbe9e7bc10554653a7766e21468d; Vina version 1.2.7; engine vina; exhaustiveness 8; poses 9; seed 42; box center [127.862, 123.474, 104.225]; box size [30.0, 30.0, 30.0].

## Record per molecule

What MolDesign recorded about each run and where each SMILES came from, as is; nothing is interpreted here.

### 1. caffeine

- SMILES in the plan: `CN1C=NC2=C1C(=O)N(C(=O)N2C)C`
- Source: PubChem CID 2519 (“Caffeine”, search “caffeine”); the SMILES matches PubChem's. https://pubchem.ncbi.nlm.nih.gov/compound/2519
- Input SMILES (canonical): Cn1c(=O)c2c(ncn2C)n(C)c1=O; docked species (from the 3D): Cn1c(=O)c2c(ncn2C)n(C)c1=O (the same).
- Protonation: at pH 7.4, 1 alternative.
- Tautomer: the input one.
- Unassigned stereochemistry in the input: 0 centers and 0 double bonds.
- Protocol run: vina 1.2.7, exhaustiveness 8, poses 9, seed 42, box center [127.862, 123.474, 104.225] size [30.0, 30.0, 30.0] Å.
- Run warnings (3):
  - [caution] Meeko-assigned histidine templates: A:353=HIE, A:414=HIE. The assignment is template-based and does not validate the experimental microstate or a specific pH. (RECEPTOR_PROTONACION_DECLARADA)
  - [info] Desolvated preparation: the deposited structure had no crystallographic waters inside the docking box, so none were removed from the site during preparation. (SITIO_DESOLVATADO)
  - [caution] The pKa table recognised no ionisable centres. The microstate was chosen by canonical SMILES order for reproducibility; that order does not estimate its population at physiological pH. (MICROESTADO_SIN_CRITERIO_QUIMICO)
- Task: 9948ea47-20c7-4bc0-9d76-b6d526e94d81

### 2. tetrabenazine

- SMILES in the plan: `CC(C)CC1CN2CCC3=CC(=C(C=C3C2CC1=O)OC)OC`
- Source: ambiguous; the SMILES matches several PubChem compounds (CID 6018, 73442840).
- Input SMILES (canonical): COc1cc2c(cc1OC)C1CC(=O)C(CC(C)C)CN1CC2; docked species (from the 3D): COc1cc2c(cc1OC)[C@@H]1CC(=O)[C@H](CC(C)C)C[N@@H+]1CC2.
- Protonation: at pH 7.4, 2 alternatives.
- Tautomer: the input one.
- Unassigned stereochemistry in the input: 2 centers and 0 double bonds.
- Protocol run: vina 1.2.7, exhaustiveness 8, poses 9, seed 42, box center [127.862, 123.474, 104.225] size [30.0, 30.0, 30.0] Å.
- Run warnings (4):
  - [caution] Meeko-assigned histidine templates: A:353=HIE, A:414=HIE. The assignment is template-based and does not validate the experimental microstate or a specific pH. (RECEPTOR_PROTONACION_DECLARADA)
  - [info] Desolvated preparation: the deposited structure had no crystallographic waters inside the docking box, so none were removed from the site during preparation. (SITIO_DESOLVATADO)
  - [caution] The docked species differs from the input: COc1cc2c(cc1OC)C1CC(=O)C(CC(C)C)CN1CC2 → COc1cc2c(cc1OC)C1CC(=O)C(CC(C)C)C[NH+]1CC2. Unevaluated alternatives remain a source of chemical uncertainty. (ESPECIE_ACOPLADA_DISTINTA)
  - [critical] The input left 2 chiral center(s) and 0 E/Z double bond(s) unspecified. Isomer derived from the 3D conformer: COc1cc2c(cc1OC)[C@@H]1CC(=O)[C@H](CC(C)C)C[N@@H+]1CC2. The other stereoisomers were not evaluated. (ESTEREOQUIMICA_NO_DECLARADA)
- Task: ec21b228-88d2-4680-bd07-a52826b6a31f

### 3. deutetrabenazine

- SMILES in the plan: `[2H]C([2H])([2H])OC1=C(C=C2[C@@H]3CC(=O)[C@H](CN3CCC2=C1)CC(C)C)OC([2H])([2H])[2H]`
- Source: PubChem CID 73442840 (“Deutetrabenazine”, search “deutetrabenazine”); the SMILES matches PubChem's. https://pubchem.ncbi.nlm.nih.gov/compound/73442840
- Input SMILES (canonical): [2H]C([2H])([2H])Oc1cc2c(cc1OC([2H])([2H])[2H])[C@@H]1CC(=O)[C@@H](CC(C)C)CN1CC2; docked species (from the 3D): [2H]C([2H])([2H])Oc1cc2c(cc1OC([2H])([2H])[2H])[C@@H]1CC(=O)[C@@H](CC(C)C)C[N@@H+]1CC2.
- Protonation: at pH 7.4, 2 alternatives.
- Tautomer: the input one.
- Unassigned stereochemistry in the input: 0 centers and 0 double bonds.
- Protocol run: vina 1.2.7, exhaustiveness 8, poses 9, seed 42, box center [127.862, 123.474, 104.225] size [30.0, 30.0, 30.0] Å.
- Run warnings (4):
  - [caution] Meeko-assigned histidine templates: A:353=HIE, A:414=HIE. The assignment is template-based and does not validate the experimental microstate or a specific pH. (RECEPTOR_PROTONACION_DECLARADA)
  - [info] Desolvated preparation: the deposited structure had no crystallographic waters inside the docking box, so none were removed from the site during preparation. (SITIO_DESOLVATADO)
  - [legacy] High variance between poses (3.0 kcal/mol). The binding mode is not unique — the prediction is less reliable.
  - [caution] The docked species differs from the input: [2H]C([2H])([2H])Oc1cc2c(cc1OC([2H])([2H])[2H])[C@@H]1CC(=O)[C@@H](CC(C)C)CN1CC2 → [2H]C([2H])([2H])Oc1cc2c(cc1OC([2H])([2H])[2H])[C@@H]1CC(=O)[C@@H](CC(C)C)C[NH+]1CC2. Unevaluated alternatives remain a source of chemical uncertainty. (ESPECIE_ACOPLADA_DISTINTA)
- Task: 83fe638d-1312-4aca-95ca-614ff7312d78

### 4. (+)-alpha-dihydrotetrabenazine

- SMILES in the plan: `CC(C)C[C@@H]1CN2CCC3=CC(=C(C=C3[C@H]2C[C@H]1O)OC)OC`
- Source: PubChem CID 14580381 (“alpha-Dihydrotetrabenazine”, search “(+)-alpha-dihydrotetrabenazine”); the SMILES matches PubChem's. https://pubchem.ncbi.nlm.nih.gov/compound/14580381
- Input SMILES (canonical): COc1cc2c(cc1OC)[C@H]1C[C@@H](O)[C@H](CC(C)C)CN1CC2; docked species (from the 3D): COc1cc2c(cc1OC)[C@H]1C[C@@H](O)[C@H](CC(C)C)C[N@H+]1CC2.
- Protonation: at pH 7.4, 2 alternatives.
- Tautomer: the input one.
- Unassigned stereochemistry in the input: 0 centers and 0 double bonds.
- Protocol run: vina 1.2.7, exhaustiveness 8, poses 9, seed 42, box center [127.862, 123.474, 104.225] size [30.0, 30.0, 30.0] Å.
- Run warnings (3):
  - [caution] Meeko-assigned histidine templates: A:353=HIE, A:414=HIE. The assignment is template-based and does not validate the experimental microstate or a specific pH. (RECEPTOR_PROTONACION_DECLARADA)
  - [info] Desolvated preparation: the deposited structure had no crystallographic waters inside the docking box, so none were removed from the site during preparation. (SITIO_DESOLVATADO)
  - [caution] The docked species differs from the input: COc1cc2c(cc1OC)[C@H]1C[C@@H](O)[C@H](CC(C)C)CN1CC2 → COc1cc2c(cc1OC)[C@H]1C[C@@H](O)[C@H](CC(C)C)C[NH+]1CC2. Unevaluated alternatives remain a source of chemical uncertainty. (ESPECIE_ACOPLADA_DISTINTA)
- Task: 3b55b91b-4aa4-490a-8172-04c8dfe8bacb

### 5. ketanserin

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
- Task: 4bde1023-1e6c-4bf9-932b-16761ea4b47c

### 6. valbenazine

- SMILES in the plan: `CC(C)C[C@@H]1CN2CCC3=CC(=C(C=C3[C@H]2C[C@H]1OC(=O)[C@H](C(C)C)N)OC)OC`
- Source: PubChem CID 24795069 (“Valbenazine”, search “valbenazine”); the SMILES matches PubChem's. https://pubchem.ncbi.nlm.nih.gov/compound/24795069

## What was done with the chosen one

ketanserin (task 4bde1023-1e6c-4bf9-932b-16761ea4b47c): Vina -11.2 kcal/mol, physical checks passed.
- Moldex: saved · message: Run saved to Moldex.
- Molcy video: started · message: Video queued in Molcy (started from its tab). · job_id: 07bebd00-612d-4556-b8ee-1208c039f1fd · file: molcy_07bebd00.mp4
- Preparation: exported · message: Preparation: REVIEW. 0 blockers and 6 requirements under review; MolChat did not decide them. · readiness: REVISION
- Delivery: building · message: This notebook is part of the delivery.

## Limits and provenance

The Vina energy is that of Vina's best pose: it is not a free energy, nor a Ki, nor a measure of activity. An iteration over a few molecules does not rank drugs. The physical checks are PoseBusters' as MolDesign declares them.

The energies, the physical checks, the protocol, the warnings and the docked species came from MolDesign; each molecule's identity, from the PubChem lookup of this conversation whose SMILES matches literally. MolChat ordered the calls, recorded what happened and wrote this notebook without the model.
