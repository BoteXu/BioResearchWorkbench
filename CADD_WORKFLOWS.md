# CADD workflow and result review (bridge 2.12)

Eight original functions expand bounded local planning and returned-summary review. They use the Python standard library and existing private artifact reports, with no network or engine execution. Heavy preparation, trajectories, indexing and computation remain on the server. Source review: [CADD_SKILL_REVIEW.md](CADD_SKILL_REVIEW.md), [cadd_sources.json](cadd_sources.json), [ORIGINS.md](ORIGINS.md). No upstream CADD skill payload is bundled or installed.

## Discovery and meaning of results

Use `biomni_tool_catalog(category="cadd")` to inspect exact current signatures. Both editions expose these auditors. All contexts require nonempty `species`, `system`, `purpose`, `source_version`. Lowercase SHA256 strings are required for bindings. Finite JSON is limited to 2 MB; most lists to 1,000 objects, AF3 to 200 and energy runs to 100.

Reports contain input hashes, per-scope issues, private JSON/HTML outputs, `scientific_validity=not_established` and `execution_state=summary_audit_only`. `success=true` means a report was generated; `qc_gate_pass` checks the declared summary contract. Caller-declared `receipt_verified`/`binding_verified` flags do not verify inaccessible bytes or engines. Bind them to independently reviewed source receipts using existing evidence/project tools. No report certifies sampling, force fields, physical geometry or biological activity.

| Category `cadd` function | Required inputs | Purpose |
| --- | --- | --- |
| guide_cadd_workflow | `task`, `context` | Explicit software/QC routing without installation or submission |
| audit_simulation_protocol | `protocol`, `context` | MD/tREMD/REST2 stages, units, declared capability and resource gates |
| audit_restart_manifest | `segments`, `context` | Segment continuity, compatibility and checkpoint lineage |
| audit_replica_exchange | `ladder`, `exchanges`, `visits`, `context` | Adjacent exchange counters and observed walker/state mixing |
| audit_docking_campaign | `expected`, `results`, `score_domain`, `context` | Complete candidate denominator and comparable score ranking |
| audit_restraint_mapping | `mapping`, `restraints`, `context` | Explicit residue keys and located restraint evidence |
| audit_af3_records | `records`, `selected_pair`, `context` | Explicit AF3 seed/sample/source and selected chain-pair summaries |
| audit_mmgbsa_summary | `runs`, `context` | Qualified independent-run endpoint-energy estimates |

## Routing and server execution

Task values: `small_molecule_docking`, `macromolecular_docking`, `md`, `tremd`, `rest2`, `af3_review`, `endpoint_energy`. Software names indicate choices, not installed or validated engines. Protein design code/weights from the reviewed collection are not adopted.

Review inputs/QC and freeze method/source/resource versions, then use existing `workflow.prepare_remote_task` and scheduler workflows through shared SSH. Require a fresh output location, exact executable/arguments, bounded logs and expected outputs. Inspect current jobs/checkpoints before recovery. Unknown submissions and native writes are not automatically retried. Public databases reuse existing tools and approved exact queries; private sources stay private.

## Simulation protocol

Declare `engine=gromacs/amber`, `mode=md/tremd/rest2`, and nonempty `engine_version`, `force_field`, `solvent_model`, `parameterization_source`, `protonation_basis`, `equilibration_acceptance`, `convergence_observables`, `resource_budget`. Supply `system_sha256`, `topology_sha256`, `independent_starts`, `temperature_K`, `temperature_unit=K`, `duration_unit=ps`, `timestep_unit=ps`.

`stages` have unique names with `minimization`, `equilibration`, `production` in that order. Every stage has positive integer `steps`. Dynamic stages require `dt_ps` and `duration_ps`; duration equals steps times timestep. Minimization has iterations, not simulated duration. Timesteps above 0.002 ps require `large_timestep_validated=true` and independent scientific/engine evidence; this is not a recommendation to increase the timestep.

tREMD/REST2 require strictly increasing `temperatures_K`, `mpi_ranks`, positive `exchange_interval_steps`, and `pilot_receipt_verified=true`. For this PLUMED multi-topology REST2 route only, declare GROMACS, `reference_temperature_K`, `thermostat_temperatures_K` at the reference temperature, and `scales` following reference/effective temperature. Require reviewed `hot_region_reviewed`, `scaled_topologies_verified`, `hrex_verified`, `plumed_verified`, `capability_receipt_verified`. These are explicit declarations, not backend probes. Independently validate the unscaled-reference energy comparison, force-field terms, topology/hot-region mapping and pilot. Another HREX implementation needs its own adapter.

Membranes, metals, glycosylation, nucleic acids and nonstandard residues need explicit parameter/charge/component review. This module records choices; it does not generate or validate topology physics. Duration is chosen for the question and convergence observables, not a universal template.

## Restarts and replica exchange

Segments declare unique `id`, `walker`, half-open `start_step/end_step`, `dt_ps`, `engine_version`, `system_sha256`, `topology_sha256`, `protocol_sha256`, `output_checkpoint_sha256`, `receipt_sha256`, `state=completed`, integer `exit_code=0`, `receipt_verified=true`. Subsequent `input_checkpoint_sha256` equals the previous output checkpoint; intervals must be continuous. Changed protocol is a separate reviewed branch. Starting after zero is marked partial. Check physical checkpoint contents, velocities, engine append checksums and duplicate frames on the server.

Exchange review accepts an increasing numeric `ladder`, one `{state_a,state_b,attempted,accepted}` counter per adjacent state pair and visits `{step,walker_states}`. Each visit is a full permutation indexed by walker; steps are unique and sorted. Zero/missing pair counters are visible. Trips count observed low-to-high-to-low journeys; sampled visits can miss transitions. Exchange rates/trips do not prove convergence or replication. This adjacent-pair adapter does not support Gibbs/all-pairs exchange. State-demultiplexed trajectories and continuous walker trajectories answer different questions.

## Docking campaigns

`expected` rows: unique chemical-state `id`, `parent_id`, `ligand_sha256`, `role=candidate/reference/negative_control`. Parent links retain related protonation/tautomer states.

`score_domain`: `engine`, `version`, `scoring`, `units`, `search_mode`, `direction=lower/higher`, `receptor_sha256`, `preparation_sha256`, `site_sha256`. Results declare that exact domain, `id`, `ligand_sha256`, `state`, `exit_code`, finite `score`, `pose_sha256`, `pose_qc_pass`. Missing/failed/unknown/incomparable states remain in the report. Only eligible results are ranked. Arbitrary units are permitted when declared; HDOCK/HADDOCK scores are not automatically called binding energy. Different receptors/boxes/preparation/versions/methods are not pooled. Technical run aggregation is explicit before unique result rows are supplied.

Inspect actual coordinates, clashes, strain, site coverage and contacts before declaring pose QC. Review control performance, selectivity and counter-screens. Control presence does not establish acceptable performance. Technical seeds and chemical states are not biological replicates or independent parent compounds.

## Restraints

One-to-one mapping rows declare string `source_chain`, `source_residue`, `structure_chain`, `structure_residue`, `numbering_scheme`, `source_version`, boolean `present`. Preserve insertion codes and author/label numbering in exact keys.

Restraints declare unique `id`, located `evidence`, `kind=active/passive/distance`, source-key `endpoints`. Active/passive have one endpoint; distance has two and `unit=angstrom`, `lower`, `upper`. Missing/unmapped/stale residues, self distances or invalid bounds block the contract. No restraints are inferred or written; accessibility, atom names, ambiguous groups and CNS AIR semantics need expert review.

## AF3 summaries

Records declare unique `id`, `target_id`, integer `seed/sample`, `input_sha256`, `structure_sha256`, `summary_sha256`, `binding_verified`, ordered `chain_ids`, and `summary`. `selected_pair` is two distinct exact IDs. Same-target input revision changes are flagged; different targets are not globally ranked.

Summary requires finite `iptm`, `ptm`, `ranking_score`, boolean `has_clash`, correctly sized `chain_pair_iptm` and `chain_pair_pae_min`. Both directions of selected entries are preserved. Summary `chain_ids`, when provided, must match declared order. No first-file/model-zero fallback, directory scan or archive extraction occurs. Derive order from exact source outputs and reviewed structural mapping.

PAE is token-indexed; AF3 pLDDT can be atom-indexed. Components are not assumed to be proteins. This module does not implement ipSAE, pDockQ, LIS or ipTM_d0. Use a separately validated server method for advanced metrics. Confidence is not affinity, specificity, experimental interaction or design success. No universal high/medium/low cutoff is applied.

## MM/GBSA and MM/PBSA

Rows declare unique `id`, `ligand_id`, `independent_start`, `method=MMGBSA/MMPBSA`, `units=kcal/mol/kJ/mol`, finite `estimate`, positive `frames`, bounded `effective_samples`, `protocol_sha256`, `trajectory_sha256`, `topology_sha256`, explicit `solvent_parameters`, `entropy_method`, `frame_selection`, `receptor_ligand_mapping`, `equilibration_removed`, `receipt_verified`, `state=completed`, integer `exit_code=0`.

Failed/unverified/non-equilibrated/reused-trajectory estimates are excluded and reported. Qualifying values are grouped by exact ligand/method/units/protocol/solvent/entropy/frame/mapping domain. Report mean across run estimates and descriptive between-run SD. No protocol pooling, frame-as-replicate t-test or conversion to experimental Kd occurs. Independent-start provenance, effective samples, entropy omission and solvation approximations still require scientific review.

## Validation

Synthetic tests cover acceptance and refusals for time/units, REST2 capability/bath errors, checkpoint gaps/revisions, exchange permutations/counts, missing/failed/mixed-domain candidates, insertion codes, stale residue mapping, AF3 source/order/shape errors and energy independence/domain separation. They validate summary auditors, not real systems or external engines. Existing release CI handles source portability on Windows/macOS/Linux. HarmonyOS retains the owned-host browser gateway boundaries; no native hardware acceptance is added.
