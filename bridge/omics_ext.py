"""Local, reproducible omics helpers with explicit input and inference limits."""
import json
import uuid
from pathlib import Path
from lazy_database import LazyModule, LazyAttribute
np = LazyModule('numpy')
pd = LazyModule('pandas')
sparse = LazyModule('scipy.sparse')
hypergeom = LazyAttribute('scipy.stats', 'hypergeom')

HERE = Path(__file__).resolve().parent


def _output(name):
    folder = HERE / "outputs" / (name + "_" + uuid.uuid4().hex)
    folder.mkdir(parents=True)
    return folder


def _table(path):
    path = Path(path).resolve(strict=True)
    return pd.read_csv(path, sep="\t" if path.suffix.lower() in {".tsv", ".gmt"} else ",", index_col=0)


def _gene_sets(path):
    p = Path(path).resolve(strict=True)
    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf8"))
    elif p.suffix.lower() == ".gmt":
        data = {}
        for line in p.read_text(encoding="utf8").splitlines():
            fields = line.split("\t")
            if len(fields) < 3 or fields[0] in data:
                raise ValueError("Malformed GMT or duplicate gene-set name")
            data[fields[0]] = fields[2:]
    else:
        raise ValueError("Provide a local GMT or JSON gene-set file")
    if not isinstance(data, dict) or not data or any(not isinstance(v, list) or any(not isinstance(g, str) for g in v) for v in data.values()):
        raise ValueError("Gene sets must map names to lists of gene identifier strings")
    return data


def _bh(pvalues):
    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    q = np.minimum.accumulate((p[order] * len(p) / np.arange(1, len(p) + 1))[::-1])[::-1]
    out = np.empty_like(q)
    out[order] = np.minimum(q, 1)
    return out


def audit_expression_matrix(path: str, matrix_kind: str, orientation: str = "genes_by_samples", metadata_path: str = "", donor_key: str = "", condition_key: str = "") -> dict:
    """Audit numeric CSV/TSV, identifiers and sample metadata without inferring its scale."""
    if matrix_kind not in {"counts", "normalized", "log_normalized", "unknown"}:
        raise ValueError("Specify counts, normalized, log_normalized, or unknown")
    if orientation not in {"genes_by_samples", "samples_by_genes"}:
        raise ValueError("Specify matrix orientation")
    frame = _table(path)
    if orientation == "samples_by_genes":
        frame = frame.T
    numbers = frame.apply(pd.to_numeric, errors="coerce")
    x = numbers.to_numpy(dtype=float)
    if not x.size:
        raise ValueError("Matrix is empty")
    finite = x[np.isfinite(x)]
    issues = []
    if frame.index.has_duplicates:
        issues.append("duplicate_gene_identifiers")
    if frame.columns.has_duplicates or any(str(c).endswith((".1", ".2")) for c in frame.columns):
        issues.append("possible_duplicate_sample_identifiers")
    missing = int((~np.isfinite(x)).sum())
    if missing:
        issues.append("missing_or_non_numeric_values")
    negative = int((finite < 0).sum())
    fractional = int((np.abs(finite - np.rint(finite)) > 1e-6).sum())
    if matrix_kind == "counts" and (negative or fractional):
        issues.append("declared_counts_contain_negative_or_fractional_values")
    result = {"success": True, "declared_matrix_kind": matrix_kind, "shape_genes_samples": list(frame.shape), "issues": issues, "finite_values": int(finite.size), "missing_values": missing, "negative_values": negative, "fractional_values": fractional, "minimum": float(finite.min()) if finite.size else None, "maximum": float(finite.max()) if finite.size else None, "sample_totals": {str(k): float(v) for k, v in numbers.sum().items()}, "scale_verified": False, "limitations": ["Integer values alone do not establish raw counts. Verify processing methods and provenance.", "Sample-level QC does not establish biological independence."]}
    if metadata_path:
        meta = _table(metadata_path)
        missing_samples = sorted(set(map(str, frame.columns)) - set(map(str, meta.index)))
        extra_samples = sorted(set(map(str, meta.index)) - set(map(str, frame.columns)))
        result["metadata_alignment"] = {"missing_samples": missing_samples, "extra_samples": extra_samples, "duplicated_metadata_ids": bool(meta.index.has_duplicates)}
        if donor_key:
            if donor_key not in meta:
                raise ValueError("donor_key is absent from metadata")
            result["donors"] = {"unique_nonmissing": int(meta[donor_key].nunique()), "missing": int(meta[donor_key].isna().sum())}
            if condition_key:
                if condition_key not in meta:
                    raise ValueError("condition_key is absent from metadata")
                result["donors_by_condition"] = {str(k): int(v) for k, v in meta.groupby(condition_key)[donor_key].nunique().items()}
    return result


def audit_h5ad(path: str, matrix_kind: str, donor_key: str = "", condition_key: str = "", layer: str = "") -> dict:
    """Inspect H5AD identifiers, metadata and matrix blocks without treating cells as replicates."""
    import anndata as ad
    if matrix_kind not in {"counts", "normalized", "log_normalized", "unknown"}:
        raise ValueError("Specify the matrix kind")
    data = ad.read_h5ad(path, backed="r")
    try:
        matrix = data.layers[layer] if layer else data.X
        missing = negative = fractional = 0
        total = 0.0
        for start in range(0, data.n_obs, 1024):
            block = matrix[start:start + 1024]
            values = block.data if sparse.issparse(block) else np.asarray(block).ravel()
            missing += int((~np.isfinite(values)).sum())
            finite = values[np.isfinite(values)]
            negative += int((finite < 0).sum())
            fractional += int((np.abs(finite - np.rint(finite)) > 1e-6).sum())
            total += float(finite.sum())
        result = {"success": True, "declared_matrix_kind": matrix_kind, "shape_cells_genes": [data.n_obs, data.n_vars], "matrix_layer": layer or "X", "obs_columns": list(data.obs.columns), "layers": list(data.layers), "duplicate_cells": bool(data.obs_names.has_duplicates), "duplicate_genes": bool(data.var_names.has_duplicates), "missing_values": missing, "negative_values": negative, "fractional_values": fractional, "total": total, "count_compatible": matrix_kind == "counts" and not (missing or negative or fractional), "limitations": ["Cells are observations; donor/sample independence must be specified.", "No normalization or differential analysis was performed."]}
        if donor_key:
            if donor_key not in data.obs:
                raise ValueError("donor_key is absent from obs")
            result["donor_count"] = int(data.obs[donor_key].nunique())
            result["missing_donors"] = int(data.obs[donor_key].isna().sum())
            if condition_key:
                if condition_key not in data.obs:
                    raise ValueError("condition_key is absent from obs")
                result["donors_by_condition"] = {str(k): int(v) for k, v in data.obs.groupby(condition_key, observed=True)[donor_key].nunique().items()}
        return result
    finally:
        data.file.close()


def local_gene_set_enrichment(genes: list[str], background: list[str], gene_sets_path: str, min_size: int = 5, max_size: int = 500) -> dict:
    """Hypergeometric ORA with explicit tested-gene universe and BH across all eligible sets."""
    if not background or not genes:
        raise ValueError("Provide a nonempty gene list and explicit tested-gene background")
    universe, selected = set(background), set(genes)
    if not selected <= universe:
        raise ValueError("Selected genes must be included in the background")
    if not 1 <= min_size <= max_size:
        raise ValueError("Invalid gene-set size bounds")
    rows = []
    for name, members in _gene_sets(gene_sets_path).items():
        eligible = set(members) & universe
        if not min_size <= len(eligible) <= max_size:
            continue
        overlap = sorted(eligible & selected)
        p = float(hypergeom.sf(len(overlap) - 1, len(universe), len(eligible), len(selected)))
        rows.append({"term": name, "p_value": p, "set_size_in_background": len(eligible), "overlap_count": len(overlap), "overlap_genes": overlap})
    qvalues = _bh([r["p_value"] for r in rows]) if rows else []
    for row, q in zip(rows, qvalues):
        row["fdr_bh"] = float(q)
    rows.sort(key=lambda r: (r["fdr_bh"], r["p_value"]))
    path = _output("ora") / "all_tested_terms.json"
    from evidence import atomic_json
    atomic_json(path, rows)
    return {"success": True, "method": "hypergeometric_overrepresentation", "background_size": len(universe), "selected_size": len(selected), "tested_sets": len(rows), "all_results_file": str(path), "results": rows, "limitations": ["Enrichment depends on the measured/tested-gene universe and gene-set version.", "Pathway enrichment does not establish causal activation."]}


def preranked_gsea(ranks_path: str, gene_sets_path: str, min_size: int = 15, max_size: int = 500, permutation_num: int = 1000, seed: int = 42) -> dict:
    """Seeded GSEA using a two-column gene/ranking-statistic CSV/TSV and local GMT/JSON."""
    import gseapy as gp
    ranks = _table(ranks_path)
    if ranks.shape[1] != 1 or ranks.index.has_duplicates:
        raise ValueError("Ranks need one numeric statistic column and unique gene identifiers")
    ranks.iloc[:, 0] = pd.to_numeric(ranks.iloc[:, 0], errors="raise")
    if not np.isfinite(ranks.iloc[:, 0].to_numpy(dtype=float)).all():
        raise ValueError("Ranking statistics must be finite")
    if not 10 <= permutation_num <= 10000:
        raise ValueError("permutation_num must be 10..10000")
    folder = _output("gsea")
    result = gp.prerank(rnk=ranks.iloc[:, 0], gene_sets=_gene_sets(gene_sets_path), min_size=min_size, max_size=max_size, permutation_num=permutation_num, seed=seed, threads=1, outdir=str(folder), no_plot=True, verbose=False)
    rows = json.loads(result.res2d.to_json(orient="records"))
    return {"success": True, "seed": seed, "permutation_num": permutation_num, "ranked_genes": len(ranks), "tied_statistics": int(ranks.iloc[:, 0].duplicated().sum()), "output_directory": str(folder), "results": rows, "limitations": ["Gene-set permutations do not substitute for biological replicate validation.", "Record contrast direction and statistic definition before interpreting NES."]}


def map_orthologs(gene_ids: list[str], source_species: str, target_species: str, orthology_type: str = "ortholog_one2one") -> dict:
    """Map explicit Ensembl IDs via homology, retaining absent and nonmatching mappings."""
    import re
    from urllib.parse import quote
    from http_client import get_json
    if len(gene_ids) > 50 or not gene_ids:
        raise ValueError("Supply 1..50 Ensembl gene identifiers per call")
    if orthology_type not in {"ortholog_one2one", "ortholog_one2many", "ortholog_many2many", "all"}:
        raise ValueError("Invalid orthology_type")
    rows = []
    for identifier in gene_ids:
        if not re.fullmatch(r"ENS[A-Z]*G\d+", identifier):
            raise ValueError("Use unversioned Ensembl gene IDs")
        data = get_json(f"https://rest.ensembl.org/homology/id/{quote(source_species, safe='')}/{identifier}", {"target_species": target_species, "type": "orthologues", "content-type": "application/json"})
        all_mappings = [h for d in data.get("data", []) for h in d.get("homologies", [])]
        retained = [h for h in all_mappings if h.get("target", {}).get("species") == target_species and (orthology_type == "all" or h.get("type") == orthology_type)]
        rows.append({"input": identifier, "matches": retained, "all_returned_mappings": all_mappings, "state": "mapped" if retained else "unmapped_or_filtered"})
    return {"success": True, "source_species": source_species, "target_species": target_species, "orthology_type": orthology_type, "rows": rows, "limitations": ["Orthology does not guarantee conserved expression, regulation, or function."]}


def annotate_cells_by_markers(path: str, markers_path: str, matrix_kind: str, min_margin: float = 0.1, min_markers: int = 2, seed: int = 42) -> dict:
    """Score explicit marker sets locally and retain ambiguous cells as Unknown."""
    import scanpy as sc
    if matrix_kind != "log_normalized":
        raise ValueError("Provide verified log-normalized expression")
    if min_margin < 0 or min_markers < 1:
        raise ValueError("Invalid ambiguity thresholds")
    data = sc.read_h5ad(path)
    if data.var_names.has_duplicates or data.obs_names.has_duplicates:
        raise ValueError("Gene and cell identifiers must be unique")
    sets = _gene_sets(markers_path)
    scores, missing = {}, {}
    for name, genes in sets.items():
        found = sorted(set(genes) & set(data.var_names))
        missing[name] = sorted(set(genes) - set(found))
        if len(found) < min_markers:
            continue
        key = "bridge_marker_" + str(len(scores))
        sc.tl.score_genes(data, found, score_name=key, random_state=seed, use_raw=False, ctrl_size=min(50, max(1, data.n_vars // 10)), n_bins=min(25, max(2, data.n_vars // 10)))
        scores[name] = data.obs[key].to_numpy()
    if len(scores) < 2:
        raise ValueError("At least two marker sets need sufficient measured genes")
    matrix = np.column_stack(list(scores.values()))
    ordered = np.argsort(matrix, axis=1)
    best = ordered[:, -1]
    margin = matrix[np.arange(data.n_obs), best] - matrix[np.arange(data.n_obs), ordered[:, -2]]
    labels = np.asarray(list(scores))[best].astype(object)
    labels[(margin < min_margin) | ~np.isfinite(margin)] = "Unknown"
    output = pd.DataFrame({"candidate_label": labels, "score_margin": margin}, index=data.obs_names)
    for name, values in scores.items():
        output["score_" + name] = values
    folder = _output("marker_annotation")
    output.to_csv(folder / "cell_labels.csv")
    return {"success": True, "output_directory": str(folder), "label_counts": {str(k): int(v) for k, v in output.candidate_label.value_counts().items()}, "missing_markers": missing, "seed": seed, "min_margin": min_margin, "limitations": ["Labels and margins are marker-based heuristics, not calibrated probabilities.", "Inspect canonical and conflicting markers and tissue/species context before accepting labels."]}


def transfer_cell_labels(reference_path: str, query_path: str, label_key: str, matrix_kind: str, neighbors: int = 15, min_vote_fraction: float = 0.7, seed: int = 42) -> dict:
    """Reference-fitted PCA/kNN transfer on shared genes with an explicit Unknown class."""
    import scanpy as sc
    from sklearn.decomposition import TruncatedSVD
    from sklearn.neighbors import KNeighborsClassifier
    if matrix_kind not in {"counts", "log_normalized"}:
        raise ValueError("Provide verified counts or compatible log-normalized matrices")
    if not 0.5 <= min_vote_fraction <= 1 or neighbors < 1:
        raise ValueError("Invalid vote threshold/neighbors")
    reference, query = sc.read_h5ad(reference_path), sc.read_h5ad(query_path)
    if any(d.var_names.has_duplicates or d.obs_names.has_duplicates for d in (reference, query)):
        raise ValueError("Identifiers must be unique")
    if label_key not in reference.obs or reference.obs[label_key].isna().any():
        raise ValueError("Reference label_key must exist without missing labels")
    genes = sorted(set(reference.var_names) & set(query.var_names))
    if len(genes) < 20 or reference.n_obs < 3 or query.n_obs < 1:
        raise ValueError("Need >=20 shared genes, >=3 reference cells and >=1 query cell")
    reference, query = reference[:, genes].copy(), query[:, genes].copy()
    for data in (reference, query):
        values = data.X.data if sparse.issparse(data.X) else np.asarray(data.X).ravel()
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError("Matrices must contain finite nonnegative values")
        if matrix_kind == "counts":
            if not np.allclose(values, np.rint(values), atol=1e-6):
                raise ValueError("Declared counts contain fractional values")
            sc.pp.normalize_total(data, target_sum=10000)
            sc.pp.log1p(data)
    # Select features and fit the projection on the reference only.
    x = sparse.csr_matrix(reference.X)
    q = sparse.csr_matrix(query.X)
    mean = np.asarray(x.mean(axis=0)).ravel()
    variance = np.asarray(x.power(2).mean(axis=0)).ravel() - mean ** 2
    chosen = np.argsort(variance)[-min(2000, len(genes)):]
    if not np.any(variance[chosen] > 0):
        raise ValueError("Reference matrix has no variable genes")
    projection = TruncatedSVD(n_components=min(30, reference.n_obs - 1, len(chosen) - 1), random_state=seed)
    embedding = projection.fit_transform(x[:, chosen])
    query_embedding = projection.transform(q[:, chosen])
    classifier = KNeighborsClassifier(n_neighbors=min(neighbors, reference.n_obs), weights="uniform")
    classifier.fit(embedding, reference.obs[label_key].astype(str))
    probabilities = classifier.predict_proba(query_embedding)
    best = probabilities.argmax(axis=1)
    confidence = probabilities.max(axis=1)
    labels = classifier.classes_[best].astype(object)
    ties = (probabilities == confidence[:, None]).sum(axis=1) > 1
    labels[(confidence < min_vote_fraction) | ties] = "Unknown"
    output = pd.DataFrame({"candidate_label": labels, "vote_fraction": confidence}, index=query.obs_names)
    folder = _output("label_transfer")
    output.to_csv(folder / "cell_labels.csv")
    return {"success": True, "output_directory": str(folder), "shared_genes": len(genes), "selected_genes": len(chosen), "reference_cells": reference.n_obs, "query_cells": query.n_obs, "label_counts": {str(k): int(v) for k, v in output.candidate_label.value_counts().items()}, "seed": seed, "limitations": ["Neighbor vote fractions are not calibrated probabilities or independent validation.", "No batch correction is applied; inspect tissue/species/batch compatibility and out-of-reference cell types.", "Cells do not constitute independent biological replicates."]}
