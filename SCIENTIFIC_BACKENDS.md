# Fixed server scientific backends

`scientific_backend.prepare_scientific_backend` prepares, never submits. Specify
existing Rscript, verified compute host, working directory, fresh output directory,
scientific context and SHA256 data input manifest. Copy the full bundle/input files
to the declared working directory and explicitly dispatch via the existing shared
terminal/scheduler. The runner checks host, input hashes and actual process/output
completion. Reuse server packages; isolated CI installation does not install locally
or on your cluster. Inspect qc.json/failure.json/summary.json/results.rds/session.txt
separately from scheduler/runner receipts.

## SuSiE / coloc

`coloc_susie`: trait CSV columns snp,beta,varbeta,effect_allele,other_allele,position,
MAF,build,ancestry; LD CSV first-column variant IDs and exact variant column order.
Harmonize allele direction/position/build/ancestry upstream. Palindromic variants
fail rather than silently flip. Numeric values, LD symmetry/unit diagonal/bounds/
positive semidefiniteness are checked before fitting. These checks cannot verify
that LD is biologically compatible; supply LD provenance and variant coverage.

Config: trait1,trait2,ld1,ld2,genome_build,ancestry,ld_provenance,coverage_description,
trait1_type,trait2_type,N1,N2,priors. Quantitative traits need sdY1/sdY2; case-control
traits need s1/s2 case fractions. Priors is an explicit list of p1/p2/p12 triples.
Real coloc::runsusie calls require convergence and retain credible sets. Real
coloc::coloc.susie reports signal pairs across the prior grid. Review sample overlap,
LD alignment, weak signals, coverage and prior sensitivity; posterior is not causal
proof. [Upstream documentation](https://chr1swallace.github.io/coloc/articles/a06_SuSiE.html).

## decoupleR

`decoupler_activity` uses R decoupleR, not the Python decoupler package. Matrix CSV:
feature IDs then named sample/condition columns. Network CSV: source,target,weight,
signed finite nonzero weights and unique edges. Declare network_source/version,
input_scale,min_targets,methods. Input scale is normalized_expression/signed_statistic/
log_fold_change; no implicit raw count normalization. Methods select ULM and/or MLM.
Per-regulator target coverage gates fitting; method sign agreement is retained.
MLM collinearity/backend failures stay failures. TF/pathway/kinase meaning depends
on the supplied network. These are inferred scores, not direct measurements; sample
columns are not automatically independent replicates.
[ULM](https://saezlab.github.io/decoupleR/reference/run_ulm.html),
[MLM](https://saezlab.github.io/decoupleR/reference/run_mlm.html).

## metafor

`metafor_multilevel`: effect CSV effect_id,study_id,yi,vi and declared moderator
columns. Covariance CSV has exact effect IDs/order, symmetric positive-definite
matrix and diagonal matching vi. At least three studies, complete moderators and
full-rank design are mandatory; moderator models need enough independent studies.
Supply effects,covariance,effect_scale,estimand,independent_unit,moderators,
dependence_description. Covariance must represent shared controls/cohort overlap
and correlated effects; random effects cannot repair wrong sampling covariance.

Real metafor::rma.mv REML uses study/effect nested random effects and returns
coefficients/uncertainty, prediction, residuals and leave-one-study-out sensitivity,
retaining failed sensitivity fits. It does not extract effects or assess study bias
automatically. [Upstream model reference](https://wviechtb.github.io/metafor/reference/rma.mv.html).

Original upstream authors own these algorithms. This project adds fixed contracts,
QC, orchestration and receipts; no upstream algorithm code is vendored here.
