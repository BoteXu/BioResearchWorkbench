# 医学研究支持 / Clinical research support (2.10)

These tools support research, source verification and professional review. They
do not autonomously diagnose, prescribe or change a person's treatment. Private
clinical tables, identifiers, drafts, cases, paths and imaging tokens stay private.
Only an explicitly approved exact public drug name or public label identifier can
leave the device through the new official-source adapters. No personal public
API, cloud model connection, library write or patient upload is configured.

## Located medical evidence and drug information

`audit_medical_guidelines` reads selected documents, validates exact excerpt
locations, records publisher/version/date/region/population, flags declared
supersession and compares reviewer-supplied actions on the same topic. It never
claims to have discovered the latest guideline or interpreted an entire guideline.
Codex reviews negation, grades, applicability and primary evidence before drawing
a conclusion. Source dates, legal access and redistribution permissions need review.

`query_drug_reference` uses explicitly approved public names at fixed
[RxNorm](https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html) or
[DailyMed](https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm)
endpoints. RxNorm is a vocabulary/name service, not an interaction checker.
DailyMed results are US labeling, bounded and possibly ambiguous. `read_drug_label`
retrieves approved Set ID XML/history and located sections; `compare_drug_labels`
records changed sections for professional review. Availability in another region,
product equivalence, interactions and clinical relevance are separate questions.
Existing upstream interaction tools retain their actual runtime state; new
official label retrieval does not validate an untested interaction tool.

## Clinical input QC and terminology

`audit_clinical_dataset` requires unit/design definitions and checks duplicate
visits, repeated units, explicit measurement units/reference provenance,
plausibility rules, time ordering and declared event/censoring values. No implicit
filter, imputation or unit conversion occurs. A biologically unusual measurement
is a review finding, not automatically an error or diagnosis.

`audit_clinical_mapping` checks caller-supplied
[OMOP](https://ohdsi.github.io/CommonDataModel/) mappings, terminology version,
duplicate ambiguity, unresolved concepts and verification state. It does not
download terminology, claim complete ETL conformance or change a clinical database.
Vocabulary licensing and target schema compatibility remain separate checks.

## Study design and real server models

Use `statistics.guide_study_statistics` first to define estimand, independent
unit, endpoints, repetition, covariates and missingness. `guide_clinical_study`
adds time-zero/eligibility/follow-up checks for cohort, treatment comparison,
survival, multicenter and target-trial designs. It can run the existing consultation
from `statistics_study`; its checklist fits no model and proves no causal claim.

`prepare_clinical_backend` prepares checksummed fixed existing-R tasks for:

| Backend | Actual upstream method | Required review / limitations |
|---|---|---|
| `cox_survival` | survival::coxph + cox.zph, coefficients/confidence intervals | Independent single-row units, finite time/status, event count, full-rank covariates; proportional hazards and censoring need review |
| `competing_risks` | cmprsk::cuminc + covariate crr, convergence | Explicit 0=censor, 1=target, 2=competing event; no automatic cause-specific model substitution |
| `propensity_iptw` | Base R logistic propensity, ATE weighted mean difference, balance/ESS and independent-unit bootstrap interval | Numeric covariates, explicit overlap bounds, 100-2000 prespecified bootstrap replications/seed, nuisance model refitted each time; no trimming/imputation or unmeasured-confounding correction |

The statistical consultation must match the model estimand and scientific
independent unit. Initial fixed models reject repeated/clustered designs,
missing values, duplicate units and nonfinite inputs. No categorical recoding or
silent covariate selection. Prepare only; dispatch on the verified compute host
through the existing shared terminal/scheduler. Reuse jsonlite/survival/cmprsk.
Actual clinical inference and real cluster availability require their own receipts.

## Prediction validation and reporting

`audit_clinical_prediction` checks actual held-out unique units, training overlap,
preprocessing/tuning declarations and finite binary probabilities. It computes
tie-aware AUC, Brier score, calibration bins, threshold net benefit (including
treat-all/treat-none) and subgroup coverage. These are descriptive estimates;
cluster/time-dependent validation and uncertainty need dedicated server analysis.
Subgroup estimates do not establish fairness or clinical utility.

`audit_medical_reporting` uses caller-supplied official versioned checklist items
and actual reviewers' located excerpts. It supports permitted
[TRIPOD+AI/TRIPOD-LLM](https://www.tripod-statement.org/) and other reporting
checklists without redistributing their rule text. Missing/unassessed items and
not-applicable reasons remain explicit. Reporting completeness is not study validity.

## Review extraction, bias and certainty

`extract_review_effects` retains exact study/cohort/outcome/timepoint/scale,
effect/variance, source hash/location and real independent reviewer identity.
It flags pending second reviews, repeated reviewer rows and numeric disagreements.
No reviewer is simulated. Excerpt containment does not establish the correct
numeric transformation or independence; shared controls/cohorts need covariance.

`record_bias_assessment` records outcome-specific reviewer judgments for
caller-supplied versioned permitted tools, including bias and evidence certainty.
No automatic RoB/GRADE score or copyrighted grading rules are bundled. Verify
design/version and license at the
[upstream RoB site](https://www.riskofbias.info/welcome/rob-2-0-tool).

## Drug surveillance, imaging and teaching

`audit_adverse_event_reports` keeps the declared latest case version, detects
duplicate pairs and calculates a case-level reporting odds ratio with explicit
continuity correction. Public AEMS/legacy FAERS reports can be processed on the
server and returned as bounded summaries. Reports cannot establish incidence,
causation or an individual's drug safety; see the
[FDA limitations](https://www.fda.gov/drugs/fda-adverse-event-monitoring-system-aems/fda-adverse-event-monitoring-system-aems-public-dashboard).

`audit_imaging_metadata` checks supplied pseudonymous patient/series splits,
acquisition fields and label-review state. The server DICOM adapter reads no
pixels. Pseudonymous tokens and metadata remain sensitive; this is not an
anonymization tool, segmentation model or image diagnosis.

`prepare_medical_teaching` creates a private editable Markdown draft using reviewed
located claims, limits and explicitly approved synthetic/reviewed-deidentified
case material. It does not publish, train a model or independently establish facts.

## Validation and attribution

Offline tests cover substantive refusal and success cases. Isolated Linux CI
executes actual synthetic survival, competing-risk and propensity methods,
including refused design/QC cases. Public drug endpoints have separate source
receipts; offline fixtures are not live-query validation. Dataset/source receipt
hashes do not prove medical truth. Existing model/software licenses and original
authors remain acknowledged; no medical guideline rule text is vendored.
