> Legacy reference preserved. For current result-only calls and tested contracts, read [v2 API](v2-api.md). These original examples may include analysis or placeholder assembly and do not constitute current runtime acceptance.

# External Galleries & Reference Implementations

Curated external resources to consult when a requested figure family needs
deeper patterns than this skill's templates provide. Each entry states what
to borrow. Retrieved 2026-11-09; re-check for version changes before
relying on API details.

## Cross-domain style

- **SciencePlots** (github.com/garrettj403/SciencePlots) — matplotlib
  style sheets for `science`, `nature`, `ieee`. Borrow: journal-specific
  variants (IEEE = B&W-readable, 600 dpi, single-column width; Nature =
  sans-serif). Our `use_style("journal")` covers the common case; consult
  when a specific journal's conventions are requested.
- **Scientific Visualization: Python + Matplotlib** (github.com/rougier/scientific-visualization-book)
  — Nicolas Rougier's open-access book. Borrow: the "ten simple rules" for
  figure design, figure layout organization (margins, alignment, typography
  scales), color-primer reasoning, and the 3D/animation chapters for
  anything beyond our `scatter3d_projections` and `trajectory-gif`
  templates.

## Bulk / transcriptomics

- **Earlier transcriptomics-figure-workbench implementation** — a retained
  project-local reference. Its private location and account association are
  intentionally omitted from this portable draft. Borrow:
  - Traceability workflow: input hash → params → output hash →
    `RENDERED_UNREVIEWED` review status bound to output hashes
    (implemented as `biostyle.record_provenance`).
  - Project theme: explicit identity→color slots, never cycle colors by row
    order (implemented as `load_project_theme` / `identity_colors`).
  - Scale variants: the same figure re-laid-out for Small/Medium/Large/
    Custom data sizes instead of shrinking text.
  - Frozen-results principle: never refit an embedding, FDR, enrichment,
    density or model to make a richer image — missing analysis stays
    missing.
  - 3D discipline (D01/D02/D03): orthographic projection, companion 2D
    projections to expose occlusion, explicit transfer functions for
    volumes, fixed cameras across animation frames (implemented as
    `scatter3d_projections`, `trajectory-gif`).
  - Richer alternative renderings: PCA with marginals, volcano with
    full-gene landscape, GSEA aligned tracks, rainclouds, per-identity
    marker pages (implemented as `volcano_marginal`, `pca_marginal`,
    `gsea_tracks`, `raincloud`, `marker_strip`).
  - Review discipline: inspect every changed export at its final physical
    size; a contact sheet or successful process cannot approve aesthetics.

## Single-cell

- **SCpubr** (enblacar.github.io/SCpubr-book) — 34 publication-ready
  Seurat plot functions, colorblind-safe defaults, rasterization options.
  Borrow: function-per-question organization, alluvial identity flows,
  dual-enrichment butterfly plots, activity heatmaps, and its legend/
  typography standardization. R users can call SCpubr directly when Seurat
  objects are in hand; restyle with `theme_biostyle()`.
- **dittoSeq** (bioconductor.org/packages/dittoSeq) — colorblind-friendly
  sc/bulk RNA-seq toolkit. Borrow: enlarged legend keys, shape/letter
  overlays on top of color for grayscale safety, and the
  "one question = one function" API shape (implemented as `dim_highlight`).
- **scCustomize + Nebulosa** (samuel-marsh.github.io/scCustomize) — Seurat
  plotting extensions. Borrow: combined QC panels, stacked violins
  (implemented as `stacked_violin`), barcode rank plots
  (`barcode_rank`), and Nebulosa expression-density plots
  (implemented as `expr_density`) as a smoother alternative to feature
  scatters for sparse markers.

## Distribution / raw-data figures

- **RainCloudPlots** (github.com/RainCloudPlots/RainCloudPlots) +
  **PtitPrince** (ptitprince, Python) and **ggdist** (R:
  `stat_halfeye` + `stat_dots`). Borrow: the cloud + rain + box anatomy —
  implemented as `biostyle.raincloud` and the ggdist recipe in
  `bulk-omics.md`.

## Docking / MD

- **ProLIF** (prolif.readthedocs.io) — protein-ligand interaction
  fingerprints from docking poses and MD trajectories. Borrow: barcode
  plots (residue × frame), 3D interaction display, LigNetwork ligand
  interaction diagrams. Compute fingerprints with ProLIF, render with our
  `ifp_barcode` template for house style.
- **MDAnalysis user guide, plotting examples** (userguide.mdanalysis.org →
  Examples → Analysis). Borrow: multi-domain RMSD overlay lines, pairwise
  2D-RMSD convergence matrices, Ramachandran plots with reference density
  contours, and pseudo-free-energy surfaces via −kT·ln P with a reversed
  colormap (our `rmsd_overlay`, `contact_map`, `ramachandran`, `fel_2d`
  templates follow these conventions).

## Machine learning

- **Yellowbrick** (scikit-yb.org) — visual diagnostics gallery for
  scikit-learn. Borrow: its visualizer taxonomy (feature / regression /
  classification / clustering / model-selection) as a checklist of
  diagnostics to offer, plus parallel coordinates (implemented as
  `parallel_coords`), prediction-error and silhouette patterns.
- **SHAP docs** (shap.readthedocs.io) — beeswarm, bar, dependence, heatmap
  and force plots. Borrow: the beeswarm color-by-feature-value convention
  and the supervised-clustering SHAP heatmap (implemented as
  `shap_summary`, `shap_dependence`, `shap_interaction`).

## Quantum chemistry

- **Multiwfn manual, spectra & DOS sections** (sobereva.com/multiwfn →
  manual §3.13, §4.11) — the de-facto convention set for IR/Raman/UV-Vis/
  ECD/VCD/NMR spectra and TDOS/PDOS/OPDOS. Borrow: stick lines at
  transition levels + broadened envelope, partial-spectrum decomposition,
  and spike markers showing degeneracy (our `ir_spectrum`, `uvvis`, `dos`
  templates follow this). **kimariDraw** (github.com/kimariyb/kimariDraw)
  re-renders Multiwfn spectral data in multi-panel layouts when a
  publication look is needed.

## General references for figure choice

- **From Data to Viz** (data-to-viz.com) — decision tree from data shape to
  chart type; use when the user's request maps to an unusual data shape.
- **Data Viz Project** (datavizproject.com) — 160+ chart types with a
  taxonomy by family / function / shape; the widest chart-type catalogue.
  Use it to name an unusual chart the user is describing.
- **FT Visual Vocabulary** (github.com/ft-interactive/chart-doctor —
  poster) — chart choice organized by communication purpose (change over
  time, composition, ranking, distribution...). Use it to sanity-check
  that the chosen figure answers the question's intent.
- **UpSet** (upset.app; Lex et al. 2014) — set-intersection visualization
  for >3 sets; Venn diagrams do not scale past 3-4 sets. Our `upset`
  template follows the matrix + intersection-bar layout; cite
  doi:10.1109/TVCG.2014.2346248 when used in publication.
- **Python Graph Gallery** (python-graph-gallery.com) — matplotlib/seaborn
  recipe patterns for uncommon chart types.
- **PyComplexHeatmap** (dingwb.github.io/PyComplexHeatmap) — Python
  counterpart of ComplexHeatmap: row/column annotations, split heatmaps,
  dot-clustermaps. Use when a Python pipeline needs ComplexHeatmap-style
  annotation without dropping to R.
- **ComplexHeatmap book** (jokergoo.github.io/ComplexHeatmap-reference)
  — annotated heatmap patterns (oncoPrint, upSet, density heatmaps) when
  matrix figures need more than our `deg_heatmap` template.

## Using external resources safely

- External galleries are inspiration and API references, not style
  authority: restyle anything borrowed through biostyle so the deliverable
  stays consistent.
- Respect licenses (MIT/GPL/Apache/CC-BY) when copying code patterns; cite
  the tool in methods when its computation (not just plotting) is used.
- Record source + retrieval date in the figure provenance sidecar when an
  external recipe materially shaped a delivered figure.
