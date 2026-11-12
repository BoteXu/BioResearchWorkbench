"""biostyle — publication-grade plotting style engine for scientific figures.

One import gives every figure a consistent, journal-quality look:

    from biostyle import use_style, save_fig, journal_size, PALETTE
    use_style("journal")                      # journal | poster | dark | minimal
    fig, ax = plt.subplots(figsize=journal_size("single", aspect=0.8))
    ...
    save_fig(fig, "fig1_volcano")             # -> fig1_volcano.png + .svg (editable text)

Design rules baked in
---------------------
- Colorblind-safe categorical palettes (Okabe-Ito derived); no rainbow/jet.
- Perceptually-uniform sequential maps (mako/rocket/viridis) and a balanced
  brand diverging map (blue <-> white <-> orange).
- Clean spines (top/right off), outward ticks, subtle grids, Liberation Sans.
- SVG text stays editable (svg.fonttype="none"); PNG at 300 dpi.
- Journal column widths: single 89 mm, 1.5-column 120 mm, double 183 mm.

Theme variants
--------------
journal  : default for manuscripts; 8-9 pt type, restrained grid.
poster   : larger type and thicker lines for talks/posters.
dark     : dark background, light text, for slide decks.
minimal  : no grid, maximum whitespace.

This module is intentionally dependency-light: numpy/matplotlib required,
seaborn/plotly optional (used only by the helpers that need them).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, to_rgb

__all__ = [
    "use_style", "current_theme", "journal_size", "save_fig",
    "PALETTE", "PHYLO", "OKABE_ITO", "SEQ_CMAPS", "DIV_CMAPS",
    "cat_palette", "seq_cmap", "div_cmap", "brand_div_cmap",
    "beautify", "grid_axis", "panel_labels", "sig_bracket", "sig_pairs",
    "ridge", "raincloud", "waterfall", "add_colorbar", "plotly_template",
    "upset_plot",
    "load_project_theme", "record_provenance",
    "results_dir", "set_seed",
]

# --------------------------------------------------------------------------
# Palettes (colorblind-safe; never rainbow/jet)
# --------------------------------------------------------------------------

#: Phylo brand accents (vivid, ordered for data series use).
PHYLO = ["#0279EE", "#FF9400", "#75A025", "#FD9BED", "#E9ED4C", "#7A00E6"]

#: Okabe-Ito: the standard colorblind-safe qualitative palette.
OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#D55E00",
             "#CC79A7", "#56B4E9", "#F0E442", "#999999"]

#: Default categorical palette (Okabe-Ito, black moved last).
PALETTE = ["#0072B2", "#E69F00", "#009E73", "#D55E00",
           "#CC79A7", "#56B4E9", "#F0E442", "#999999"]

#: Names accepted by :func:`seq_cmap` (perceptually uniform, CVD-safe).
SEQ_CMAPS = ("mako", "rocket", "viridis", "flare", "crest", "bone_r")

#: Names accepted by :func:`div_cmap` (balanced diverging maps).
DIV_CMAPS = ("brand", "vlag", "icefire", "Spectral_r")

_BRAND_DIV = ["#0279EE", "#7FB6F2", "#FAF9F3", "#FFC466", "#FF9400"]


def cat_palette(n: int, style: str = "okabe") -> list[str]:
    """Return ``n`` categorical colors, cycling if needed.

    style: "okabe" (default, colorblind-safe) or "phylo" (brand accents).
    """
    base = OKABE_ITO if style == "okabe" else PHYLO
    return [base[i % len(base)] for i in range(n)]


def seq_cmap(name: str = "mako"):
    """Perceptually-uniform sequential colormap by name (see SEQ_CMAPS)."""
    try:
        import seaborn as sns  # optional
        return sns.color_palette(name, as_cmap=True)
    except Exception:
        return plt.get_cmap("viridis" if name not in ("mako", "rocket",
                                                      "flare", "crest")
                            else "viridis")


def brand_div_cmap():
    """Balanced blue<->white<->orange diverging map (brand, CVD-safe)."""
    return LinearSegmentedColormap.from_list("biostyle_brand", _BRAND_DIV)


def div_cmap(name: str = "brand"):
    """Diverging colormap by name (see DIV_CMAPS)."""
    if name == "brand":
        return brand_div_cmap()
    try:
        import seaborn as sns  # optional
        return sns.color_palette(name, as_cmap=True)
    except Exception:
        return plt.get_cmap("RdBu_r")


# --------------------------------------------------------------------------
# Themes
# --------------------------------------------------------------------------

_THEMES = ("journal", "poster", "dark", "minimal")
_current = {"theme": None}

_FONT_STACK = ["Liberation Sans", "Arimo", "Helvetica", "Arial", "DejaVu Sans"]


def use_style(theme: str = "journal", font_scale: float = 1.0) -> str:
    """Apply a biostyle theme globally. Returns the theme applied.

    Call once per notebook/script session, before creating figures.
    ``font_scale`` multiplies every font size (e.g. 1.25 for a 2-panel
    composite that will be printed small).
    """
    if theme not in _THEMES:
        raise ValueError(f"theme must be one of {_THEMES}, got {theme!r}")

    dark = theme == "dark"
    base = 9.0 if theme == "journal" else 12.0 if theme == "poster" else 10.0
    base *= font_scale
    ink = "#FAF9F3" if dark else "#1A1A1A"
    bg = "#1E1E24" if dark else "white"
    grid = "#B9C4CF" if not dark else "#4A4A55"
    try:  # register seaborn's perceptual maps so rcParams can use them by name
        import seaborn as sns
        from matplotlib import colormaps as _cms
        if "mako" not in _cms:
            _cms.register(sns.color_palette("mako", as_cmap=True), name="mako")
        image_cmap = "mako"
    except Exception:
        image_cmap = "viridis"

    mpl.rcParams.update({
        # typography
        "font.family": "sans-serif",
        "font.sans-serif": _FONT_STACK,
        "font.size": base,
        "axes.labelsize": base,
        "axes.labelweight": "medium",
        "axes.titlesize": base + 1,
        "axes.titleweight": "semibold" if theme != "minimal" else "normal",
        "xtick.labelsize": base - 1,
        "ytick.labelsize": base - 1,
        "legend.fontsize": base - 1,
        "legend.title_fontsize": base - 1,
        # figure
        "figure.facecolor": bg,
        "axes.facecolor": bg,
        "savefig.facecolor": bg,
        "figure.dpi": 110,
        "savefig.dpi": 300,
        # axes & spines
        "axes.edgecolor": ink,
        "axes.linewidth": 0.8,
        "axes.labelcolor": ink,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": theme != "minimal",
        "axes.grid": theme not in ("minimal",),
        "axes.grid.axis": "y",
        # ticks
        "xtick.color": ink,
        "ytick.color": ink,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 3.0,
        "xtick.major.width": 0.8,
        "ytick.major.size": 3.0,
        "ytick.major.width": 0.8,
        "xtick.minor.size": 1.8,
        "ytick.minor.size": 1.8,
        # grid
        "grid.color": grid,
        "grid.linestyle": "-",
        "grid.linewidth": 0.5,
        "grid.alpha": 0.35 if theme == "journal" else 0.5,
        # legend
        "legend.frameon": False,
        "legend.handlelength": 1.2,
        "legend.handletextpad": 0.5,
        "legend.borderaxespad": 0.2,
        # lines / marks
        "lines.linewidth": 1.6,
        "lines.markersize": 5.0,
        "lines.markeredgewidth": 0.0,
        # output
        "savefig.bbox": None,
        "savefig.pad_inches": 0.05,
        "svg.fonttype": "none",   # keep SVG text editable
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        # color cycle
        "axes.prop_cycle": mpl.cycler(color=PALETTE),
        "image.cmap": image_cmap,
    })
    _current["theme"] = theme
    return theme


def current_theme() -> str:
    """Theme last applied by :func:`use_style` (None if never called)."""
    return _current["theme"]


# --------------------------------------------------------------------------
# Sizes & output
# --------------------------------------------------------------------------

#: Journal column widths in inches (89 mm / 120 mm / 183 mm).
COLUMN_IN = {"single": 3.50, "onehalf": 4.73, "double": 7.20}


def journal_size(width: str = "single", aspect: float = 0.75) -> tuple[float, float]:
    """Figure size in inches for a journal column width.

    width: "single" (89 mm), "onehalf" (120 mm) or "double" (183 mm).
    aspect: height / width (0.75 ~ 4:3, 0.62 ~ golden section).
    """
    if width not in COLUMN_IN:
        raise ValueError(f"width must be one of {tuple(COLUMN_IN)}, got {width!r}")
    w = COLUMN_IN[width]
    return (w, w * aspect)


def results_dir(subdir: str | None = None) -> Path:
    """Directory where figures are written.

    Uses ``$BIOMNI_RESULTS`` when set (platform convention), else ``./figures``.
    """
    root = Path(os.environ.get("BIOMNI_RESULTS", "figures"))
    out = root / subdir if subdir else root
    out.mkdir(parents=True, exist_ok=True)
    return out


def save_fig(fig, name: str, subdir: str | None = None,
             formats: tuple = ("png", "svg"), dpi: int | None = None,
             close: bool = False) -> list[str]:
    """Save a figure as PNG (+300 dpi) and SVG (editable text); return paths.

    ``name`` is a file stem without extension. Existing files are overwritten
    only under versioned names the caller chooses (e.g. ``fig1_v2``).
    """
    outdir = results_dir(subdir)
    written = []
    for ext in formats:
        path = outdir / f"{name}.{ext}"
        fig.savefig(path, dpi=dpi or mpl.rcParams["savefig.dpi"])
        written.append(str(path))
    if close:
        plt.close(fig)
    return written


# --------------------------------------------------------------------------
# Axes cosmetics
# --------------------------------------------------------------------------

def beautify(ax, despine: bool = True, grid: bool | None = None) -> None:
    """Apply final polish to an axes: spines, tick sizes, optional grid."""
    if despine:
        ax.spines[["top", "right"]].set_visible(False)
    if grid is not None:
        ax.grid(grid)
    ax.tick_params(length=3, width=0.8)


def grid_axis(ax, axis: str = "y", on: bool = True) -> None:
    """Restrict grid to one axis (y for bar/box, x for horizontal bars)."""
    ax.grid(on, axis=axis)
    ax.set_axisbelow(True)
    if on and axis == "y":
        ax.grid(False, axis="x")
    elif on and axis == "x":
        ax.grid(False, axis="y")


def panel_labels(fig, axes=None, labels=None, x: float = -0.14, y: float = 1.06,
                 size: float | None = None, weight: str = "bold") -> None:
    """Add bold panel tags (a, b, c, ...) to axes of a composite figure.

    ``axes``: list of Axes (defaults to fig.axes). ``labels``: override the
    default lowercase sequence. x/y are axes-fraction offsets.
    """
    axes = axes if axes is not None else list(fig.axes)
    if hasattr(axes, "ravel"):            # flatten 2D axes arrays from subplots
        axes = axes.ravel()
    axes = list(axes)
    labels = labels if labels is not None else list("abcdefghij")[:len(axes)]
    size = size or mpl.rcParams["font.size"] + 2
    for ax, lab in zip(axes, labels):
        ax.text(x, y, lab, transform=ax.transAxes, fontsize=size,
                fontweight=weight, va="bottom", ha="right")


def sig_bracket(ax, x1: float, x2: float, y: float, h: float, text: str,
                lw: float = 1.0) -> None:
    """Draw one significance bracket with a centered label.

    (x1, x2) are the two category positions, y the bracket height,
    h the stub height, text e.g. "ns", "*", "**", "***".
    """
    ax.plot([x1, x1, x2, x2], [y, y + h, y + h, y], lw=lw, c="black")
    ax.text((x1 + x2) / 2, y + h, text, ha="center", va="bottom")


def sig_pairs(ax, positions: dict, pairs: list, pvals: list,
              y_start: float, step: float, h: float = 0.02) -> None:
    """Stack several brackets above categories.

    positions: {category: x}; pairs: [(cat_a, cat_b), ...];
    pvals: matching list of floats (converted to stars);
    y_start/step: base height and increment per bracket (data units).
    """
    def stars(p):
        return "****" if p < 1e-4 else "***" if p < 1e-3 else \
               "**" if p < 1e-2 else "*" if p < 0.05 else "ns"
    span = ax.get_ylim()[1] - ax.get_ylim()[0]
    for i, ((a, b), p) in enumerate(zip(pairs, pvals)):
        sig_bracket(ax, positions[a], positions[b],
                    y_start + i * step, h * span, stars(p))


# --------------------------------------------------------------------------
# Composite plot helpers
# --------------------------------------------------------------------------

def ridge(df, value_col: str, group_col: str, order=None, overlap: float = 0.9,
          palette=None, ax=None, fill_alpha: float = 0.85):
    """Ridgeline plot: stacked KDEs per group (distributions that share x).

    df: long-format DataFrame; overlap in [0, 1] controls stacking density.
    Returns (fig, ax). Requires scipy.
    """
    from scipy.stats import gaussian_kde

    ax = ax or plt.gca()
    groups = order or list(df[group_col].unique())
    palette = palette or cat_palette(len(groups))
    data = [df.loc[df[group_col] == g, value_col].to_numpy() for g in groups]
    xs = np.linspace(min(d.min() for d in data), max(d.max() for d in data), 240)
    dens = [gaussian_kde(d)(xs) for d in data]
    step = overlap * max(d.max() for d in dens)
    for i, (g, d) in enumerate(zip(groups, dens)):
        y0 = i * step
        ax.fill_between(xs, y0, y0 + d, color=palette[i], alpha=fill_alpha, lw=0)
        ax.plot(xs, y0 + d, color="white" if _current["theme"] == "dark"
                else "#333333", lw=0.8)
        ax.text(xs[0], y0 + d.max() * 0.5, str(g), ha="right", va="center",
                fontsize=mpl.rcParams["font.size"] - 1)
    ax.set_yticks([])
    ax.spines[["top", "right", "left"]].set_visible(False)
    return ax


def waterfall(ax, values, labels=None, color_up: str = "#009E73",
              color_down: str = "#D55E00", connector: bool = True):
    """Waterfall (bridge) chart for sequential contributions, e.g. per-residue
    binding-energy decomposition. ``values``: signed contributions in order."""
    vals = np.asarray(values, dtype=float)
    labels = labels or [str(i) for i in range(len(vals))]
    starts = np.concatenate([[0.0], np.cumsum(vals)[:-1]])
    colors = [color_up if v >= 0 else color_down for v in vals]
    ax.bar(range(len(vals)), vals, bottom=starts, color=colors, width=0.72,
           edgecolor="white", linewidth=0.4)
    if connector:
        run = np.concatenate([[0.0], np.cumsum(vals)])
        ax.step(np.arange(len(vals) + 1), run, where="mid",
                color="#666666", lw=0.7, alpha=0.8)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(range(len(vals)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    return ax


def add_colorbar(fig, mappable, ax, label: str = "", fraction: float = 0.035,
                 pad: float = 0.02, outline: bool = False):
    """Slim, labeled colorbar attached to ``ax`` (right side)."""
    cbar = fig.colorbar(mappable, ax=ax, fraction=fraction, pad=pad)
    cbar.ax.tick_params(length=2.5, width=0.7, labelsize=mpl.rcParams["font.size"] - 1)
    cbar.outline.set_visible(outline)
    if label:
        cbar.set_label(label)
    return cbar


def raincloud(df, value_col: str, group_col: str, order=None, palette=None,
              ax=None, jitter: float = 0.08, cloud_width: float = 0.9,
              box_width: float = 0.12, seed: int = 0):
    """Raincloud plot: half-KDE cloud + raw jittered rain + thin box.

    Shows the full distribution, every observation, and robust summary stats
    in one panel (Allen et al. style). Vertical orientation: groups on x.
    Returns (fig, ax). Requires scipy.
    """
    from scipy.stats import gaussian_kde

    rng = np.random.default_rng(seed)
    ax = ax or plt.gca()
    groups = order or sorted(df[group_col].unique(), key=str)
    palette = palette or cat_palette(len(groups))
    for i, (g, c) in enumerate(zip(groups, palette)):
        d = df.loc[df[group_col] == g, value_col].to_numpy()
        kde = gaussian_kde(d)
        y = np.linspace(d.min(), d.max(), 160)
        dens = kde(y)
        dens = dens / dens.max() * cloud_width
        ax.fill_betweenx(y, i, i + dens, color=c, alpha=0.75, lw=0)  # cloud
        ax.plot(i + dens, y, color=c, lw=0.8)
        rain = i - cloud_width * 0.25 - np.abs(rng.normal(0, jitter, len(d)))
        ax.scatter(rain, d, s=4, c=c, alpha=0.5, lw=0, zorder=2)      # rain
        bp = ax.boxplot(d, positions=(i,), widths=(box_width,), vert=True,
                        showfliers=False, showcaps=False,
                        medianprops=dict(color="#1A1A1A", lw=1.4),
                        boxprops=dict(color="#1A1A1A", lw=1.0),
                        whiskerprops=dict(color="#1A1A1A", lw=1.0), zorder=3)
    ax.set_xticks(range(len(groups)), [str(g) for g in groups])
    ax.set_xlim(-cloud_width * 0.6 - 0.3, len(groups) - 1 + cloud_width + 0.3)
    beautify(ax)
    return ax


# --------------------------------------------------------------------------
# Project theming & provenance (traceability)
# --------------------------------------------------------------------------

def load_project_theme(path: str | os.PathLike) -> dict:
    """Apply a project theme JSON: identity->color mapping, palette, font.

    Expected keys (all optional): ``identity_colors`` (dict label->hex),
    ``categorical`` (list of hex), ``sequential`` / ``diverging`` (names),
    ``font`` (family name). Returns the parsed theme. Apply after
    :func:`use_style` so every figure of one project shares identity colors.
    """
    theme = json.loads(Path(path).read_text())
    if "categorical" in theme and theme["categorical"]:
        PALETTE[:] = theme["categorical"]
        mpl.rcParams["axes.prop_cycle"] = mpl.cycler(color=PALETTE)
    if theme.get("font"):
        mpl.rcParams["font.sans-serif"] = [theme["font"], *_FONT_STACK]
    if theme.get("sequential"):
        mpl.rcParams["image.cmap"] = theme["sequential"]
    return theme


def identity_colors(theme: dict, labels) -> dict:
    """Color mapping for labels from a project theme (falls back to palette)."""
    fixed = theme.get("identity_colors", {})
    labels = list(labels)
    auto = {l: c for l, c in zip(labels, cat_palette(len(labels)))
            if l not in fixed}
    return {**auto, **fixed}


def record_provenance(name: str, inputs: dict, params: dict,
                      outputs: list[str], subdir: str | None = None) -> str:
    """Write a JSON sidecar recording what produced a figure (traceability).

    inputs: {role: path}; params: plotting parameters; outputs: written file
    paths (hashed). Status is recorded as ``RENDERED_UNREVIEWED`` — visual
    review is a separate, human step. Returns the sidecar path.
    """
    import datetime
    import hashlib

    def digest(p):
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()

    record = {
        "figure": name,
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "status": "RENDERED_UNREVIEWED",
        "inputs": {k: {"path": str(v), "sha256": digest(v)}
                   for k, v in inputs.items()},
        "params": params,
        "outputs": [{"path": p, "sha256": digest(p)} for p in outputs],
    }
    sidecar = results_dir(subdir) / f"{name}.provenance.json"
    sidecar.write_text(json.dumps(record, indent=1, ensure_ascii=False))
    return str(sidecar)


# --------------------------------------------------------------------------
# plotly bridge (interactive layer)
# --------------------------------------------------------------------------

def plotly_template(theme: str | None = None):
    """Return a plotly layout dict matching biostyle's static look.

    Usage: ``fig.update_layout(**plotly_template())``.
    Requires plotly only in the calling session.
    """
    theme = theme or _current["theme"] or "journal"
    dark = theme == "dark"
    base = 9 if theme == "journal" else 12 if theme == "poster" else 10
    ink = "#FAF9F3" if dark else "#1A1A1A"
    grid = "#4A4A55" if dark else "#D8DEE4"
    return {
        "font": {"family": "Liberation Sans, Arimo, Arial, sans-serif",
                 "size": base + 2, "color": ink},
        "paper_bgcolor": "#1E1E24" if dark else "white",
        "plot_bgcolor": "#1E1E24" if dark else "white",
        "colorway": PALETTE,
        "margin": {"l": 56, "r": 24, "t": 44, "b": 48},
        "title": {"font": {"size": base + 4}},
        "xaxis": {"gridcolor": grid, "zerolinecolor": grid,
                  "linecolor": ink, "ticks": "outside",
                  "tickcolor": ink, "showline": True},
        "yaxis": {"gridcolor": grid, "zerolinecolor": grid,
                  "linecolor": ink, "ticks": "outside",
                  "tickcolor": ink, "showline": True},
        "legend": {"bgcolor": "rgba(0,0,0,0)", "borderwidth": 0},
        "hoverlabel": {"font_size": base + 1},
    }


def upset_plot(sets: dict, ax: plt.Axes | None = None, max_shown: int = 20,
               dot_color: str = "#1A1A1A") -> tuple[plt.Figure, plt.Axes]:
    """Minimal UpSet plot (Lex et al. 2014): intersection bars + matrix.

    Zero-dependency fallback for the `upsetplot` package (incompatible with
    pandas >= 3 copy-on-write). Vertical layout: intersection-size bars on
    top, membership matrix below, set-size bars on the right.
    Returns (fig, ax).
    """
    names = list(sets)
    sets = {k: set(map(str, v)) for k, v in sets.items()}
    members: dict[str, set] = {}
    for n, s in sets.items():
        for m in s:
            members.setdefault(m, set()).add(n)
    patterns: dict[tuple, int] = {}
    for m, ns in members.items():
        key = tuple(1 if n in ns else 0 for n in names)
        patterns[key] = patterns.get(key, 0) + 1
    pats = sorted(patterns.items(), key=lambda kv: -kv[1])[:max_shown]
    counts = [c for _, c in pats]

    fig = ax.figure if ax is not None else plt.figure(
        figsize=journal_size("double", 0.5))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 2.2], width_ratios=[4, 1],
                          hspace=0.06, wspace=0.04)
    ax_b = fig.add_subplot(gs[0, 0])
    ax_b.bar(range(len(pats)), counts, color="#526272", width=0.68)
    ax_b.set_ylabel("Intersection size")
    ax_b.set_xticks([])
    ax_b.set_xlim(-0.6, len(pats) - 0.4)
    beautify(ax_b)
    ax_m = fig.add_subplot(gs[1, 0])
    for j, (pat, _) in enumerate(pats):
        on = [i for i, b in enumerate(pat) if b]
        if len(on) > 1:  # connector line across the membership dots
            ax_m.plot([j] * len(on), on, c=dot_color, lw=1.0, zorder=2)
        ax_m.scatter([j] * len(pat), range(len(pat)),
                     c=[dot_color if b else "#E4E7EA" for b in pat],
                     s=26, lw=0, zorder=3)
    ax_m.set_yticks(range(len(names)), names, fontsize=8)
    ax_m.set_xticks([])
    ax_m.set_xlim(-0.6, len(pats) - 0.4)
    ax_m.invert_yaxis()
    beautify(ax_m)
    ax_s = fig.add_subplot(gs[1, 1], sharey=ax_m)
    set_sizes = [len(sets[n]) for n in names]
    ax_s.barh(range(len(names)), set_sizes, color="#9AA5AE", height=0.68)
    ax_s.set_xlabel("Set size")
    ax_s.tick_params(labelsize=7)
    beautify(ax_s)
    return fig, ax_m


def set_seed(seed: int = 0) -> None:
    """Seed numpy's global RNG (convenience for reproducible demo layouts)."""
    np.random.seed(seed)


# v2: one shared controlled-layout implementation (QC re-exports this module).
# Legacy helper names remain available; these corrected public APIs take priority.
from design_system import (use_style, journal_size, cat_palette, identity_colors,
                           sig_pairs, safe_save, PALETTES, choose_grid, wrap_label)

def current_theme():
    from design_system import _STYLE_STATE
    return _STYLE_STATE['theme']

def save_fig(fig, name, subdir=None, formats=("png", "svg"), dpi=None,
             close=False, overwrite=False):
    if subdir is not None:
        p = Path(subdir)
        if p.is_absolute() or '..' in p.parts:
            raise ValueError('subdir must stay beneath BIOMNI_RESULTS')
    written = safe_save(fig, name, results_dir(subdir), formats, dpi or 300, overwrite)
    if close: plt.close(fig)
    return written

__all__ += ['identity_colors', 'PALETTES', 'choose_grid', 'wrap_label', 'safe_save']
