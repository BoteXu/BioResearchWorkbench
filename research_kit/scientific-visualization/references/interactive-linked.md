> Legacy reference preserved. For current result-only calls and tested contracts, read [v2 API](v2-api.md). These original examples may include analysis or placeholder assembly and do not constitute current runtime acceptance.

# Linked & Interactive Figures

Two kinds of "linkage": **static linkage** (coordinated scales/colors across
panels of one figure) and **interactive linkage** (selections in one view
update another; hover reveals values). Interactive output is a single
self-contained HTML file (plotly, inline data, no CDN) that opens offline.

## When interactive vs static

| Use static (PNG/SVG) | Use interactive (HTML) |
|---|---|
| Publication submission | Data exploration with the user |
| Print/PDF deliverables | Presentations with drill-down questions |
| > ~10k points without rasterization | Linked UMAP ↔ marker exploration |
| Journal column widths | Dashboards with condition toggles |

Deliver interactive files as `<name>.html` in the results directory and say
what can be clicked/hovered. Keep static versions of the same figures for
anything that will be printed.

Templates in this file: `umap-dashboard` (linked UMAP ↔ violin),
`condition-toggle` (metric switch buttons), `pose-3d-html` (3D viewer),
`trajectory-gif` (animation + offline player).

## Static linkage patterns

- **Shared color mapping**: build one `dict` of category → color and pass it
  to every panel (`palette` argument in seaborn, `scale_colour_manual` in R).
- **Shared quantitative scale**: for comparable heatmaps/embeddings fix
  `vmin`/`vmax` (or `zmin`/`zmax`) to the same values and say so in captions.
- **One legend**: draw the legend once (rightmost or top panel), suppress it
  elsewhere (`legend=None` / `show.legend = FALSE`).
- **Aligned panels**: matplotlib `gridspec` height ratios; R patchwork
  `plot_layout(heights=...)`; keep panel widths equal for visual scanning.

## Interactive UMAP dashboard `id: umap-dashboard`

Linked UMAP ↔ per-cluster violin, hover shows cell metadata; buttons switch
the coloring. Single self-contained HTML.

```python
# INPUT : DataFrame df, columns: x, y (embedding), cluster, condition, gene_A, gene_B
# OUTPUT: umap_dashboard.html (self-contained)
# DEPENDS: plotly
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from biostyle import plotly_template, results_dir, PALETTE

clusters = sorted(df.cluster.unique())
colors = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(clusters)}
fig = make_subplots(rows=1, cols=2, column_widths=[0.62, 0.38],
                    subplot_titles=("UMAP", "Expression by cluster"))
for c in clusters:
    d = df[df.cluster == c]
    fig.add_trace(go.Scattergl(x=d.x, y=d.y, mode="markers", name=c,
                               marker=dict(size=3, color=colors[c], opacity=0.85),
                               customdata=d[["condition", "gene_A"]].to_numpy(),
                               hovertemplate="%{customdata[0]} | gene_A %{customdata[1]:.2f}<extra>" + c + "</extra>"),
                  row=1, col=1)
    fig.add_trace(go.Violin(x=d.cluster, y=d.gene_A, name=c, side="positive",
                            marker_color=colors[c], showlegend=False, width=0.9),
                  row=1, col=2)
fig.update_layout(**plotly_template(), height=560,
                  hovermode="closest",
                  updatemenus=[dict(type="buttons", direction="right", x=1.0, y=1.12,
                                    buttons=[dict(label="gene_A", method="update",
                                                  args=[{"y.axis.title": "gene_A"}])])])
fig.write_html(results_dir() / "umap_dashboard.html", include_plotlyjs="inline")
```

Notes: `include_plotlyjs="inline"` embeds the library (~3 MB) so the file
opens offline. `Scattergl` keeps >100k cells responsive. For gene switching,
generate one violin trace per gene and use `updatemenus` visibility toggles
instead of rebuilding the figure.

## Condition-toggle dashboard `id: condition-toggle`

```python
# INPUT : DataFrame df (long format: metric, condition, replicate, value)
# OUTPUT: metric_dashboard.html (buttons switch metric; boxes update)
# DEPENDS: plotly
import plotly.graph_objects as go
from biostyle import plotly_template, results_dir, PALETTE

metrics = df.metric.unique().tolist()
fig = go.Figure()
buttons = []
for mi, metric in enumerate(metrics):
    for ci, cond in enumerate(df.condition.unique()):
        d = df[(df.metric == metric) & (df.condition == cond)]
        fig.add_trace(go.Box(y=d.value, name=cond, marker_color=PALETTE[ci % len(PALETTE)],
                             visible=(mi == 0), legendgroup=cond))
    vis = [t == mi for t in range(len(metrics)) for _ in range(df.condition.nunique())]
    buttons.append(dict(label=metric, method="update",
                        args=[{"visible": vis}]))
fig.update_layout(**plotly_template(), updatemenus=[dict(type="buttons",
                     direction="right", x=0.5, y=1.15, buttons=buttons)],
                  boxmode="group")
fig.write_html(results_dir() / "metric_dashboard.html", include_plotlyjs="inline")
```

## Interactive 3D pose viewer `id: pose-3d-html`

```python
# INPUT : PDB complex file
# OUTPUT: pose_viewer.html (rotatable 3D, self-contained)
# DEPENDS: py3Dmol
import py3Dmol
from biostyle import results_dir

v = py3Dmol.view(width=640, height=480)
v.addModel(open("complex.pdb").read(), "pdb")
v.setStyle({"cartoon": {"color": "#9FB8CE", "opacity": 0.85}})
v.addStyle({"resn": "LIG"}, {"stick": {"colorscheme": "cyanCarbon", "radius": 0.2}})
v.zoomTo()
v.show()
# py3Dmol in a notebook renders interactively; to export standalone HTML,
# render snapshots (pose_grid_3d) or hand the PDB + a one-line viewer page:
html = """<!doctype html><meta charset=utf-8>
<script src="https://3Dmol.org/build/3Dmol-min.js"></script>"""  # NOTE: CDN — see guardrail
```

Guardrail: the skill requires self-contained HTML (no CDN). py3Dmol's
notebook widget cannot be fully inlined; when a standalone rotatable viewer
is required, write a small HTML that embeds the PDB text and uses an
inlined 3Dmol script if the user's environment provides it, or deliver the
static pose grid instead and say why.

## Molecular trajectory animation `id: trajectory-gif`

Key-frame GIF plus an offline HTML player (slider + play/pause) for MD
trajectories or any frame sequence. Fixed camera and coordinate range are
mandatory — the animation must not fake motion by rescaling axes.

```python
# INPUT : list frames of (x, y) arrays (or per-atom coordinates); float dt (ps)
# OUTPUT: traj_anim.gif + traj_player.html (offline)
# DEPENDS: matplotlib (Pillow writer)
import matplotlib.pyplot as plt, numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter
from biostyle import use_style, results_dir, journal_size

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 1.0))
scat = ax.scatter([], [], s=8, c="#0279EE", lw=0)
title = ax.set_title("")
all_xy = np.concatenate(frames)
ax.set(xlim=(all_xy[:, 0].min(), all_xy[:, 0].max()),
       ylim=(all_xy[:, 1].min(), all_xy[:, 1].max()),
       xlabel="x (Å)", ylabel="y (Å)")
def update(i):
    scat.set_offsets(frames[i])
    title.set_text(f"t = {i * dt:.1f} ps")
    return scat, title
anim = FuncAnimation(fig, update, frames=len(frames), interval=80, blit=True)
out = results_dir()
anim.save(out / "traj_anim.gif", writer=PillowWriter(fps=12))
plt.close(fig)

# Offline player: embed the GIF, add slider + play/pause via vanilla JS
player = """<!doctype html><meta charset="utf-8"><title>Trajectory player</title>
<style>body{font-family:sans-serif;margin:2em}img{max-width:100%}</style>
<img src="traj_anim.gif" id="f">
<p><button onclick="f.play()">play</button> <button onclick="f.pause()">pause</button>
<input type="range" min="0" max="100" value="0" oninput="f.currentTime=this.value/100*f.duration">
</p>"""
(out / "traj_player.html").write_text(player)
```

For 3D frame sequences, render each key frame with the `pose_grid_3d`
camera approach first, then assemble the PNGs into the GIF — never rotate
the camera between frames (it fakes motion).

## Beauty checklist (interactive)

- Same palette and fonts as the static figures (`plotly_template()`).
- Hover templates with units; no raw indices.
- Buttons/menus labeled with the user's terms, not column names.
- File opens offline (`include_plotlyjs="inline"`); test by opening it.
- State in the delivery message what is clickable and what it changes.

## Common pitfalls

- Shipping HTML that needs internet (CDN plotly/3Dmol) — violates the
  self-contained rule.
- Interactive figures as the only record: always keep static versions for
  print and review.
- Overloading hover with every column; show 2-3 informative fields.
- Forgetting `Scattergl` for large cell counts (SVG-mode markers lag).
