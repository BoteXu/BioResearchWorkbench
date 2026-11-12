> Legacy reference preserved. For current result-only calls and tested contracts, read [v2 API](v2-api.md). These original examples may include analysis or placeholder assembly and do not constitute current runtime acceptance.

# Molecular Docking Figures

Docking and virtual-screening visualization: affinity comparisons, 2D
interaction diagrams, 3D poses, validation against experiment. Data
typically: docking score tables (ligand × pose/conformation), PDB/SDF/MOL2
files, per-residue interaction or energy tables, experimental affinity
(IC50/Ki) for validation.

## Catalog

| Question | Figure | Data input | Language | Template id |
|---|---|---|---|---|
| Which ligand binds best? | Affinity bars with error bars | score table | py | `affinity_bar` |
| Score spread across poses | Score violin/box | score table | py | `score_violin` |
| How does the ligand bind? | 2D interaction diagram | SDF/MOL of complex | py | `interaction_2d` |
| What does the pose look like? | 3D pose grid snapshots | PDB complex | py | `pose_grid_3d` |
| Which conformation for which ligand? | Score heatmap (conf × ligand) | score matrix | py | `score_heatmap` |
| Does docking reproduce affinity? | Validation scatter (R²) | predicted vs experimental | py | `validation_scatter` |
| Which residues are contacted? | Contact-frequency heatmap | contact table | py | `contact_freq` |
| Which residues contribute energy? | Per-residue decomposition waterfall | energy table | py | `res_contrib` |
| Pose families? | RMSD clustering heatmap | pose-RMSD matrix | py | `pose_rmsd_cluster` |
| Where do hits drop out? | Virtual-screening funnel | stage counts | py | `vs_funnel` |
| Is potency explained by size? | Ligand-efficiency comparison | score + heavy atoms | py | `ligand_efficiency` |
| Which ligand wins across methods? | Consensus rank heatmap | ligand × method rank matrix | py | `consensus_rank` |
| When do contacts persist in MD? | IFP barcode (see MD reference) | interaction fingerprint table | py | `ifp_barcode` (molecular-dynamics.md) |

---

### affinity_bar — Affinity comparison with error bars `id: affinity_bar`

```python
# INPUT : DataFrame sc, columns: ligand(str), affinity(float, kcal/mol or pKd), sem(float, optional)
# OUTPUT: fig_affinity.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, beautify, grid_axis

use_style("journal")
d = sc.groupby("ligand").affinity.agg(["mean", "sem"]).sort_values("mean")
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
ax.bar(range(len(d)), d["mean"], yerr=d["sem"].fillna(0), width=0.66,
       color=["#0072B2" if v == d["mean"].min() else "#9FB8CE" for v in d["mean"]],
       edgecolor="white", lw=0.5, capsize=2, error_kw=dict(lw=0.9))
ax.set_xticks(range(len(d)), d.index, rotation=45, ha="right", fontsize=7)
ax.set(xlabel="Ligand", ylabel="Docking affinity (kcal/mol)")
best = d["mean"].min()
ax.axhline(best, c="#D55E00", lw=0.8, ls=":")
beautify(ax); grid_axis(ax, "y", on=False)
save_fig(fig, "fig_affinity")
```

### score_violin — Score distribution across poses `id: score_violin`

```python
# INPUT : DataFrame sc, columns: ligand(str), pose(int), affinity(float)
# OUTPUT: fig_score_violin.png/svg
# DEPENDS: matplotlib, seaborn
import matplotlib.pyplot as plt, seaborn as sns
from biostyle import use_style, save_fig, journal_size, beautify, grid_axis

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.6))
sns.violinplot(sc, x="ligand", y="affinity", inner="box", cut=0,
               color="#9FB8CE", linecolor="#33506B", ax=ax)
sns.stripplot(sc, x="ligand", y="affinity", size=2.5, color="#333333",
              alpha=0.5, ax=ax)
ax.set(xlabel="Ligand", ylabel="Affinity (kcal/mol)")
ax.tick_params(axis="x", rotation=45)
beautify(ax); grid_axis(ax, "y", on=False)
save_fig(fig, "fig_score_violin")
```

### interaction_2d — 2D interaction diagram `id: interaction_2d`

```python
# INPUT : SDF/MOL file of the protein-ligand complex (or ligand + residue list)
# OUTPUT: fig_interaction_2d.png/svg
# DEPENDS: rdkit
from rdkit import Chem
from rdkit.Chem import Draw
from rdkit.Chem.Draw import rdMolDraw2D
from biostyle import results_dir

mol = Chem.MolFromMolFile("ligand_in_pocket.mol", removeHs=False)
d = rdMolDraw2D.MolDraw2DCairo(900, 700)
opts = d.drawOptions()
opts.addStereoAnnotation = True
opts.legendFontSize = 22
rdMolDraw2D.PrepareAndDrawMolecule(d, mol)
d.FinishDrawing()
out = results_dir() / "fig_interaction_2d.png"
out.write_bytes(d.GetDrawingText())
```

Note: RDKit draws the ligand; annotate interacting residues by adding
`SetAtomLegend` text or compose the residue-contact list beside the drawing
(see `contact_freq`). For publication 2D interaction maps with residue
wedges, use the offline-capable `prolif` package if installable, else
compose ligand drawing + contact table as two panels.

### pose_grid_3d — 3D pose grid snapshots `id: pose_grid_3d`

```python
# INPUT : PDB file of protein-ligand complex (protein + ligand in same file)
# OUTPUT: fig_poses.png (grid of 4 views) — PNG only (3D render)
# DEPENDS: py3Dmol (uv pip install py3Dmol); fallback: none (skip with note)
import py3Dmol
from biostyle import results_dir

def snapshot(view, spec, w=500, h=500):
    view.zoomTo(); view.setBackgroundColor("white")
    png = view.png(w, h, quiet=True)
    return png

views = [(0, 0), (90, 0), (0, 90), (45, 45)]     # (azimuth, elevation) via rotate
v = py3Dmol.view(width=500, height=500)
v.addModel(open("complex.pdb").read(), "pdb")
v.setStyle({"cartoon": {"color": "#9FB8CE", "opacity": 0.85}})
v.addStyle({"resn": "LIG"}, {"stick": {"colorscheme": "cyanCarbon", "radius": 0.18}})
v.spin(False)
# Render one view per rotation; py3Dmol renders the current camera state.
# Compose the 4 PNGs into a grid with matplotlib:
import matplotlib.pyplot as plt, numpy as np
from PIL import Image
from biostyle import use_style, journal_size, panel_labels
use_style("journal")
fig, axes = plt.subplots(2, 2, figsize=journal_size("onehalf", 1.0))
for ax, (az, el) in zip(axes.flat, views):
    v2 = py3Dmol.view(width=500, height=500)
    v2.addModel(open("complex.pdb").read(), "pdb")
    v2.setStyle({"cartoon": {"color": "#9FB8CE", "opacity": 0.85}})
    v2.addStyle({"resn": "LIG"}, {"stick": {"colorscheme": "cyanCarbon", "radius": 0.18}})
    v2.rotate(az, axis="y"); v2.rotate(el, axis="x")
    v2.zoomTo()
    img = Image.open(__import__("io").BytesIO(v2.png(500, 500, quiet=True)))
    ax.imshow(img); ax.axis("off")
panel_labels(fig, axes)
fig.savefig(results_dir() / "fig_poses.png", dpi=300, bbox_inches="tight")
```

If py3Dmol is unavailable, say so and offer: (a) install it, or (b) export
the pose as PDB for the user's molecular viewer — do not fake a 3D figure.

### score_heatmap — Conformation × ligand score heatmap `id: score_heatmap`

```python
# INPUT : DataFrame M (index=ligand, columns=receptor conformation, values=affinity)
# OUTPUT: fig_score_heatmap.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, div_cmap, add_colorbar

use_style("journal")
M = M.loc[M.mean(axis=1).sort_values().index]      # order ligands by mean affinity
M = M[M.mean().sort_values().index]                # order conformations by mean
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.8))
im = ax.imshow(M, cmap=div_cmap("brand"), aspect="auto")
ax.set_xticks(range(M.shape[1]), M.columns, rotation=45, ha="right", fontsize=7)
ax.set_yticks(range(M.shape[0]), M.index, fontsize=7)
ax.set(xlabel="Receptor conformation", ylabel="Ligand")
for s in ax.spines.values(): s.set_visible(False)
add_colorbar(fig, im, ax, label="Affinity (kcal/mol)")
save_fig(fig, "fig_score_heatmap")
```

### validation_scatter — Docking vs experimental affinity `id: validation_scatter`

```python
# INPUT : DataFrame val, columns: exp_pkd(float), dock_kcal(float), ligand(str)
# OUTPUT: fig_validation.png/svg
# DEPENDS: matplotlib, scipy
import matplotlib.pyplot as plt, numpy as np
from scipy.stats import pearsonr, spearmanr
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
r, rp = pearsonr(val.exp_pkd, -val.dock_kcal)
rho, _ = spearmanr(val.exp_pkd, -val.dock_kcal)
fig, ax = plt.subplots(figsize=journal_size("single", 0.9))
ax.scatter(val.exp_pkd, -val.dock_kcal, s=30, c="#0072B2",
           edgecolor="white", lw=0.5, zorder=3)
lim = [min(val.exp_pkd.min(), (-val.dock_kcal).min()) - 1,
       max(val.exp_pkd.max(), (-val.dock_kcal).max()) + 1]
ax.plot(lim, lim, c="#999999", lw=0.8, ls="--")
ax.set_xlim(lim); ax.set_ylim(lim)
ax.set(xlabel="Experimental pK$_d$", ylabel="-Docking energy (kcal/mol)")
ax.text(0.04, 0.96, f"Pearson r = {r:.2f}\nSpearman ρ = {rho:.2f}  (n = {len(val)})",
        transform=ax.transAxes, va="top", fontsize=7.5)
beautify(ax)
save_fig(fig, "fig_validation")
```

### contact_freq — Residue × ligand contact heatmap `id: contact_freq`

```python
# INPUT : DataFrame C (index=residue label, columns=ligand, values=contact frequency 0-1)
# OUTPUT: fig_contacts.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, seq_cmap, add_colorbar

use_style("journal")
C = C.loc[C.sum(axis=1).sort_values(ascending=False).index[:30]]   # top residues
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.9))
im = ax.imshow(C, cmap=seq_cmap("rocket"), aspect="auto", vmin=0, vmax=1)
ax.set_xticks(range(C.shape[1]), C.columns, rotation=45, ha="right", fontsize=7)
ax.set_yticks(range(C.shape[0]), C.index, fontsize=6.5)
ax.set(xlabel="Ligand", ylabel="Binding-site residue")
for s in ax.spines.values(): s.set_visible(False)
add_colorbar(fig, im, ax, label="Contact frequency")
save_fig(fig, "fig_contacts")
```

### res_contrib — Per-residue energy waterfall `id: res_contrib`

```python
# INPUT : DataFrame e, columns: residue(str), dG(float, kcal/mol, signed contribution)
# OUTPUT: fig_res_contrib.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, waterfall, beautify, grid_axis

use_style("journal")
d = e.reindex(e.dG.abs().sort_values(ascending=False).index[:15])
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.55))
waterfall(ax, d.dG.to_numpy(), d.residue.tolist())
ax.set(ylabel="ΔG contribution (kcal/mol)")
beautify(ax); grid_axis(ax, "y", on=False)
save_fig(fig, "fig_res_contrib")
```

### pose_rmsd_cluster — Pose RMSD clustering heatmap `id: pose_rmsd_cluster`

```python
# INPUT : ndarray R (n_poses x n_poses, ligand RMSD matrix); list labels
# OUTPUT: fig_pose_cluster.png/svg
# DEPENDS: matplotlib, seaborn
import matplotlib.pyplot as plt, seaborn as sns
from biostyle import use_style, save_fig, journal_size, results_dir

use_style("journal")
g = sns.clustermap(R, cmap="mako", xticklabels=labels, yticklabels=labels,
                   figsize=journal_size("onehalf", 1.0), dendrogram_ratio=0.12,
                   cbar_pos=(0.02, 0.8, 0.03, 0.18))
g.ax_cbar.set_title("RMSD (Å)", fontsize=8)
g.tick_params(labelsize=6)
g.savefig(results_dir() / "fig_pose_cluster.png", dpi=300, bbox_inches="tight")
```

### vs_funnel — Virtual-screening funnel `id: vs_funnel`

```python
# INPUT : dict stages {"Docking": 1_000_000, "Rescoring": 50000, "MM-GBSA": 500, "Manual": 40}
# OUTPUT: fig_funnel.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
names, counts = zip(*stages.items())
widths = np.log10(counts)
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
left = (widths.max() - widths) / 2
ax.barh(range(len(counts)), widths, left=left, height=0.62,
        color=["#0072B2", "#4C93D6", "#8FBCE6", "#D55E00"][:len(counts)],
        edgecolor="white", lw=0.6)
for i, (n, c) in enumerate(zip(names, counts)):
    ax.text(widths.max() / 2, i, f"{n}: {c:,}", ha="center", va="center",
            color="white", fontweight="bold", fontsize=8)
ax.set_yticks(range(len(counts)), [f"Stage {i+1}" for i in range(len(counts))])
ax.invert_yaxis(); ax.set_xticks([])
for s in ax.spines.values(): s.set_visible(False)
save_fig(fig, "fig_funnel")
```

### ligand_efficiency — Ligand-efficiency comparison `id: ligand_efficiency`

```python
# INPUT : DataFrame lig, columns: ligand(str), dock_kcal(float), heavy_atoms(int)
# OUTPUT: fig_le.png/svg (LE = -ΔG / heavy atoms)
# DEPENDS: matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
lig = lig.assign(LE=-lig.dock_kcal / lig.heavy_atoms).sort_values("LE")
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
ax.scatter(lig.heavy_atoms, lig.LE, s=34, c="#0072B2", edgecolor="white", lw=0.5)
for _, r in lig.nlargest(6, "LE").iterrows():
    ax.annotate(r.ligand, (r.heavy_atoms, r.LE), fontsize=7,
                xytext=(4, 3), textcoords="offset points")
ax.axhline(0.3, c="#D55E00", lw=0.8, ls=":")   # classic LE reference
ax.text(ax.get_xlim()[1], 0.3, " LE = 0.3", va="bottom", ha="right", fontsize=7, c="#D55E00")
ax.set(xlabel="Heavy-atom count", ylabel="Ligand efficiency (kcal/mol/atom)")
beautify(ax)
save_fig(fig, "fig_le")
```

### consensus_rank — Consensus rank heatmap `id: consensus_rank`

Ligand × scoring-function rank matrix, rows ordered by mean rank (consensus).
One scoring function mis-ranks; consensus across ≥3 exposes robust hits.
Cell text = rank; row order = the result.

```python
# INPUT : DataFrame ranks (index=ligand, columns=method, values=rank 1=best)
# OUTPUT: fig_consensus.png/svg
# DEPENDS: matplotlib, numpy
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, seq_cmap, add_colorbar

use_style("journal")
R = ranks.loc[ranks.mean(axis=1).sort_values().index]
vmax = R.to_numpy().max()
fig, ax = plt.subplots(figsize=journal_size("single", 1.0))
im = ax.imshow(R.to_numpy(), cmap=seq_cmap("mako").reversed(), aspect="auto",
               vmin=1, vmax=vmax, rasterized=True)
ax.set_xticks(range(R.shape[1]), R.columns, rotation=30, ha="right", fontsize=8)
ax.set_yticks(range(R.shape[0]), R.index, fontsize=7)
for i in range(R.shape[0]):
    for j in range(R.shape[1]):
        v = R.iloc[i, j]
        ax.text(j, i, int(v), ha="center", va="center", fontsize=6,
                color="white" if v < vmax * 0.5 else "#222222")
add_colorbar(fig, im, ax, label="Rank (1 = best)")
save_fig(fig, "fig_consensus")
```

---

## Beauty checklist (docking)

- Affinity sign convention: state kcal/mol (more negative = better) or pK
  (higher = better) on the axis label; never mix.
- Highlight the best ligand/pose in brand blue, keep others muted.
- 3D snapshots: white background, semi-transparent cartoon, ligand in stick
  with colored carbons; 4 canonical views (0/90/180/45°).
- Heatmaps: order rows/columns by mean value or clustering, never raw order.
- Validation scatter: identity line, both correlation coefficients, n.

## Common pitfalls

- Comparing scores across different docking protocols/receptors — only
  compare within one protocol.
- Presenting docking scores as binding free energies; label as "docking
  affinity/score".
- 2D interaction diagrams from RDKit alone lack residue wedges — compose
  with a contact table or use proLIF if installable.
- Funnel plots with linear widths hide early-stage attrition; use log width.
