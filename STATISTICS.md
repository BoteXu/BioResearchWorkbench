# Statistics consultation and bounded analysis

Version 2.7 adds a dedicated `statistics` category. Codex reviews the research question and source evidence; the tools provide reproducible design guidance, checks and explicitly selected calculations. No separate model, API key or external statistics service is required.

## Consultation first

`guide_study_statistics(study)` fits nothing. Its required fields are `question`, `design`, `outcome_type`, `independent_unit`, `estimand`, `groups`, `repeated`, `clustered`, `primary_endpoints`, `missing_data` and `covariates`.

Design choices: randomized, observational, diagnostic, prediction or descriptive. Outcome choices: continuous, binary, count, ordinal, survival, expression or composition. Declare the population, exposure/treatment, outcome, time horizon and intended contrast in the question/estimand. Cells, spots, frames and technical measurements do not automatically constitute independent replicates.

The consultation returns candidate methods, required assumptions, missing-data guidance, prospective power guidance, multiplicity and reporting requirements. It does not choose a method from a normality-test p-value. It distinguishes causal identification, descriptive association, prediction and diagnostic performance.

## Executable functions

| Function | Behavior | Boundary |
|---|---|---|
| `audit_statistical_dataset` | Missingness by column/group, independent-unit counts, duplicated records and group overlap | No imputation or silent row removal; observed data cannot prove MCAR/MAR/MNAR |
| `compare_groups` | Two-sided Welch or paired t test, mean-difference interval, descriptive Hedges g or paired dz | Explicit unit IDs; pairing aligns by ID; no pseudoreplication, missing-value omission or automatic test switching |
| `adjust_pvalues` | BH, BY, Holm or Bonferroni for a declared complete family | No selected-significant-only family; the caller must provide all intended tests |
| `plan_sample_size` | Prospective two-sided independent common-SD or paired t scenarios; noncentral t; explicit attrition | Paired effect uses SD of differences. No exact Welch, clustered, survival or RNA-seq power claim; no observed post-hoc power |
| `fit_statistical_model` | OLS with HC3, binary logistic, Poisson with optional log exposure offset, or random-intercept linear model | Explicit typed predictors/interactions; no formula evaluation; cluster inference requires at least ten clusters; missingness and rank gates |
| `meta_analyze_effects` | Fixed or DL random effects, Q/I2/tau2 and leave-one-out sensitivity | Independent non-overlapping cohorts with identical scale/contrast; normal intervals and DL limitations retained |
| `audit_prediction_split` | Unit overlap, preprocessing-fit and tuning leakage | IDs do not detect related donors, mislabeled samples, site leakage or leaked features |

Guidance, table audits, multiplicity adjustment and split audits are available in the lightweight server edition. Scientific calculations require the optional local edition and its dependencies. Larger data/models should be dispatched to existing server environments.

`fit_statistical_model` accepts `predictors={"age":"numeric","group":"categorical"}`. Categorical references are lexicographically first and recorded in the report; confirm they match the estimand before interpreting coefficients. Interactions are explicit pairs of predictor names. Logistic effects are log odds. Poisson effects are log rates only when exposure is defined consistently; omission of an exposure offset must be justified. HC3/cluster covariance does not fix an incorrect link, confounding, separation or lack of overlap.

Mixed-model output includes variance parameters; they are not ordinary exposure effects. Convergence is checked, but convergence alone does not verify an adequate random-effects structure. Review the saved coefficient, design and diagnostic tables. Repeated units must be nested in declared clusters. Boundary fits and nonfinite tests fail rather than being reported as completed inference.

Ordinal models, survival methods, multiple imputation, clustered/complex-design power and REML/Hartung-Knapp meta-analysis are consultation topics, not implemented execution backends in this release. Their scientific specifications must be prepared and reviewed before adding a server execution adapter. Never describe a recommendation as an executed result.

## Reporting and interpretation

Prespecify primary endpoints, contrast, independent unit, missingness strategy and test family. Report effect estimates and uncertainty alongside p-values, exclusions, diagnostics, sensitivity and negative findings. Do not interpret non-significance as equivalence or a causal null. Equivalence/noninferiority requires an externally justified margin and its own planned analysis.

Synthetic known-answer checks cover mean differences, paired alignment, pseudoreplication refusal, sample size, inverse-variance pooling and actual regression backends. They establish engineering behavior, not validity of real data or clinical conclusions.

## Primary references

- [SciPy Welch t test and confidence intervals](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html)
- [Statsmodels power and sample size](https://www.statsmodels.org/stable/stats.html#power-and-sample-size-calculations)
- [Statsmodels model documentation](https://www.statsmodels.org/stable/user-guide.html)
- [SciPy FDR adjustment](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.false_discovery_control.html)
- [Dream repeated-measures expression analysis](https://bioconductor.org/packages/release/bioc/vignettes/variancePartition/inst/doc/dream.html)
