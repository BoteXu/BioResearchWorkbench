> Legacy reference preserved. For current result-only calls and tested contracts, read [v2 API](v2-api.md). These original examples may include analysis or placeholder assembly and do not constitute current runtime acceptance.

# Machine Learning Figures

Model evaluation and interpretation visualization: classification and
regression benchmarks, feature importance, SHAP explanations, clustering
diagnostics. Data typically: sklearn model objects or prediction tables
(y_true, y_pred, y_prob), CV results, SHAP values, feature matrices.

## Catalog

| Question | Figure | Data input | Language | Template id |
|---|---|---|---|---|
| Which classifier wins? | Multi-model ROC with CI bands | y_true + y_prob per model | py | `roc_multi` |
| Precision-recall trade-off | PR curve | y_true + y_prob | py | `pr_curve` |
| Where does it err? | Confusion matrix (counts + rates) | y_true + y_pred | py | `confusion` |
| Are probabilities calibrated? | Calibration curve + Brier | y_true + y_prob | py | `calibration` |
| How much lift over random? | Cumulative gain / lift chart | y_true + y_prob | py | `gain_lift` |
| What drives predictions? | Feature importance (2 methods) | fitted model + X | py | `feat_importance` |
| SHAP explanation | SHAP beeswarm + bar | shap values | py | `shap_summary` |
| How does one feature act? | SHAP dependence scatter | shap values + X | py | `shap_dependence` |
| Do SHAP effects interact? | SHAP interaction heatmap | shap interaction values | py | `shap_interaction` |
| Enough data? | Learning curve with variance band | model + X, y | py | `learning_curve` |
| Which hyperparameters? | Grid-search heatmap | cv_results | py | `grid_heatmap` |
| Regression accuracy | Predicted vs true (density) | y_true + y_pred | py | `reg_scatter` |
| Regression diagnostics | Residual 2×2 panel | y_true + y_pred | py | `reg_diagnostics` |
| Where is the boundary? | 2D decision boundary | model + 2 features | py | `decision_boundary` |
| Cluster structure | Silhouette plot | labels + distances | py | `silhouette` |
| How many clusters? | Elbow + silhouette combo | inertia + sil per k | py | `k_selection` |
| Model comparison across folds | CV score boxplots | CV results table | py | `cv_box` |
| Feature redundancy | Feature correlation heatmap | X | py | `feat_corr` |
| Training evidence | Training-curve dashboard | epoch history table | py | `training_dashboard` |
| Many metrics at a glance | Radar (normalized) | model × metric table | py | `radar` |
| Do classes separate in feature space? | Parallel coordinates | X + class labels | py | `parallel_coords` |
| How does one feature act? | PDP + ICE curves | fitted model + X | py | `pdp_ice` |

---

### roc_multi — Multi-model ROC with confidence bands `id: roc_multi`

```python
# INPUT : dict preds {model_name: (y_true(array), y_prob(array))}; optional n_boot
# OUTPUT: fig_roc.png/svg
# DEPENDS: sklearn, matplotlib
import matplotlib.pyplot as plt, numpy as np
from sklearn.metrics import roc_curve, roc_auc_score, auc
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
def roc_ci(y, p, n_boot=300, seed=0):
    rng = np.random.default_rng(seed)
    fprs = np.linspace(0, 1, 100); aucs = []
    curves = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) < 2: continue
        fpr, tpr, _ = roc_curve(y[idx], p[idx])
        curves.append(np.interp(fprs, fpr, tpr))
        aucs.append(roc_auc_score(y[idx], p[idx]))
    lo, hi = np.percentile(curves, [2.5, 97.5], axis=0)
    return fprs, lo, hi, np.mean(aucs), np.std(aucs)

fig, ax = plt.subplots(figsize=journal_size("single", 1.0))
for i, (name, (y, p)) in enumerate(preds.items()):
    fpr, tpr, _ = roc_curve(y, p)
    c = cat_palette(len(preds))[i]
    ax.plot(fpr, tpr, c=c, lw=1.8, label=f"{name} (AUC {roc_auc_score(y, p):.2f})")
    try:
        _, lo, hi, _, _ = roc_ci(np.asarray(y), np.asarray(p))
        ax.fill_between(fpr, lo, hi, color=c, alpha=0.12, lw=0)
    except Exception:
        pass
ax.plot([0, 1], [0, 1], c="#999999", lw=0.8, ls="--")
ax.set(xlabel="False positive rate", ylabel="True positive rate",
       xlim=(-0.02, 1.02), ylim=(-0.02, 1.02))
ax.legend(loc="lower right", fontsize=7)
beautify(ax)
save_fig(fig, "fig_roc")
```

### pr_curve — Precision-recall curve `id: pr_curve`

```python
# INPUT : dict preds {model_name: (y_true, y_prob)}
# OUTPUT: fig_pr.png/svg
# DEPENDS: sklearn, matplotlib
import matplotlib.pyplot as plt
from sklearn.metrics import precision_recall_curve, average_precision_score
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 1.0))
for i, (name, (y, p)) in enumerate(preds.items()):
    prec, rec, _ = precision_recall_curve(y, p)
    ap = average_precision_score(y, p)
    ax.plot(rec, prec, c=cat_palette(len(preds))[i], lw=1.8,
            label=f"{name} (AP {ap:.2f})")
ax.set(xlabel="Recall", ylabel="Precision", xlim=(-0.02, 1.02), ylim=(-0.02, 1.02))
ax.legend(loc="lower left", fontsize=7)
beautify(ax)
save_fig(fig, "fig_pr")
```

### confusion — Confusion matrix with counts and rates `id: confusion`

```python
# INPUT : arrays y_true, y_pred (labels); list names (class names)
# OUTPUT: fig_confusion.png/svg
# DEPENDS: sklearn, matplotlib
import matplotlib.pyplot as plt, numpy as np
from sklearn.metrics import confusion_matrix
from biostyle import use_style, save_fig, journal_size, seq_cmap

use_style("journal")
cm = confusion_matrix(y_true, y_pred)
rate = cm / cm.sum(axis=1, keepdims=True)
fig, ax = plt.subplots(figsize=journal_size("single", 0.9))
im = ax.imshow(rate, cmap=seq_cmap("mako"), vmin=0, vmax=1)
ax.set_xticks(range(len(names)), names, rotation=45, ha="right")
ax.set_yticks(range(len(names)), names)
for i in range(cm.shape[0]):
    for j in range(cm.shape[1]):
        ax.text(j, i, f"{cm[i, j]}\n{rate[i, j]:.0%}", ha="center", va="center",
                fontsize=7, color="white" if rate[i, j] > 0.5 else "#1A1A1A")
ax.set(xlabel="Predicted", ylabel="True")
for s in ax.spines.values(): s.set_visible(False)
save_fig(fig, "fig_confusion")
```

### calibration — Calibration curve + Brier `id: calibration`

```python
# INPUT : dict preds {model_name: (y_true, y_prob)}
# OUTPUT: fig_calibration.png/svg
# DEPENDS: sklearn, matplotlib
import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 0.9))
ax.plot([0, 1], [0, 1], c="#999999", lw=0.8, ls="--", label="Perfectly calibrated")
for i, (name, (y, p)) in enumerate(preds.items()):
    frac_pos, mean_p = calibration_curve(y, p, n_bins=10, strategy="quantile")
    b = brier_score_loss(y, p)
    ax.plot(mean_p, frac_pos, marker="o", ms=3, lw=1.4,
            c=cat_palette(len(preds))[i], label=f"{name} (Brier {b:.3f})")
ax.set(xlabel="Mean predicted probability", ylabel="Observed fraction positive")
ax.legend(loc="upper left", fontsize=7)
beautify(ax)
save_fig(fig, "fig_calibration")
```

### gain_lift — Cumulative gain and lift `id: gain_lift`

```python
# INPUT : array y_true, array y_prob (binary)
# OUTPUT: fig_gain_lift.png/svg (2 panels)
# DEPENDS: matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, beautify, panel_labels

use_style("journal")
order = np.argsort(-y_prob)
y_sorted = np.asarray(y_true)[order]
x = np.arange(1, len(y_sorted) + 1) / len(y_sorted)
gain = np.cumsum(y_sorted) / y_sorted.sum()
lift = gain / x
fig, axes = plt.subplots(1, 2, figsize=journal_size("onehalf", 0.5))
axes[0].plot(x, gain, c="#0072B2", lw=1.8, label="Model")
axes[0].plot([0, 1], [0, 1], c="#999999", ls="--", lw=0.8, label="Random")
axes[0].set(xlabel="Fraction targeted", ylabel="Cumulative gain")
axes[0].legend(fontsize=7)
axes[1].plot(x, lift, c="#D55E00", lw=1.8)
axes[1].axhline(1, c="#999999", ls="--", lw=0.8)
axes[1].set(xlabel="Fraction targeted", ylabel="Lift")
for ax in axes: beautify(ax)
panel_labels(fig, axes)
save_fig(fig, "fig_gain_lift")
```

### feat_importance — Feature importance, two methods `id: feat_importance`

```python
# INPUT : fitted sklearn model, X (DataFrame), y; n_repeats for permutation
# OUTPUT: fig_importance.png/svg (paired bars: impurity vs permutation)
# DEPENDS: sklearn, matplotlib
import matplotlib.pyplot as plt, numpy as np
from sklearn.inspection import permutation_importance
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
perm = permutation_importance(model, X, y, n_repeats=20, random_state=0)
imp = perm.importances_mean
order = np.argsort(imp)[-15:]                       # top 15
fig, ax = plt.subplots(figsize=journal_size("single", 0.9))
ypos = np.arange(len(order))
ax.barh(ypos + 0.2, imp[order], height=0.38, color="#0072B2", label="Permutation")
if hasattr(model, "feature_importances_"):
    fi = model.feature_importances_ / model.feature_importances_.sum()
    ax.barh(ypos - 0.2, fi[order], height=0.38, color="#FF9400", label="Impurity")
ax.set_yticks(ypos, X.columns[order], fontsize=7)
ax.set(xlabel="Importance (normalized)")
ax.legend(fontsize=7, loc="lower right")
beautify(ax); ax.grid(axis="x", alpha=0.3); ax.grid(axis="y", visible=False)
save_fig(fig, "fig_importance")
```

### shap_summary — SHAP beeswarm + bar `id: shap_summary`

```python
# INPUT : shap.Explanation or (shap_values, X) for a fitted model
# OUTPUT: fig_shap.png/svg (2 panels: beeswarm + mean |SHAP| bar)
# DEPENDS: shap, matplotlib
import matplotlib.pyplot as plt, shap
from biostyle import use_style, save_fig, journal_size

use_style("journal")
fig = plt.figure(figsize=journal_size("onehalf", 0.6))
ax1 = fig.add_subplot(121)
shap.plots.beeswarm(shap_values, max_display=12, show=False)
ax1 = plt.gca(); ax1.set_xlabel("")
ax2 = fig.add_subplot(122)
shap.plots.bar(shap_values, max_display=12, show=False)
plt.gcf().set_size_inches(*journal_size("double", 0.45))
save_fig(plt.gcf(), "fig_shap")
```

Note: SHAP explains the model, not the biology; pair with domain knowledge
and state the model + data in the caption. Correlated features split credit.

### shap_dependence — SHAP dependence scatter `id: shap_dependence`

```python
# INPUT : shap_values (Explanation), X, feature name, optional interaction feature
# OUTPUT: fig_shap_dep.png/svg
# DEPENDS: shap, matplotlib
import matplotlib.pyplot as plt, shap
from biostyle import use_style, save_fig, journal_size, add_colorbar

use_style("journal")
fig = plt.figure(figsize=journal_size("single", 0.8))
ax = fig.add_subplot(111)
shap.plots.scatter(shap_values[:, feature], color=shap_values[:, color_by],
                   ax=ax, show=False)
save_fig(fig, "fig_shap_dep")
```

### shap_interaction — SHAP interaction heatmap `id: shap_interaction`

```python
# INPUT : ndarray shap_int (n_features x n_features, mean |SHAP interaction|)
# OUTPUT: fig_shap_int.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, seq_cmap, add_colorbar

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 1.0))
im = ax.imshow(shap_int, cmap=seq_cmap("mako"))
ax.set_xticks(range(len(names)), names, rotation=45, ha="right", fontsize=6.5)
ax.set_yticks(range(len(names)), names, fontsize=6.5)
add_colorbar(fig, im, ax, label="mean |SHAP interaction|")
save_fig(fig, "fig_shap_int")
```

### learning_curve — Learning curve with variance band `id: learning_curve`

```python
# INPUT : fitted estimator (clone-able), X, y
# OUTPUT: fig_learning.png/svg
# DEPENDS: sklearn, matplotlib
import matplotlib.pyplot as plt, numpy as np
from sklearn.model_selection import learning_curve
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
sizes, tr, va = learning_curve(model, X, y, cv=5,
                               train_sizes=np.linspace(0.1, 1.0, 8),
                               scoring="roc_auc", n_jobs=-1)
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
ax.fill_between(sizes, va.mean(1) - va.std(1), va.mean(1) + va.std(1),
                color="#0072B2", alpha=0.15, lw=0)
ax.plot(sizes, tr.mean(1), c="#FF9400", lw=1.6, label="Train")
ax.plot(sizes, va.mean(1), c="#0072B2", lw=1.6, label="CV")
ax.set(xlabel="Training examples", ylabel="ROC AUC")
ax.legend(loc="lower right")
beautify(ax)
save_fig(fig, "fig_learning")
```

### grid_heatmap — Grid-search heatmap `id: grid_heatmap`

```python
# INPUT : dict cv_results (from GridSearchCV.cv_results_), param names p1, p2
# OUTPUT: fig_grid.png/svg
# DEPENDS: matplotlib, pandas
import matplotlib.pyplot as plt, pandas as pd, numpy as np
from biostyle import use_style, save_fig, journal_size, seq_cmap, add_colorbar

use_style("journal")
df = pd.DataFrame(cv_results)
piv = df.pivot_table(index=f"param_{p1}", columns=f"param_{p2}",
                     values="mean_test_score")
fig, ax = plt.subplots(figsize=journal_size("single", 0.85))
im = ax.imshow(piv, cmap=seq_cmap("mako"), aspect="auto")
ax.set_xticks(range(piv.shape[1]), piv.columns, rotation=45, ha="right")
ax.set_yticks(range(piv.shape[0]), piv.index)
ax.set(xlabel=p2, ylabel=p1)
i = np.unravel_index(np.argmax(piv.to_numpy()), piv.shape)
ax.scatter(i[1], i[0], marker="*", s=120, c="#FF9400", edgecolor="white", lw=0.6)
add_colorbar(fig, im, ax, label="Mean CV score")
save_fig(fig, "fig_grid")
```

### reg_scatter — Predicted vs true (density) `id: reg_scatter`

```python
# INPUT : arrays y_true, y_pred
# OUTPUT: fig_reg.png/svg
# DEPENDS: matplotlib, scipy
import matplotlib.pyplot as plt, numpy as np
from scipy.stats import gaussian_kde
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
xy = np.vstack([y_true, y_pred])
z = gaussian_kde(xy)(xy)
o = np.argsort(z)
fig, ax = plt.subplots(figsize=journal_size("single", 0.9))
sc = ax.scatter(y_true[o], y_pred[o], c=z[o], s=12, cmap="mako", lw=0)
lim = [min(y_true.min(), y_pred.min()), max(y_true.max(), y_pred.max())]
ax.plot(lim, lim, c="#999999", lw=0.8, ls="--")
rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
r = np.corrcoef(y_true, y_pred)[0, 1]
ax.text(0.04, 0.96, f"RMSE = {rmse:.2f}\nPearson r = {r:.2f}  (n = {len(y_true)})",
        transform=ax.transAxes, va="top", fontsize=7.5)
ax.set(xlabel="Observed", ylabel="Predicted")
beautify(ax)
save_fig(fig, "fig_reg")
```

### reg_diagnostics — Residual 2×2 panel `id: reg_diagnostics`

```python
# INPUT : arrays y_true, y_pred (+ optional exog for QQ)
# OUTPUT: fig_diagnostics.png/svg (residuals vs fitted, QQ, scale-location, leverage)
# DEPENDS: matplotlib, scipy
import matplotlib.pyplot as plt, numpy as np
from scipy import stats
from biostyle import use_style, save_fig, journal_size, beautify, panel_labels

use_style("journal")
res = y_true - y_pred
std_res = res / res.std()
fig, axes = plt.subplots(2, 2, figsize=journal_size("double", 0.5))
axes[0, 0].scatter(y_pred, res, s=6, c="#0072B2", lw=0)
axes[0, 0].axhline(0, c="#999999", lw=0.8, ls="--")
axes[0, 0].set(xlabel="Fitted", ylabel="Residuals")
stats.probplot(std_res, plot=axes[0, 1])
axes[0, 1].set(xlabel="Theoretical quantiles", ylabel="Standardized residuals")
axes[1, 0].scatter(y_pred, np.sqrt(np.abs(std_res)), s=6, c="#D55E00", lw=0)
axes[1, 0].set(xlabel="Fitted", ylabel="√|standardized residuals|")
leverage = (y_pred - y_pred.mean()) ** 2 / np.sum((y_pred - y_pred.mean()) ** 2)
axes[1, 1].scatter(leverage, std_res, s=6, c="#009E73", lw=0)
axes[1, 1].set(xlabel="Leverage (proxy)", ylabel="Standardized residuals")
for ax in axes.flat: beautify(ax)
panel_labels(fig, axes)
save_fig(fig, "fig_diagnostics")
```

### decision_boundary — 2D decision boundary `id: decision_boundary`

```python
# INPUT : fitted model (2 features), X2 (DataFrame, 2 cols), y
# OUTPUT: fig_boundary.png/svg
# DEPENDS: sklearn, matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, cat_palette, div_cmap, beautify

use_style("journal")
xx, yy = np.meshgrid(np.linspace(X2.iloc[:, 0].min() - 1, X2.iloc[:, 0].max() + 1, 300),
                     np.linspace(X2.iloc[:, 1].min() - 1, X2.iloc[:, 1].max() + 1, 300))
if hasattr(model, "predict_proba"):
    Z = model.predict_proba(np.c_[xx.ravel(), yy.ravel()])[:, 1].reshape(xx.shape)
else:
    Z = model.predict(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)
fig, ax = plt.subplots(figsize=journal_size("single", 0.9))
cf = ax.contourf(xx, yy, Z, levels=20, cmap=div_cmap("brand"), alpha=0.85)
ax.scatter(X2.iloc[:, 0], X2.iloc[:, 1], c=[cat_palette(2)[int(v)] for v in y],
           s=8, edgecolor="white", lw=0.3)
ax.set(xlabel=X2.columns[0], ylabel=X2.columns[1])
beautify(ax)
save_fig(fig, "fig_boundary")
```

### silhouette — Silhouette plot `id: silhouette`

```python
# INPUT : array labels (cluster per sample), ndarray D (distance matrix) or X
# OUTPUT: fig_silhouette.png/svg
# DEPENDS: sklearn, matplotlib
import matplotlib.pyplot as plt, numpy as np
from sklearn.metrics import silhouette_samples
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
s = silhouette_samples(X, labels)
order = np.argsort([s[labels == c].mean() for c in np.unique(labels)])
fig, ax = plt.subplots(figsize=journal_size("single", 1.0))
y0 = 8
for ci, c in enumerate(np.unique(labels)[order]):
    vals = np.sort(s[labels == c])
    ax.barh(np.arange(y0, y0 + len(vals)), vals, height=1.0,
            color=cat_palette(len(np.unique(labels)))[ci], lw=0)
    y0 += len(vals) + 6
ax.axvline(s.mean(), c="#D55E00", lw=1.2, ls="--")
ax.text(s.mean(), y0, f" mean {s.mean():.2f}", fontsize=7, c="#D55E00")
ax.set(xlabel="Silhouette coefficient", yticks=[])
for sp in ("top", "right", "left"): ax.spines[sp].set_visible(False)
save_fig(fig, "fig_silhouette")
```

### k_selection — Elbow + silhouette combo `id: k_selection`

```python
# INPUT : list ks, list inertias, list sils (per k)
# OUTPUT: fig_k_selection.png/svg (twin axes)
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
import numpy as np
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
ax.plot(ks, inertias, c="#0072B2", lw=1.6, marker="o", ms=4, label="Inertia")
ax.set(xlabel="Number of clusters k", ylabel="Inertia")
ax.tick_params(axis="y", colors="#0072B2")
ax.yaxis.label.set_color("#0072B2")
ax2 = ax.twinx()
ax2.plot(ks, sils, c="#D55E00", lw=1.6, marker="s", ms=4, label="Silhouette")
ax2.set_ylabel("Mean silhouette", color="#D55E00")
ax2.spines["right"].set_visible(True)
best = ks[int(np.argmax(sils))]
ax2.scatter([best], [max(sils)], s=110, facecolor="none",
            edgecolor="#D55E00", lw=1.4, zorder=5)
beautify(ax)
save_fig(fig, "fig_k_selection")
```

### cv_box — Multi-model CV score boxplots `id: cv_box`

```python
# INPUT : DataFrame cv, columns: model(str), fold(int), score(float)
# OUTPUT: fig_cv_box.png/svg
# DEPENDS: matplotlib, seaborn
import matplotlib.pyplot as plt, seaborn as sns
from biostyle import use_style, save_fig, journal_size, beautify, grid_axis

use_style("journal")
order = cv.groupby("model").score.median().sort_values(ascending=False).index
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
sns.boxplot(cv, x="model", y="score", order=order, width=0.55,
            fliersize=0, boxprops=dict(facecolor="#DCE8F2", edgecolor="#33506B"),
            medianprops=dict(color="#D55E00", lw=1.6),
            whiskerprops=dict(color="#33506B"), capprops=dict(color="#33506B"), ax=ax)
sns.stripplot(cv, x="model", y="score", order=order, size=3,
              color="#333333", alpha=0.6, ax=ax)
ax.set(xlabel="", ylabel="CV score (ROC AUC)")
ax.tick_params(axis="x", rotation=30)
beautify(ax); grid_axis(ax, "y", on=False)
save_fig(fig, "fig_cv_box")
```

### feat_corr — Feature correlation heatmap `id: feat_corr`

```python
# INPUT : DataFrame X (features as columns)
# OUTPUT: fig_featcorr.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, div_cmap, add_colorbar

use_style("journal")
C = X.corr()
fig, ax = plt.subplots(figsize=journal_size("single", 1.0))
im = ax.imshow(C, cmap=div_cmap("brand"), vmin=-1, vmax=1)
ax.set_xticks(range(len(C)), C.columns, rotation=45, ha="right", fontsize=6.5)
ax.set_yticks(range(len(C)), C.index, fontsize=6.5)
for s in ax.spines.values(): s.set_visible(False)
add_colorbar(fig, im, ax, label="Pearson r")
save_fig(fig, "fig_featcorr")
```

### training_dashboard — Training-curve dashboard `id: training_dashboard`

Loss/metric curves for train and validation splits across epochs, with the
selected epoch marked — the training-evidence companion to any model figure.

```python
# INPUT : DataFrame hist, columns: epoch(int), split("train"/"val"), metric(str), value(float)
# OUTPUT: fig_training.png/svg (one panel per metric)
# DEPENDS: matplotlib, numpy
import matplotlib.pyplot as plt
import numpy as np
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify, panel_labels

use_style("journal")
metrics = hist.metric.unique().tolist()
fig, axes = plt.subplots(1, len(metrics), figsize=journal_size("onehalf", 0.45 * len(metrics) / 2 + 0.3))
axes = np.atleast_1d(axes)
for ax, metric in zip(axes, metrics):
    d = hist[hist.metric == metric]
    for split, ls in [("train", "-"), ("val", "--")]:
        dd = d[d.split == split]
        ax.plot(dd.epoch, dd.value, ls, c=cat_palette(2)[split == "val"],
                lw=1.6, label=split)
    best = d[d.split == "val"].loc[d[d.split == "val"].value.idxmin()]
    ax.scatter(best.epoch, best.value, s=48, facecolor="none",
               edgecolor="#D55E00", lw=1.2, zorder=5)
    ax.set(xlabel="Epoch", ylabel=metric, title=metric)
    beautify(ax)
axes[0].legend(fontsize=7)
panel_labels(fig, axes)
save_fig(fig, "fig_training")
```

### radar — Multi-model multi-metric radar `id: radar`

Compare models across ≥5 normalized metrics at a glance. Use only when all
metrics share a common direction (higher = better after normalization);
never for publication without the underlying numbers elsewhere.

```python
# INPUT : DataFrame scores (index=model, columns=metric, values normalized 0-1)
# OUTPUT: fig_radar.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, cat_palette

use_style("journal")
labels = scores.columns.tolist()
ang = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
ang += ang[:1]
fig, ax = plt.subplots(figsize=journal_size("single", 1.0),
                       subplot_kw=dict(polar=True))
for i, (model, row) in enumerate(scores.iterrows()):
    vals = row.tolist() + [row.iloc[0]]
    ax.plot(ang, vals, c=cat_palette(len(scores))[i], lw=1.6, label=model)
    ax.fill(ang, vals, c=cat_palette(len(scores))[i], alpha=0.12, lw=0)
ax.set_xticks(ang[:-1], labels, fontsize=7)
ax.set_yticks([0.25, 0.5, 0.75, 1.0], ["0.25", "0.5", "0.75", "1"], fontsize=6)
ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), fontsize=7)
ax.grid(alpha=0.3)
save_fig(fig, "fig_radar")
```

### parallel_coords — Parallel coordinates `id: parallel_coords`

Yellowbrick-style feature-space view: each line is one sample crossing
min-max-normalized feature axes, colored by class. Use for class-separation
checks and biomarker-panel intuition. Normalize per axis or the largest-scale
feature flattens everything else; subsample above ~2000 lines or the plot
turns to mud.

```python
# INPUT : DataFrame X (samples x numeric features); Series y (class per sample)
# OUTPUT: fig_parallel.png/svg
# DEPENDS: matplotlib, pandas, numpy
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
Xn = (X - X.min()) / (X.max() - X.min() + 1e-12)        # per-axis min-max
classes = sorted(y.unique(), key=str)
pal = cat_palette(len(classes))
if len(Xn) > 2000:                                       # keep lines readable
    idx = np.random.RandomState(0).choice(len(Xn), 2000, replace=False)
    Xn, y = Xn.iloc[idx].reset_index(drop=True), y.iloc[idx].reset_index(drop=True)
fig, ax = plt.subplots(figsize=journal_size("double", 0.55))
xs = np.arange(Xn.shape[1])
for i, c in enumerate(classes):
    m = (y == c).to_numpy()
    ax.plot(xs, Xn[m].T, c=pal[i], lw=0.5, alpha=0.25, label=c)
ax.set(xticks=xs, xticklabels=Xn.columns.tolist(),
       ylabel="Normalized value (0-1)")
ax.tick_params(axis="x", rotation=30)
ax.legend(ncols=min(4, len(classes)), fontsize=7, loc="upper right",
          frameon=False)
beautify(ax)
save_fig(fig, "fig_parallel")
```

### pdp_ice — PDP + ICE curves `id: pdp_ice`

Partial dependence (bold) over individual conditional expectation curves
(faint) for one feature — shows the average effect AND its heterogeneity
across samples. Sample ≤200 ICE lines; state the model and n.

```python
# INPUT : fitted sklearn model model; DataFrame X; str feature
# OUTPUT: fig_pdp_ice.png/svg
# DEPENDS: matplotlib, numpy
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
grid = np.linspace(X[feature].min(), X[feature].max(), 60)
Xc = X.copy()
ice = np.zeros((len(X), len(grid)))
for j, v in enumerate(grid):
    Xc[feature] = v
    ice[:, j] = model.predict(Xc)
pdp = ice.mean(0)
fig, ax = plt.subplots(figsize=journal_size("single", 0.8))
ax.plot(grid, ice[:200].T, c="#BBBBBB", lw=0.4, alpha=0.5)
ax.plot(grid, pdp, c="#0072B2", lw=2.0, label="PDP (mean)")
ax.set(xlabel=feature, ylabel="Predicted value")
ax.legend(fontsize=7, frameon=False, loc="best")
beautify(ax)
save_fig(fig, "fig_pdp_ice")
```

---

## Beauty checklist (ML)

- ROC/PR: state n and class balance; CI bands from bootstrap, not wishful
  smoothness; legend inside axes, no frame.
- Confusion matrix: show counts AND row-normalized rates; color by rate.
- Twin-axis plots (k_selection): color axis labels to match their series.
- SHAP: state model, data, and that SHAP shows attribution, not causation.
- All "score" axes: name the metric exactly (ROC AUC, AP, RMSE...).

## Common pitfalls

- Averaging ROC curves point-wise instead of computing AUC per fold.
- Reading SHAP dependence as causal effect; correlated features distort it.
- Decision boundary plots on 2 features of a model trained on many — label
  as a 2D projection.
- Silhouette with Euclidean distance on one-hot/categorical features.
