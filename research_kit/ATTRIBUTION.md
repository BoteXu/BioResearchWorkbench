# Origins and third-party attribution

BioResearchWorkbench began with Biomni and remains an independent downstream workbench. The maintained additions here are orchestration, method adapters, QC/acceptance contracts, source reviews, blank templates and visualization. Scientific algorithms and tool names remain those of the original authors; calling an original API does not make the algorithm original to this project.

- Official Biomni foundation: https://github.com/snap-stanford/Biomni (fixed upstream version and license are in the main ORIGINS.md).
- Native engine/model repositories are referenced and hash/version bound, not vendored. This includes MAGPIE, PRnet, scDiffusion, Squidiff, CellNavi, Stack, MorphDiff, ShEPhERD-2, CPA, scGPT and BoolNet/MaBoSS. Engine/model/output/data licenses are separate. Actual licensing checks precede use; missing/conflicted terms are not bypassed.
- SIRIUS/CSI, DIA-NN Academia and DOCKovalent retain their upstream restrictions. CSI is a result importer here, not an unlicensed offline reimplementation. Commercial Spectronaut and licensed engine binaries are not included.
- The user-contributed standards were revised into source-based policies, field dictionaries and templates at the user's explicit publication request. Their original Office/ZIP attachments, machine information, private fingerprints and execution evidence are not distributed.
- `scientific-visualization/assets/viewer/3Dmol-min.js` retains BSD-3-Clause plus incorporated Three.js/jQuery notices in the adjacent license files: https://github.com/3dmol/3Dmol.js/blob/master/LICENSE . It is an optional offline viewer, not a molecular analysis engine.
- `scientific-visualization/assets/fonts` retains the SIL Open Font License 1.1, reserved names and original copyright notices: https://github.com/liberationfonts/liberation-fonts/blob/main/LICENSE . Font files are unmodified; no private local font is bundled.
- Python/R libraries are dependencies installed separately. No journal reference figures, article PDFs, source poster pixels, original third-party skill repositories, private study data, model weights or software binaries are included.

Public source publication never authorizes uploading new private project data. Existing data/source receipts remain local; public examples must identify their actual public source, license, transformations and scientific/display limits separately.
