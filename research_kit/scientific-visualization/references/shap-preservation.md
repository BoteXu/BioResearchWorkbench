# SHAP designs retained from the earlier workbench

The earlier workbench already included H33/R08 contribution swarms and H36/R11
class swarms, calibrated rose insets and concentric share rings. These are
existing design families, not newly invented templates. The original skill,
examples and source files remain intact. The v2 draft preserves the family as a
variant of `shap_summary`; it does not add another independent catalog ID.

The actual default is now `variant="reference_classic"`, `layout="inset"`: a small calibrated rose inside reserved swarm-panel space. Use `layout="compact"` for the earlier rose/ring companion. Multi-output classic pages remain available. The narrow default displays eight swarm rows and the wide default twelve; `max_features` selects more or fewer without changing the full denominator.

Use `variant="reference_classic"` for the restored combination. This is a
responsive port of the earlier design, not a claim of pixel-identical rendering.
The recent large side-by-side `beeswarm_rose` experiment is an optional alternative
and must not automatically replace the earlier design.

```python
from renderers import render_template

fig, metadata = render_template(
    "shap_summary", supplied_results,
    variant="reference_classic", width="double",
    outdir=output_directory, stem="shap_classic_v2",
)
```

`supplied_results` has `features`, `explanation.shap` (samples by features),
`explanation.feature_values` on the same axes, `explanation.unit`, and optionally
a frozen `share_table` (outputs by all features, nonnegative rows summing to one).
For one output, `positive_class` names the explained model output. For several
actual outputs, supply `class_contributions`, an ordered list of dictionaries
with `label`, `shap`, and `feature_values`. Labels are actual explained outputs,
not invented classes or automatically inferred biological subgroups. Models
with different SHAP units/backgrounds must use separate pages.

`feature_value_limits` and `feature_value_label` declare the feature-color scale.
The renderer does not fit a model or compute explanations. Units come from the actual explained output/link. Mixed raw feature units use declared within-feature range colors (Low–High); genuine standardized features retain their declared limits. A supplied full share table is verified against the complete contributions. If absent, v2.1 can create the exact display-only mean-absolute summary from all supplied contribution values. It saves the full feature magnitude/share table beside the figure and identifies this presentation aggregation in metadata. This does not compute a new SHAP explanation or refit a model.

All supplied features remain in the share denominator. The classic companion
rose and rings show eight named features plus an explicitly labeled remainder.
The small inset shows up to eight of the displayed swarm features and the
complete remainder. `max_features` changes displayed rows, never the complete
denominator. Set `max_features=len(features)` for all rows. Feature names wrap
with extra row height. The same feature keeps the same color in roses and rings; the swarm
color represents the supplied feature value, a different variable.

Rose sectors have equal angles and areas proportional to shares. The radius
therefore uses the square root of share. Rings encode shares by angle, with an
explicit outer-to-inner output order and a complete feature key. Both retain a
complete denominator; neither displays mean SHAP as a causal effect.

Layout options include `width="single"|"onehalf"|"double"`, `ncols`, `nrows`,
and `max_features`. At most two output columns are supported in this port;
excessively tall pages fail clearly and require output pagination. The original
multi-output reference remains available in the earlier workbench.

The real WDBC validation case contains one explained malignant log-odds output,
569 observations and 30 features. It reuses a frozen exact linear explanation
from a full-data descriptive fit. Its performance plots use separate OOF
predictions. These are not external clinical validation and not TreeSHAP.

Acceptance is per export and hash-bound. The layout port is not automatically
an aesthetic improvement: retain the earlier reference when it is more readable
or attractive, and compare using the same supplied channels.
