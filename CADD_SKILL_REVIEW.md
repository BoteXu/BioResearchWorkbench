# CADD skill source review

Reviewed source: [makabaka007x/cadd-skill](https://github.com/makabaka007x/cadd-skill/tree/49f09d57b9c5ace7f404b4eeb6a870b571c8efaf), commit `49f09d57b9c5ace7f404b4eeb6a870b571c8efaf`.

## Scope and disposition

The snapshot contains 13 skills, 126 tracked files and 33 Python files. All skill folders were inspected with the existing bounded static scanner. Python sources were parsed without importing them; no syntax errors were found. Workflow instructions and relevant execution, deletion, networking, archive and result-selection paths were manually reviewed. Several simulation-template extensions are excluded by the scanner; relevant templates were read separately. No source scripts or scientific engines were executed. Dependency contents, dynamic behavior and live software acceptance are outside this review.

No root license file or explicit redistribution grant was found. Public visibility alone does not grant redistribution rights. None of this collection's skill text, scripts, templates or binaries is bundled here. This project independently implements bounded audits using official documentation and credits the collection for the gap review. Direct reuse needs a compatible license and another version-specific review.

## Findings affecting adoption

These are default-behavior and correctness risks, not evidence of malicious intent. A static scan is not a safety certification. Locations refer to the reviewed commit.

| Priority | Source location | Finding | Integration decision |
| --- | --- | --- | --- |
| High | `gmx-workflow-packer/scripts/build_md_bundle.py:228`, `build_rest2_bundle.py:753`; `amber-md-expert/scripts/create_run_dir.py:56` | Force/overwrite can recursively remove a configuration-selected existing directory. GROMACS builders do this before completing a dry run. | Preserve fresh-output and reviewed-revision controls. No destructive builder copied. |
| High | `haddock/scripts/haddock.sh:94`, `:111`, `:156` | Example launch can delete a prior run, apply a local patch and start a detached process. Cleanup removes analysis/results. | Preserve runs, shared-terminal and scheduler receipts. No automatic cleanup or detached launch. |
| High | `bindingdb-skill/scripts/rest_request.py:63`, `:180` and equivalent REST helpers | Absolute path URLs override the base URL. Arbitrary hosts/headers/bodies are accepted; complete response bytes are read before compacting. | Reuse scoped database tools and approved exact public queries. No generic REST client imported. |
| High | `af-analysis/af3_ranking.py:79`, `:140`, `:401`; `af3_deepanalyze.py:46`, `:199`, `:213` | First/model-zero file assumptions can mismatch samples. Advanced analysis derives chain lengths from atom selections or guessed equal/two-chain splits and assumes protein types. Zip extraction lacks explicit expanded-size/member budgets. Summary quality categories use an undocumented cutoff. | Require explicit sample binding and ordered chains. Audit selected official summary arrays; no universal quality cutoff, metric recomputation or archive extraction. |
| Medium | `unidock-pro/scripts/analyze_unidock_results.py:45`, `:66` | Unparseable candidate outputs are omitted, hiding failure denominators. | Preserve expected/missing/failed/excluded/eligible states and exact score domains. |
| Medium | `hdock/scripts/run_hdock_case.py:67`, `:147`, `:213` | Binary search includes working-directory/ancestor files. Execution captures unbounded output without a timeout and accepts an existing output directory. | Require selected executable/version/input bindings, bounded logs and fresh server outputs. |
| Context | `amber-md-expert/SKILL.md:90`; `gmx-workflow-packer/SKILL.md:97` | Instructions embed another environment's scheduling/time-confirmation preferences. | This user's instructions and actual cluster policy govern duration, resources and authorization. |

## Mapping of all 13 source skills

| Source skill | Workbench coverage | Adoption state |
| --- | --- | --- |
| amber-md-expert | Protocol, units/time, segment and endpoint-energy review | Original audits; Amber runtime remains server-specific |
| gmx-workflow-packer | MD/tREMD/REST2 gates, checkpoint and exchange diagnostics | Original audits; GROMACS/PLUMED runtime remains server-specific |
| hdock | Macromolecular docking route, pose/control/completeness checks | Route and audit; no HDOCK runtime claim |
| haddock | Residue mapping, restraint evidence and campaign review | Original audits; no HADDOCK/CNS runtime claim |
| unidock-pro | Explicit mode, preparation/domain binding and failures | Original campaign auditor; no GPU engine installation |
| af-analysis | Sample/seed/source and selected chain-pair summary checks | Original auditor; advanced metrics remain external |
| rfdiffusion3 | Existing target/structure evidence and source/QC boundaries | Reference reviewed; no design code, weights or target-specific design pipeline incorporated |
| pubchem-pug-skill | Existing PubChem tools and specialist database plugin | Reuse; no duplicate installation |
| chembl-skill | Existing ChEMBL and activity evidence audits | Reuse; no duplicate installation |
| bindingdb-skill | Installed BindingDB specialist plugin and scoped queries | Reuse; no duplicate REST client |
| chebi-skill | Installed ChEBI specialist plugin and identity context | Reuse; no duplicate REST client |
| uniprot-skill | Existing UniProt and identifier/structure mapping | Reuse; no duplicate installation |
| rcsb-pdb-skill | Existing PDB/PDB-data and structure context | Reuse; no duplicate installation |

## Independent implementation references

The scientific algorithms retain original authorship. New Workbench code supplies contracts and review gates, not simulation, docking search, confidence prediction or energy algorithms.

- [GROMACS restart/append handling](https://manual.gromacs.org/current/user-guide/managing-simulations.html): actual checkpoint and output checksums require engine validation.
- [GROMACS replica exchange](https://manual.gromacs.org/current/reference-manual/algorithms/replica-exchange.html): exchange/state diagnostics require method-specific interpretation.
- [PLUMED partial tempering](https://www.plumed.org/doc-v2.9/user-doc/html/partial_tempering.html): scaling is force-field dependent and needs unscaled-reference energy checks.
- [AlphaFold 3 output contracts](https://github.com/google-deepmind/alphafold3/blob/main/docs/output.md): seed/sample and ordered chains matter; tokens, atoms and chains have distinct axes.
- [HADDOCK AIR documentation](https://www.bonvinlab.org/software/haddock2.4/airs/): evidence and residue mapping require review.
- [Amber force fields](https://ambermd.org/AmberModels.php) and [manuals](https://ambermd.org/Manuals.php): exact-version parameters and solvent/ion combinations require scientific choices. No manual content is redistributed.

Callable functions and validation limits: [CADD_WORKFLOWS.md](CADD_WORKFLOWS.md).
