> Legacy reference preserved. For current result-only calls and tested contracts, read [v2 API](v2-api.md). These original examples may include analysis or placeholder assembly and do not constitute current runtime acceptance.

# Molecular Dynamics Figures

Trajectory analysis visualization: convergence, flexibility, free energy,
correlated motion, binding energy. Data typically: GROMACS `.xvg` /
cpptraj `.dat` exports (time series), distance/contact matrices, MM-PBSA
decomposition tables, or trajectories parsed with MDAnalysis/mdtraj.

## Catalog

| Question | Figure | Data input | Language | Template id |
|---|---|---|---|---|
| Has the simulation converged? | RMSD overlay (multi-system) | time series | py | `rmsd_overlay` |
| Which regions are flexible? | RMSF with secondary-structure bands | per-residue series | py | `rmsf` |
| Is the protein compact/stable? | Rg + SASA time series + distributions | time series | py | `rg_sasa` |
| How stable are H-bonds? | H-bond count series + histogram | time series | py | `hbond` |
| Is a key distance/angle stable? | Time series + ridgeline density | time series | py | `dist_ridge` |
| What does the free-energy landscape look like? | 2D FEL contour | two CVs | py | `fel_2d` |
| PMF along a coordinate | 1D PMF curves | profile table | py | `pmf_1d` |
| How does the trajectory explore space? | Trajectory PCA (time-colored) | feature matrix | py | `traj_pca` |
| Which residue pairs contact? | Contact-frequency matrix | contact matrix | py | `contact_map` |
| Which motions are correlated? | DCCM matrix | correlation matrix | py | `dccm` |
| Is backbone geometry sane? | Ramachandran density | φ/ψ angles | py | `ramachandran` |
| Which energy terms drive binding? | MM-PBSA stacked components | energy table | py | `mmpbsa_stack` |
| Which residues drive binding? | Per-residue ΔG waterfall | energy table | py | `mmpbsa_residue` |
| Are estimates converged? | Block-average convergence | time series | py | `convergence` |
| When does each contact live? | IFP barcode (residue × frame) | interaction fingerprint table | py | `ifp_barcode` |
| Does the trajectory revisit states? | Pairwise 2D-RMSD matrix | frame × frame RMSD | py | `rmsd_2d` |
| How do states populate over time? | State-occupancy stacked area | state label per frame | py | `state_occupancy` |

---

### rmsd_overlay — Multi-system RMSD overlay `id: rmsd_overlay`

```python
# INPUT : dict series {system_name: DataFrame(time(ns), rmsd(nm))}
# OUTPUT: fig_rmsd.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt, pandas as pd
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.5))
for i, (name, d) in enumerate(series.items()):
    r = d.rmsd.rolling(50, min_periods=1).mean()          # rolling mean overlay
    ax.plot(d.time, d.rmsd, c=cat_palette(len(series))[i], lw=0.4, alpha=0.25)
    ax.plot(d.time, r, c=cat_palette(len(series))[i], lw=1.8, label=name)
ax.set(xlabel="Time (ns)", ylabel="RMSD (nm)")
ax.legend(loc="best", ncol=len(series) // 2 + 1)
beautify(ax)
save_fig(fig, "fig_rmsd")
```

### rmsf — RMSF with secondary-structure bands `id: rmsf`

```python
# INPUT : dict systems {name: DataFrame(resid(int), rmsf(nm))};
#         list sse [(start, end, "H"/"E")] secondary-structure elements
# OUTPUT: fig_rmsf.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.5))
sse_color = {"H": "#E9ED4C", "E": "#9FB8CE"}
for (a, b, t) in sse:
    ax.axvspan(a, b, color=sse_color.get(t, "#EEEEEE"), alpha=0.35, lw=0)
for i, (name, d) in enumerate(systems.items()):
    ax.plot(d.resid, d.rmsf, c=cat_palette(len(systems))[i], lw=1.4, label=name)
ax.set(xlabel="Residue number", ylabel="RMSF (nm)")
ax.legend(loc="upper right")
beautify(ax)
save_fig(fig, "fig_rmsf")
```

### rg_sasa — Rg and SASA panels `id: rg_sasa`

```python
# INPUT : dict series {name: DataFrame(time, rg, sasa_total, sasa_polar, sasa_apolar)}
# OUTPUT: fig_rg_sasa.png/svg (2x2: Rg series, Rg dist, SASA series, SASA decomposition)
# DEPENDS: matplotlib, scipy
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import gaussian_kde
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify, panel_labels

use_style("journal")
fig, axes = plt.subplots(2, 2, figsize=journal_size("double", 0.5))
d = next(iter(series.values()))                   # single-system example
axes[0, 0].plot(d.time, d.rg.rolling(50, min_periods=1).mean(), c="#0072B2", lw=1.2)
axes[0, 0].set(ylabel="Rg (nm)")
kde = gaussian_kde(d.rg); xs = np.linspace(d.rg.min(), d.rg.max(), 200)
axes[0, 1].fill_between(xs, kde(xs), color="#0072B2", alpha=0.7, lw=0)
axes[0, 1].set(xlabel="Rg (nm)", ylabel="Density")
axes[1, 0].plot(d.time, d.sasa_total.rolling(50, min_periods=1).mean(), c="#D55E00", lw=1.2)
axes[1, 0].set(xlabel="Time (ns)", ylabel="SASA (nm$^2$)")
axes[1, 1].stackplot(d.time[::100],
                     d.sasa_polar[::100], d.sasa_apolar[::100],
                     colors=["#0072B2", "#FF9400"], alpha=0.85, labels=["Polar", "Apolar"])
axes[1, 1].set(xlabel="Time (ns)", ylabel="SASA (nm$^2$)")
axes[1, 1].legend(loc="upper right", fontsize=7)
for ax in axes.flat: beautify(ax)
panel_labels(fig, axes)
save_fig(fig, "fig_rg_sasa")
```

### hbond — H-bond stability `id: hbond`

```python
# INPUT : DataFrame hb, columns: time(ns), n_hbonds(int)  (or per-pair occupancy table)
# OUTPUT: fig_hbond.png/svg (2 panels: series + histogram)
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, beautify, panel_labels

use_style("journal")
fig, axes = plt.subplots(1, 2, figsize=journal_size("onehalf", 0.5))
axes[0].plot(hb.time, hb.n_hbonds, c="#0072B2", lw=0.5, alpha=0.4)
axes[0].plot(hb.time, hb.n_hbonds.rolling(100, min_periods=1).mean(), c="#0072B2", lw=1.6)
axes[0].set(xlabel="Time (ns)", ylabel="H-bonds (protein-ligand)")
axes[1].hist(hb.n_hbonds, bins=range(int(hb.n_hbonds.max()) + 2),
             color="#0072B2", lw=0, align="left")
axes[1].set(xlabel="H-bonds per frame", ylabel="Frames")
for ax in axes: beautify(ax)
panel_labels(fig, axes)
save_fig(fig, "fig_hbond")
```

### dist_ridge — Key distance: series + ridgeline `id: dist_ridge`

```python
# INPUT : dict series {condition: DataFrame(time, dist(nm))} for one key distance
# OUTPUT: fig_dist.png/svg (top: overlaid series; bottom: ridgeline densities)
# DEPENDS: matplotlib, scipy
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, cat_palette, ridge, beautify, panel_labels

use_style("journal")
fig, axes = plt.subplots(2, 1, figsize=journal_size("onehalf", 0.7), sharex=True,
                         gridspec_kw={"height_ratios": [1, 1.2]})
for i, (name, d) in enumerate(series.items()):
    axes[0].plot(d.time, d.dist, c=cat_palette(len(series))[i], lw=0.8, label=name)
axes[0].set(ylabel="Distance (nm)")
axes[0].legend(ncol=len(series), fontsize=7, loc="upper right")
import pandas as pd
long = pd.concat([d.assign(condition=k) for k, d in series.items()])
ridge(long, "dist", "condition", ax=axes[1], overlap=0.9,
      palette=cat_palette(len(series)))
axes[1].set(xlabel="Distance (nm)")
panel_labels(fig, axes)
save_fig(fig, "fig_dist")
```

### fel_2d — 2D free-energy landscape `id: fel_2d`

```python
# INPUT : DataFrame cv, columns: cv1(float), cv2(float)  (e.g. Rg vs RMSD, per frame)
# OUTPUT: fig_fel.png/svg
# DEPENDS: matplotlib, scipy
import matplotlib.pyplot as plt, numpy as np
from scipy.stats import gaussian_kde
from biostyle import use_style, save_fig, journal_size, seq_cmap, add_colorbar

use_style("journal")
k = gaussian_kde(np.vstack([cv.cv1, cv.cv2]))
x1 = np.linspace(cv.cv1.min(), cv.cv1.max(), 160)
x2 = np.linspace(cv.cv2.min(), cv.cv2.max(), 160)
X1, X2 = np.meshgrid(x1, x2)
P = k(np.vstack([X1.ravel(), X2.ravel()])).reshape(X1.shape)
G = -0.0019872041 * 300 * np.log(P + 1e-12)      # kcal/mol at 300 K
G -= G.min()
fig, ax = plt.subplots(figsize=journal_size("single", 0.9))
cf = ax.contourf(X1, X2, G, levels=18, cmap=seq_cmap("mako_r"), extend="max")
cs = ax.contour(X1, X2, G, levels=[1, 2, 3, 5], colors="white", linewidths=0.5)
ax.clabel(cs, fmt="%d", fontsize=6)
mi = np.unravel_index(np.argmin(G), G.shape)
ax.scatter(X1[mi], X2[mi], marker="*", s=90, c="#FF9400", edgecolor="white",
           lw=0.6, zorder=5, label="Global minimum")
ax.legend(loc="upper right")
ax.set(xlabel="CV 1 (e.g. RMSD, nm)", ylabel="CV 2 (e.g. Rg, nm)")
add_colorbar(fig, cf, ax, label="ΔG (kcal/mol)")
save_fig(fig, "fig_fel")
```

Note: KDE-based FEL smooths; state bandwidth/frames in the caption. For
binning-based FEL use `np.histogram2d` + gaussian_filter instead — avoid
interpolation artifacts near sparse regions (mask P below ~5 frames).

### pmf_1d — 1D PMF curves `id: pmf_1d`

```python
# INPUT : dict profiles {method/window: DataFrame(coord, pmf(kcal/mol))}
# OUTPUT: fig_pmf.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
for i, (name, d) in enumerate(profiles.items()):
    ax.plot(d.coord, d.pmf - d.pmf.min(), c=cat_palette(len(profiles))[i], lw=1.6, label=name)
ax.set(xlabel="Reaction coordinate (nm or Å)", ylabel="PMF (kcal/mol)")
ax.legend(); beautify(ax)
save_fig(fig, "fig_pmf")
```

### traj_pca — Trajectory PCA projection `id: traj_pca`

```python
# INPUT : ndarray feats (frames x features, e.g. pairwise distances after alignment)
# OUTPUT: fig_trajpca.png/svg
# DEPENDS: sklearn, matplotlib
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from biostyle import use_style, save_fig, journal_size, seq_cmap, add_colorbar

use_style("journal")
p = PCA(n_components=2).fit(feats)
proj, evr = p.transform(feats), p.explained_variance_ratio_ * 100
fig, ax = plt.subplots(figsize=journal_size("single", 0.9))
import numpy as np
sc = ax.scatter(proj[:, 0], proj[:, 1], c=np.arange(len(proj)), s=4,
                cmap=seq_cmap("rocket"), lw=0, rasterized=True)
ax.set(xlabel=f"PC1 ({evr[0]:.0f}%)", ylabel=f"PC2 ({evr[1]:.0f}%)")
add_colorbar(fig, sc, ax, label="Frame (time)")
save_fig(fig, "fig_trajpca")
```

### contact_map — Residue contact-frequency matrix `id: contact_map`

```python
# INPUT : ndarray F (n_res x n_res, contact frequencies 0-1)
# OUTPUT: fig_contacts_md.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, seq_cmap, add_colorbar

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 1.0))
im = ax.imshow(F, cmap=seq_cmap("mako"), vmin=0, vmax=1, origin="lower")
ax.set(xlabel="Residue i", ylabel="Residue j")
add_colorbar(fig, im, ax, label="Contact frequency")
save_fig(fig, "fig_contacts_md")
```

### dccm — Dynamic cross-correlation matrix `id: dccm`

```python
# INPUT : ndarray C (n_res x n_res, correlations -1..1)
# OUTPUT: fig_dccm.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, div_cmap, add_colorbar

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 1.0))
im = ax.imshow(C, cmap=div_cmap("brand"), vmin=-1, vmax=1, origin="lower")
ax.set(xlabel="Residue i", ylabel="Residue j")
add_colorbar(fig, im, ax, label="C$_{ij}$")
save_fig(fig, "fig_dccm")
```

### ramachandran — Ramachandran density `id: ramachandran`

```python
# INPUT : DataFrame ang, columns: phi(deg), psi(deg)
# OUTPUT: fig_rama.png/svg
# DEPENDS: matplotlib, scipy
import matplotlib.pyplot as plt, numpy as np
from scipy.stats import gaussian_kde
from biostyle import use_style, save_fig, journal_size, seq_cmap

use_style("journal")
k = gaussian_kde(np.vstack([ang.phi, ang.psi]))
X, Y = np.meshgrid(np.linspace(-180, 180, 180), np.linspace(-180, 180, 180))
D = k(np.vstack([X.ravel(), Y.ravel()])).reshape(X.shape)
fig, ax = plt.subplots(figsize=journal_size("single", 1.0))
ax.contourf(X, Y, D, levels=20, cmap=seq_cmap("mako"))
ax.set(xlabel="φ (°)", ylabel="ψ (°)", xticks=[-180, -90, 0, 90, 180],
       yticks=[-180, -90, 0, 90, 180], xlim=(-180, 180), ylim=(-180, 180))
ax.set_aspect("equal")
save_fig(fig, "fig_rama")
```

### mmpbsa_stack — MM-PBSA energy components `id: mmpbsa_stack`

```python
# INPUT : dict comps {term: (mean, sd)} e.g. {"vdW": (-45.2, 3.1), "Electrostatic": (-20.1, 4.0), ...}
# OUTPUT: fig_mmpbsa.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify, grid_axis

use_style("journal")
names = list(comps); means = [comps[n][0] for n in names]; sds = [comps[n][1] for n in names]
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
colors = ["#0072B2" if m < 0 else "#D55E00" for m in means]
ax.bar(names, means, yerr=sds, color=colors, width=0.6, capsize=2.5,
       error_kw=dict(lw=0.9), edgecolor="white", lw=0.5)
ax.axhline(0, c="black", lw=0.8)
ax.set(xlabel="Energy component", ylabel="ΔG$_{bind}$ contribution (kcal/mol)")
beautify(ax); grid_axis(ax, "y", on=False)
save_fig(fig, "fig_mmpbsa")
```

### mmpbsa_residue — Per-residue ΔG waterfall `id: mmpbsa_residue`

```python
# INPUT : DataFrame e, columns: residue(str), dG(float)
# OUTPUT: fig_mmpbsa_res.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, waterfall, beautify, grid_axis

use_style("journal")
d = e.reindex(e.dG.abs().sort_values(ascending=False).index[:15])
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.55))
waterfall(ax, d.dG.to_numpy(), d.residue.tolist())
ax.set(ylabel="Per-residue ΔG$_{bind}$ (kcal/mol)")
beautify(ax); grid_axis(ax, "y", on=False)
save_fig(fig, "fig_mmpbsa_res")
```

### ifp_barcode — Interaction-fingerprint barcode `id: ifp_barcode`

ProLIF-style barcode: one row per residue-interaction pair, one column per
frame — shows exactly when each contact lives during the trajectory. The
protein-ligand stability figure of record for MD.

```python
# INPUT : DataFrame ifp, rows=frames, columns=residue pairs (e.g. "ASP352.B_HBD"),
#         values bool/0-1 (contact present). Build with proLIF:
#         fp = prolif.Fingerprint(); fp.run(traj, lig); df = fp.to_dataframe()
# OUTPUT: fig_ifp_barcode.png/svg
# DEPENDS: matplotlib (proLIF optional for computing the table)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
INTERACTION_COLORS = {"Hydrophobic": "#E9ED4C", "HBDonor": "#0279EE",
                      "HBAcceptor": "#FF9400", "PiStacking": "#FD9BED",
                      "Cationic": "#D55E00", "VdWContact": "#9FB8CE"}
fig, ax = plt.subplots(figsize=journal_size("onehalf", 1.0))
for i, col in enumerate(ifp.columns):
    kind = col.rsplit("_", 1)[-1]
    frames = np.where(ifp[col].to_numpy(dtype=bool))[0]
    ax.scatter(frames, np.full(len(frames), i), marker="s", s=1.6,
               c=INTERACTION_COLORS.get(kind, "#999999"), lw=0, rasterized=True)
ax.set_yticks(range(len(ifp.columns)), ifp.columns, fontsize=6)
ax.set(xlabel="Frame (time)", ylabel="Residue – interaction")
ax.invert_yaxis()
handles = [mpatches.Patch(color=c, label=k) for k, c in INTERACTION_COLORS.items()]
ax.legend(handles=handles, fontsize=6, ncol=2, loc="lower right")
beautify(ax); ax.grid(False)
save_fig(fig, "fig_ifp_barcode")
```

If proLIF is installable (`uv pip install prolif`), prefer computing the
fingerprint table with it and rendering the barcode with the template
above; its `Barcode.display()` and `LigNetwork` diagrams are the reference
implementations for this figure family.

### convergence — Block-average convergence check `id: convergence`

```python
# INPUT : ndarray x (time series, e.g. RMSD or dG per frame)
# OUTPUT: fig_convergence.png/svg (running mean ± block SEM vs time)
# DEPENDS: matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
n = len(x); blocks = np.array_split(x, 10)
run_mean = np.cumsum(x) / np.arange(1, n + 1)
fig, ax = plt.subplots(figsize=journal_size("single", 0.6))
ax.plot(np.arange(1, n + 1) / n * 100, run_mean, c="#0072B2", lw=1.4)
block_sem = np.std([b.mean() for b in blocks]) / np.sqrt(len(blocks))
ax.axhspan(run_mean[-1] - 2 * block_sem, run_mean[-1] + 2 * block_sem,
           color="#FF9400", alpha=0.25, lw=0)
ax.set(xlabel="Simulation progress (%)", ylabel="Running mean")
beautify(ax)
save_fig(fig, "fig_convergence")
```

### rmsd_2d — Pairwise 2D-RMSD matrix `id: rmsd_2d`

Frame × frame pairwise RMSD heatmap (MDAnalysis `DistanceMatrix` pattern):
diagonal blocks of low RMSD = conformational states; off-diagonal blocks =
state revisits. The convergence view that 1D RMSD cannot give. State the
alignment selection and frame count in the caption.

```python
# INPUT : ndarray D (n_frames x n_frames pairwise RMSD, Å, time-ordered)
# OUTPUT: fig_rmsd_2d.png/svg
# DEPENDS: matplotlib, numpy
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, seq_cmap, add_colorbar

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 0.9))
im = ax.imshow(D, cmap=seq_cmap("mako"), origin="lower", rasterized=True,
               extent=[0, D.shape[0], 0, D.shape[0]])
ax.set(xlabel="Frame (time-ordered)", ylabel="Frame", xticks=[], yticks=[])
add_colorbar(fig, im, ax, label="Pairwise RMSD (Å)")
save_fig(fig, "fig_rmsd_2d")
```

### state_occupancy — State-occupancy stacked area `id: state_occupancy`

Fractional occupancy of pre-defined conformational states (from clustering
or CV thresholds) over time, stacked to 1. Shows transitions and
re-equilibration; keep ≤5 states or the stack becomes unreadable.

```python
# INPUT : DataFrame occ (index=time bins, columns=state names, values=fraction)
# OUTPUT: fig_state_occ.png/svg
# DEPENDS: matplotlib, numpy
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
pal = cat_palette(occ.shape[1])
fig, ax = plt.subplots(figsize=journal_size("double", 0.45))
ax.stackplot(occ.index.to_numpy(),
             [occ[c].to_numpy() for c in occ.columns],
             labels=occ.columns, colors=pal, alpha=0.9, lw=0)
ax.set(xlabel="Time (ns)", ylabel="State occupancy (fraction)", ylim=(0, 1))
ax.legend(ncols=min(4, occ.shape[1]), fontsize=7, loc="upper center",
          bbox_to_anchor=(0.5, -0.22), frameon=False)
beautify(ax)
save_fig(fig, "fig_state_occ")
```

---

## Beauty checklist (MD)

- Always show raw series faintly + rolling mean boldly; state window length.
- Multi-system overlays: consistent colors per system across every figure of
  the deliverable.
- FEL: state temperature, CV definitions, frames, and smoothing method;
  mask low-density regions instead of extrapolating.
- DCCM/diverging maps: fix vmin/vmax to ±1 (or ±max) and say so.
- Secondary-structure bands behind RMSF make helices/sheets readable.

## Common pitfalls

- Reading convergence off raw RMSD noise — use running means and block SEM.
- FEL from KDE in sparse regions produces fake minima; mask low-count bins.
- Comparing MM-PBSA absolute values across different force fields/protocols.
- Forgetting to state equilibration exclusion (e.g. "first 10 ns discarded").
