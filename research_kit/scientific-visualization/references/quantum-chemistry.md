> Legacy reference preserved. For current result-only calls and tested contracts, read [v2 API](v2-api.md). These original examples may include analysis or placeholder assembly and do not constitute current runtime acceptance.

# Quantum Chemistry Figures

Computational chemistry visualization: spectra, densities of states,
orbital levels, reaction profiles, convergence, charges. Data typically:
Gaussian/ORCA/psi4 outputs parsed with cclib (install if missing:
`uv pip install cclib`), Multiwfn exports, or plain CSV tables of
frequencies/intensities/energies.

## Catalog

| Question | Figure | Data input | Language | Template id |
|---|---|---|---|---|
| What are the vibrational modes? | IR spectrum (stick + broadened) | freq + intensity table | py | `ir_spectrum` |
| What are the excitations? | UV-Vis with oscillator strengths | excitation energies + f | py | `uvvis` |
| Absorption vs emission? | Mirror plot + Stokes shift | both spectra tables | py | `emission_stokes` |
| Chiroptical response? | ECD/CD spectrum | rotatory strengths | py | `ecd` |
| Electronic states distribution? | DOS/PDOS stacked areas | levels + occupations | py | `dos` |
| Where are HOMO/LUMO? | Orbital energy level diagram | orbital energies | py | `orbitals` |
| What is the reaction path? | IRC / reaction-profile curves | energy vs coordinate | py | `irc` |
| How does energy vary in a scan? | PES scan curve | scan table | py | `scan_curve` |
| Did the optimization converge? | E + max-force dual panel | optimization log table | py | `opt_convergence` |
| Where is charge localized? | Charge bar chart (Mulliken/NBO) | per-atom charges | py | `charges` |
| How does substitution shift charge? | Charge difference plot | two charge sets | py | `charge_diff` |
| Which bonds weaken? | Wiberg bond-order matrix | bond-order matrix | py | `wiberg` |
| Charge on the molecular sketch | 2D structure colored by charge | SMILES + charges | py | `charge_2d` |
| How do gaps compare across systems? | HOMO-LUMO gap bars | orbital energies per system | py | `gap_compare` |
| Which conformers matter? | Boltzmann population bars | conformer energies | py | `boltzmann` |
| Where are the weak interactions? | NCI/RDG scatter | sign(λ2)ρ + RDG per grid point | py | `nci_rdg` |
| What are the NMR shifts? | NMR spectrum (sticks + envelope) | peak table (ppm, intensity) | py | `nmr_spectrum` |
| Where does the 2D scan cross barriers? | 2D PES contour | regular-grid scan energies | py | `pes_2d` |

---

### ir_spectrum — IR spectrum with broadening `id: ir_spectrum`

```python
# INPUT : DataFrame fr, columns: freq(cm-1, float), inten(km/mol or eps, float);
#         optional dict extra {method_name: DataFrame} for overlays
# OUTPUT: fig_ir.png/svg
# DEPENDS: numpy, matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
def broaden(freqs, intens, fwhm=12.0, grid=None, profile="gauss"):
    grid = grid if grid is not None else np.linspace(400, 4000, 1800)
    sigma = fwhm / 2.3548
    y = np.zeros_like(grid)
    for f, a in zip(freqs, intens):
        if profile == "gauss":
            y += a * np.exp(-0.5 * ((grid - f) / sigma) ** 2)
        else:                                    # Lorentzian
            y += a * (fwhm / 2) ** 2 / ((grid - f) ** 2 + (fwhm / 2) ** 2)
    return grid, y

grid, spec = broaden(fr.freq.to_numpy(), fr.inten.to_numpy())
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
ax.plot(grid, spec, c="#0072B2", lw=1.4, label="Gaussian (FWHM 12 cm$^{-1}$)")
ax.vlines(fr.freq, 0, fr.inten / fr.inten.max() * spec.max() * 0.9,
          color="#9FB8CE", lw=0.8)                       # stick spectrum
ax.set(xlabel="Wavenumber (cm$^{-1}$)", ylabel="Transmittance-weighted intensity (a.u.)",
       xlim=(400, 4000))
ax.invert_xaxis()                                        # IR convention
ax.legend(fontsize=7); beautify(ax)
save_fig(fig, "fig_ir")
```

### uvvis — UV-Vis absorption with oscillator strengths `id: uvvis`

```python
# INPUT : DataFrame ex, columns: eV(float), f(float, oscillator strength);
#         optional DataFrame exp (columns: nm, absorb) for overlay
# OUTPUT: fig_uvvis.png/svg
# DEPENDS: numpy, matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
def broaden_ev(e_ev, f, sigma=0.15, nm_grid=None):
    lam_nm = 1239.84193 / np.asarray(e_ev)               # eV -> nm
    grid = nm_grid if nm_grid is not None else np.linspace(200, 800, 1200)
    y = np.zeros_like(grid)
    for l, a in zip(lam_nm, f):
        y += a * np.exp(-0.5 * ((grid - l) / sigma) ** 2)
    return grid, y

grid, spec = broaden_ev(ex.eV, ex.f)
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
ax.plot(grid, spec / spec.max(), c="#0072B2", lw=1.5, label="Calculated")
ax.vlines(1239.84193 / ex.eV, 0, ex.f / ex.f.max() * 0.85,
          color="#FF9400", lw=1.0, label="Oscillator strength")
if "exp" in dir() and exp is not None:
    ax.plot(exp.nm, exp.absorb / exp.absorb.max(), c="#333333", lw=1.2,
            ls="--", label="Experimental")
ax.set(xlabel="Wavelength (nm)", ylabel="Normalized absorbance (a.u.)",
       xlim=(200, 800))
ax.legend(fontsize=7); beautify(ax)
save_fig(fig, "fig_uvvis")
```

### emission_stokes — Absorption/emission mirror plot `id: emission_stokes`

```python
# INPUT : DataFrame abs (nm, intensity), DataFrame emi (nm, intensity)
# OUTPUT: fig_stokes.png/svg (mirrored around zero)
# DEPENDS: numpy, matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
ax.fill_between(abs.nm, abs.intensity / abs.intensity.max(), 0,
                color="#0072B2",
                alpha=0.75, lw=0, label="Absorption")
ax.fill_between(emi.nm, -emi.intensity / emi.intensity.max(), 0,
                color="#FF9400",
                alpha=0.75, lw=0, label="Emission")
ax.axhline(0, c="black", lw=0.8)
stokes = (emi.nm[emi.intensity.idxmax()]
         - abs.nm[abs.intensity.idxmax()])
ax.text(0.97, 0.06, f"Stokes shift ≈ {stokes:.0f} nm", transform=ax.transAxes,
        ha="right", fontsize=7.5)
ax.set(xlabel="Wavelength (nm)", ylabel="Normalized intensity (a.u.)")
ax.legend(loc="upper right", fontsize=7); beautify(ax)
save_fig(fig, "fig_stokes")
```

### ecd — ECD spectrum `id: ecd`

```python
# INPUT : DataFrame ex, columns: eV(float), R(float, rotatory strength in 1e-40 cgs)
# OUTPUT: fig_ecd.png/svg
# DEPENDS: numpy, matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
sigma = 0.2                                            # eV
grid = np.linspace(1.5, 6.5, 800)
y = sum(R * np.exp(-0.5 * ((grid - E) / sigma) ** 2) for E, R in zip(ex.eV, ex.R))
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
ax.plot(1239.84193 / grid[::-1], y[::-1], c="#7A00E6", lw=1.5)
ax.axhline(0, c="black", lw=0.8)
ax.set(xlabel="Wavelength (nm)", ylabel="Δε (a.u.)")
beautify(ax)
save_fig(fig, "fig_ecd")
```

### dos — DOS/PDOS stacked areas `id: dos`

```python
# INPUT : DataFrame dos, columns: E(eV, float), pdos_s, pdos_p, pdos_d (floats)
# OUTPUT: fig_dos.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
ax.stackplot(dos.E, dos.pdos_s, dos.pdos_p, dos.pdos_d,
             colors=["#0072B2", "#FF9400", "#009E73"],
             labels=["s", "p", "d"], alpha=0.85, lw=0)
ax.axvline(0, c="#D55E00", lw=1.0, ls="--")            # Fermi level
ax.text(0.02, 0.95, "$E_F$", transform=ax.transAxes, color="#D55E00", fontsize=9)
ax.set(xlabel="Energy – E$_F$ (eV)", ylabel="PDOS (states/eV)")
ax.legend(loc="upper right", fontsize=7); beautify(ax)
save_fig(fig, "fig_dos")
```

### orbitals — Orbital energy level diagram `id: orbitals`

```python
# INPUT : dict levels {system: {"energies": array(eV), "occ": array(0/1/2)}}
# OUTPUT: fig_orbitals.png/svg (level lines, HOMO/LUMO arrows, gap annotation)
# DEPENDS: matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 0.9))
w, dx = 0.32, 1.0
for i, (name, lv) in enumerate(levels.items()):
    E, occ = np.asarray(lv["energies"]), np.asarray(lv["occ"])
    homo_i = np.where(occ > 0)[0].max()
    for j, e in enumerate(E):
        solid = occ[j] > 0
        ax.hlines(e, i * dx - w / 2, i * dx + w / 2,
                  color="#0072B2" if solid else "#D55E00", lw=2.2)
        if j in (homo_i, homo_i + 1):
            ax.text(i * dx + w / 2 + 0.04, e,
                    "HOMO" if j == homo_i else "LUMO", fontsize=7, va="center")
    gap = E[homo_i + 1] - E[homo_i]
    ax.annotate("", xy=(i * dx - w / 2 - 0.06, E[homo_i]),
                xytext=(i * dx - w / 2 - 0.06, E[homo_i + 1]),
                arrowprops=dict(arrowstyle="<->", lw=0.8, color="#333333"))
    ax.text(i * dx - w / 2 - 0.10, (E[homo_i] + E[homo_i + 1]) / 2,
            f"Δ = {gap:.2f} eV", rotation=90, fontsize=6.5,
            ha="right", va="center")
ax.set_xticks([i * dx for i in range(len(levels))], list(levels))
ax.set(ylabel="Orbital energy (eV)")
beautify(ax); ax.grid(False)
save_fig(fig, "fig_orbitals")
```

### irc — IRC / reaction profile `id: irc`

```python
# INPUT : dict paths {method: DataFrame(coord(float), E(kcal/mol, relative))}
# OUTPUT: fig_irc.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
for i, (name, d) in enumerate(paths.items()):
    ax.plot(d.coord, d.E, c=cat_palette(len(paths))[i], lw=1.8, label=name)
    ts_i = d.E.idxmax()
    ax.scatter(d.coord[ts_i], d.E[ts_i], s=42, c=cat_palette(len(paths))[i],
               edgecolor="white", lw=0.6, zorder=5)
ax.axhline(0, c="#999999", lw=0.7, ls=":")
ax.set(xlabel="Reaction coordinate (Å or IRC steps)", ylabel="Relative energy (kcal/mol)")
ax.legend(fontsize=7); beautify(ax)
save_fig(fig, "fig_irc")
```

### scan_curve — PES scan curve `id: scan_curve`

```python
# INPUT : DataFrame scan, columns: coord(float, Å or deg), E(kcal/mol relative)
# OUTPUT: fig_scan.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 0.65))
ax.plot(scan.coord, scan.E, c="#0072B2", lw=1.8, marker="o", ms=3.5,
        mfc="white", mec="#0072B2")
ax.set(xlabel="Scanned coordinate (Å / °)", ylabel="Relative energy (kcal/mol)")
beautify(ax)
save_fig(fig, "fig_scan")
```

### opt_convergence — Optimization convergence panel `id: opt_convergence`

```python
# INPUT : DataFrame opt, columns: step(int), E(float), max_force(float), rms_force(float)
# OUTPUT: fig_opt.png/svg (2 panels: energy + forces vs step, threshold line)
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, beautify, panel_labels

use_style("journal")
fig, axes = plt.subplots(1, 2, figsize=journal_size("onehalf", 0.5))
axes[0].plot(opt.step, opt.E, c="#0072B2", lw=1.6, marker="o", ms=3)
axes[0].set(xlabel="Optimization step", ylabel="Energy (Hartree)")
axes[1].semilogy(opt.step, opt.max_force, c="#D55E00", lw=1.6, label="max")
axes[1].semilogy(opt.step, opt.rms_force, c="#0072B2", lw=1.6, label="RMS")
axes[1].axhline(4.5e-4, c="#999999", lw=0.8, ls="--")   # Gaussian default threshold
axes[1].text(0.98, 4.5e-4 * 1.4, "convergence threshold", fontsize=6.5,
             ha="right", color="#666666", transform=axes[1].get_yaxis_transform())
axes[1].set(xlabel="Optimization step", ylabel="Force (Hartree/Bohr)")
axes[1].legend(fontsize=7)
for ax in axes: beautify(ax)
panel_labels(fig, axes)
save_fig(fig, "fig_opt")
```

### charges — Per-atom charge bar chart `id: charges`

```python
# INPUT : DataFrame q, columns: atom(str, e.g. "C1"), charge(float)
# OUTPUT: fig_charges.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, div_cmap, beautify

use_style("journal")
q = q.sort_values("charge")
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.5))
norm = plt.Normalize(q.charge.min(), q.charge.max())
cmap = div_cmap("brand")
ax.bar(range(len(q)), q.charge, color=[cmap(v) for v in q.charge],
       width=0.7, edgecolor="white", lw=0.3)
ax.set_xticks(range(len(q)), q.atom, rotation=90, fontsize=6)
ax.axhline(0, c="black", lw=0.8)
ax.set(xlabel="Atom", ylabel="Partial charge (e)")
beautify(ax); ax.grid(False)
save_fig(fig, "fig_charges")
```

### charge_diff — Charge difference on substitution `id: charge_diff`

```python
# INPUT : DataFrame dq, columns: atom(str), delta_q(float, substituted - parent)
# OUTPUT: fig_chargediff.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, div_cmap, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("onehalf", 0.5))
colors = ["#D55E00" if v > 0 else "#0072B2" for v in dq.delta_q]
ax.bar(dq.atom, dq.delta_q, color=colors, width=0.7, edgecolor="white", lw=0.3)
ax.axhline(0, c="black", lw=0.8)
ax.set(xlabel="Atom", ylabel="Δq on substitution (e)")
ax.tick_params(axis="x", rotation=90, labelsize=6)
beautify(ax); ax.grid(False)
save_fig(fig, "fig_chargediff")
```

### wiberg — Wiberg bond-order matrix `id: wiberg`

```python
# INPUT : ndarray W (n_atoms x n_atoms), list atom_labels
# OUTPUT: fig_wiberg.png/svg
# DEPENDS: matplotlib
import matplotlib.pyplot as plt
from biostyle import use_style, save_fig, journal_size, seq_cmap, add_colorbar

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 1.0))
im = ax.imshow(W, cmap=seq_cmap("mako"), vmin=0)
ax.set_xticks(range(len(atom_labels)), atom_labels, rotation=90, fontsize=6)
ax.set_yticks(range(len(atom_labels)), atom_labels, fontsize=6)
for s in ax.spines.values(): s.set_visible(False)
add_colorbar(fig, im, ax, label="Wiberg bond order")
save_fig(fig, "fig_wiberg")
```

### charge_2d — 2D structure colored by charge `id: charge_2d`

```python
# INPUT : str smiles; dict charges {atom_index(int): charge(float)}
# OUTPUT: fig_charge2d.png/svg
# DEPENDS: rdkit
from rdkit import Chem
from rdkit.Chem import Draw
from rdkit.Chem.Draw import rdMolDraw2D
from biostyle import results_dir

def _charge_color(q, lo=-0.5, hi=0.5):
    """Charge -> brand diverging RGB floats (blue negative, orange positive)."""
    t = min(max((q - lo) / (hi - lo), 0.0), 1.0)     # 0 = most negative
    blue, white, orange = (0.008, 0.474, 0.933), (1, 1, 1), (1.0, 0.580, 0.0)
    a, b = (blue, white) if t < 0.5 else (white, orange)
    u = t * 2 if t < 0.5 else (t - 0.5) * 2
    return tuple(ai + (bi - ai) * u for ai, bi in zip(a, b))

mol = Chem.MolFromSmiles(smiles)
d = rdMolDraw2D.MolDraw2DCairo(700, 600)
opts = d.drawOptions()
opts.useBWAtomPalette = False
opts.setAtomPalette({i: (*_charge_color(q), 1.0) for i, q in charges.items()})
rdMolDraw2D.PrepareAndDrawMolecule(d, mol)
d.FinishDrawing()
(results_dir() / "fig_charge2d.png").write_bytes(d.GetDrawingText())
```

The `_charge_color` helper interpolates blue -> white -> orange across the
charge range; widen `lo`/`hi` to the actual min/max of your charges.  Add a
colorbar legend beside the drawing when delivering.

### gap_compare — HOMO-LUMO gap comparison `id: gap_compare`

```python
# INPUT : dict gaps {system: {"homo": eV, "lumo": eV}}
# OUTPUT: fig_gap.png/svg (dumbbell plot: HOMO-LUMO pairs per system)
# DEPENDS: matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
names = list(gaps)
homo = [gaps[n]["homo"] for n in names]
lumo = [gaps[n]["lumo"] for n in names]
y = np.arange(len(names))
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
for yi, h, l in zip(y, homo, lumo):
    ax.plot([h, l], [yi, yi], c="#C7CDD4", lw=2.2, zorder=1)
ax.scatter(homo, y, s=42, c="#0072B2", zorder=3, label="HOMO", edgecolor="white", lw=0.5)
ax.scatter(lumo, y, s=42, c="#D55E00", zorder=3, label="LUMO", edgecolor="white", lw=0.5)
ax.set_yticks(y, names, fontsize=7)
ax.set(xlabel="Orbital energy (eV)")
ax.legend(loc="lower right", fontsize=7)
beautify(ax); ax.grid(axis="x", alpha=0.3); ax.grid(axis="y", visible=False)
save_fig(fig, "fig_gap")
```

### boltzmann — Conformer populations `id: boltzmann`

```python
# INPUT : DataFrame conf, columns: conformer(str), dE(kcal/mol, relative)
# OUTPUT: fig_boltzmann.png/svg (bars: ΔE; line/labels: Boltzmann % at 298 K)
# DEPENDS: matplotlib
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, cat_palette, beautify

use_style("journal")
d = conf.sort_values("dE")
p = np.exp(-d.dE * 1000 / (1.9872041e-3 * 298.15))
p = p / p.sum() * 100
fig, ax = plt.subplots(figsize=journal_size("single", 0.7))
ax.bar(range(len(d)), d.dE, color=cat_palette(len(d)), width=0.66,
       edgecolor="white", lw=0.5)
for i, (de, pop) in enumerate(zip(d.dE, p)):
    ax.text(i, de + 0.05, f"{pop:.0f}%", ha="center", fontsize=7)
ax.set_xticks(range(len(d)), d.conformer, rotation=45, ha="right", fontsize=7)
ax.set(xlabel="Conformer", ylabel="Relative energy (kcal/mol)")
beautify(ax); ax.grid(axis="y", visible=False)
save_fig(fig, "fig_boltzmann")
```

### nci_rdg — NCI/RDG scatter `id: nci_rdg`

Noncovalent-interaction scatter (Multiwfn/RDGrid convention): RDG vs
sign(λ₂)·ρ; the low-RDG spike at ρ≈0 is the interaction region — blue side
attraction, red side repulsion. State the grid and isosurface value used.

```python
# INPUT : ndarray sgn_rho (sign(lambda2)*rho per grid point); ndarray rdg (RDG per point)
# OUTPUT: fig_nci.png/svg
# DEPENDS: matplotlib, numpy
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, div_cmap, beautify

use_style("journal")
fig, ax = plt.subplots(figsize=journal_size("single", 0.8))
ax.scatter(sgn_rho, rdg, s=1.5, c=sgn_rho, cmap=div_cmap("brand"),
           vmin=-0.05, vmax=0.05, lw=0, rasterized=True)
ax.set(xlim=(-0.1, 0.1), ylim=(0, 2.0),
       xlabel=r"sign($\lambda_2$)$\rho$ (a.u.)", ylabel="RDG (a.u.)")
beautify(ax)
save_fig(fig, "fig_nci")
```

### nmr_spectrum — NMR spectrum (sticks + envelope) `id: nmr_spectrum`

Computed NMR shifts as a broadened envelope with stick markers at each
transition (Multiwfn convention); ppm axis reversed by NMR convention.
State the reference (TMS) and broadening FWHM.

```python
# INPUT : DataFrame shifts (columns: ppm, intensity); float fwhm (ppm)
# OUTPUT: fig_nmr.png/svg
# DEPENDS: matplotlib, numpy
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, beautify

use_style("journal")
ppm = np.linspace(shifts.ppm.max() + 1, shifts.ppm.min() - 1, 2000)
sigma = fwhm / 2.355
spec = np.sum(shifts.intensity.to_numpy() *
              np.exp(-0.5 * ((ppm[:, None] - shifts.ppm.to_numpy()) / sigma) ** 2),
              axis=1)
fig, ax = plt.subplots(figsize=journal_size("single", 0.6))
ax.plot(ppm, spec, c="#0072B2", lw=1.2)
ax.vlines(shifts.ppm, 0, shifts.intensity / shifts.intensity.max()
          * spec.max() * 0.12, color="#999999", lw=0.8)
ax.set(xlabel="Chemical shift (ppm)", ylabel="Intensity (a.u.)", yticks=[])
beautify(ax)
save_fig(fig, "fig_nmr")
```

### pes_2d — 2D PES contour `id: pes_2d`

Relaxed/rigid 2D coordinate scan as filled contours with white level lines;
energy clipped to a sane window (e.g. 40 kJ/mol) so the minimum region
keeps contrast. Mark the optimized minimum if available.

```python
# INPUT : DataFrame pes (columns: r1, r2, energy)  # regular grid scan
# OUTPUT: fig_pes_2d.png/svg
# DEPENDS: matplotlib, numpy
import matplotlib.pyplot as plt, numpy as np
from biostyle import use_style, save_fig, journal_size, seq_cmap, add_colorbar

use_style("journal")
pivot = pes.pivot_table(index="r2", columns="r1", values="energy")
E = np.minimum(pivot.to_numpy() - pivot.to_numpy().min(), 40.0)
fig, ax = plt.subplots(figsize=journal_size("single", 0.85))
cs = ax.contourf(pivot.columns, pivot.index, E, levels=20, cmap=seq_cmap("mako"))
ax.contour(pivot.columns, pivot.index, E, levels=20,
           colors="white", linewidths=0.4)
ax.set(xlabel="Coordinate 1 (Å / deg)", ylabel="Coordinate 2 (Å / deg)")
add_colorbar(fig, cs, ax, label="Relative energy (kJ/mol)")
save_fig(fig, "fig_pes_2d")
```

---

## Beauty checklist (quantum chemistry)

- Spectra: state broadening model and FWHM/sigma; sticks + envelope together.
- Energy axes: state the reference (relative to reactants/global minimum).
- Orbital diagrams: solid lines = occupied, hollow/colored = virtual; label
  HOMO/LUMO and the gap.
- Charges: state the method (Mulliken/NBO/Hirshfeld) — they are not
  observables.
- IR x-axis inverted (4000 → 400 cm⁻¹) per spectroscopy convention.

## Common pitfalls

- Comparing absolute energies across different levels of theory/basis sets.
- Boltzmann populations without stating temperature.
- Over-broadening spectra until features merge — keep FWHM honest.
- Presenting Mulliken charges as experimental quantities.
