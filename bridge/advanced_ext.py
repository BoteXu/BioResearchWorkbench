"""Auditable analysis extensions with explicit source, design and validation boundaries."""
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path
from transcriptomics_ext import _context,_frames,_capacity,_folder,_finish,_workflow,_read,require_local


def _hashes(**paths):
    return {k:hashlib.sha256(Path(v).read_bytes()).hexdigest() for k,v in paths.items()}


def _design(meta,predictors,interactions=None):
    import numpy as np
    import pandas as pd
    from statistics_ext import _finite
    if not isinstance(predictors,dict) or not 1<=len(predictors)<=20 or not set(predictors)<=set(meta): raise ValueError('Declare bounded predictor columns and types')
    columns={};encodings={};groups={}
    for key,spec in predictors.items():
        if not isinstance(spec,dict) or spec.get('type') not in {'numeric','categorical'} or meta[key].eq('').any(): raise ValueError('Predictors require explicit types and no missing values')
        if spec['type']=='numeric':
            columns[key]=[_finite(x) for x in meta[key]];groups[key]=[key]
        else:
            levels=sorted(set(meta[key]));ref=spec.get('reference')
            if not 2<=len(levels)<=30 or ref not in levels: raise ValueError('Declare a categorical reference level')
            if meta[key].value_counts().min()<3: raise ValueError('Each categorical level requires at least three independent observations in this adapter')
            names=[]
            for value in levels:
                if value!=ref:
                    name=key+'['+value+']';columns[name]=(meta[key]==value).astype(float);names.append(name)
            groups[key]=names;encodings[key]={'levels':levels,'reference':ref}
    for pair in interactions or []:
        if not isinstance(pair,list) or len(pair)!=2 or pair[0]==pair[1] or not set(pair)<=set(predictors): raise ValueError('Interactions must name two distinct declared predictors')
        for left in groups[pair[0]]:
            for right in groups[pair[1]]:
                name=left+':'+right
                if name in columns: raise ValueError('Duplicate interaction')
                columns[name]=np.asarray(columns[left])*np.asarray(columns[right])
    if len(columns)!=len(set(columns)): raise ValueError('Encoded coefficient name collision')
    x=pd.DataFrame(columns,index=meta.index,dtype=float);x.insert(0,'Intercept',1.)
    if x.shape[1]>50 or np.linalg.matrix_rank(x)!=x.shape[1] or len(x)-x.shape[1]<3: raise ValueError('Confounded, oversized or saturated design')
    return x,encodings


@_workflow
def run_designed_expression(matrix_path: str, metadata_path: str, matrix_kind: str, unit_key: str, predictors: dict, contrast_weights: dict, context: dict, interactions: list = None, method: str = 'limma_ebayes', rscript: str = 'Rscript', min_count: int = 10, min_samples: int = 3) -> dict:
    """Design-aware limma/voom/edgeR expression analysis with continuous covariates, explicit reference levels, interactions and one numeric contrast."""
    require_local();_context(context)
    if matrix_kind not in {'raw_counts','log2_normalized'} or method not in {'limma_ebayes','limma_voom','edgeR_ql'} or (matrix_kind=='raw_counts')!=(method!='limma_ebayes'): raise ValueError('Match declared input scale to an appropriate backend')
    matrix,meta=_frames(matrix_path,metadata_path,matrix_kind=='raw_counts');_capacity(matrix,'bulk')
    if unit_key not in meta or meta[unit_key].eq('').any() or meta[unit_key].duplicated().any(): raise ValueError('This adapter requires one observation per independent unit; use an explicit mixed-model server workflow for repetition')
    x,encodings=_design(meta,predictors,interactions)
    from statistics_ext import _finite
    import numpy as np
    import pandas as pd
    if not isinstance(contrast_weights,dict) or not contrast_weights or not set(contrast_weights)<=set(x.columns): raise ValueError('Contrast weights must name encoded coefficients')
    weights=np.array([_finite(contrast_weights.get(k,0)) for k in x.columns])
    if np.all(weights==0): raise ValueError('Zero contrast is not a test')
    from qc_ext import qc_frames
    qc=qc_frames(matrix,meta,{'matrix':matrix_path,'metadata':metadata_path},matrix_kind,context,{'predictors':predictors,'interactions':interactions or [],'contrast':contrast_weights,'independent_units':len(meta)})
    if not qc['qc_gate_pass']: raise ValueError('Preanalysis QC blocked formal fit: '+qc['report_file'])
    keep=(matrix>=min_count).sum(axis=1)>=min_samples if matrix_kind=='raw_counts' else matrix.var(axis=1)>0
    if not 1<=min_count<=10000 or not 3<=min_samples<=len(meta) or keep.sum()<20: raise ValueError('Invalid filter or fewer than twenty eligible genes')
    folder=_folder('designed_expression');matrix.loc[keep].to_csv(folder/'expression.csv');x.to_csv(folder/'design_matrix.csv')
    pd.DataFrame({'weight':weights},index=x.columns).to_csv(folder/'contrast.csv');pd.DataFrame({'kept':keep}).to_csv(folder/'gene_filter.csv')
    from software_ext import resolve
    executable=resolve('rscript',rscript)
    with (folder/'backend.log').open('w',encoding='utf8') as log:
        p=subprocess.run([executable,'--vanilla',str(Path(__file__).parent/'designed_expression.R'),str(folder),method],stdout=log,stderr=subprocess.STDOUT,timeout=600,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),env={**os.environ,'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'})
    if p.returncode: raise RuntimeError('Expression backend failed; inspect backend.log')
    results=pd.read_csv(folder/'differential_expression.csv',index_col=0)
    from transcriptomics_ext import _plots
    expression=pd.read_csv(folder/'exploratory_expression.csv',index_col=0);_plots(expression,results,folder)
    return _finish(folder,{'workflow':'designed_expression','method':method,'contrast_weights':contrast_weights,'contrast_description':context['contrast'],'encodings':encodings,'predictors':predictors,'interactions':interactions or [],'independent_units':len(meta),'preanalysis_qc':qc,'backend_version':(folder/'backend_version.txt').read_text().strip(),'input_hashes':_hashes(matrix=matrix_path,metadata=metadata_path),'context':context,'limitations':['Numeric interactions and reference levels must match the scientific estimand.','An interaction contrast is not necessarily a simple case/control fold change.','No automatic batch correction, covariate selection or causal inference.','One observation per independent unit only; repeated measurements require another backend.']})


@_workflow
def import_expression_data(input_path: str, input_format: str, context: dict, layer: str = '', tenx_directory: str = '') -> dict:
    """Convert bounded H5AD raw-count layers or 10x MTX directories to gene-by-cell CSV; preserve IDs and reject guessed count provenance."""
    require_local();_context(context)
    import numpy as np
    import pandas as pd
    import anndata as ad
    if input_format=='h5ad':
        source=Path(input_path).resolve(strict=True)
        if source.stat().st_size>200000000 or not layer: raise ValueError('Provide a bounded H5AD and an explicit raw-count layer name (X is allowed only when source provenance declares raw counts)')
        data=ad.read_h5ad(source,backed='r')
        try:
            from transcriptomics_ext import inspect_local_compute
            if not inspect_local_compute(data.n_vars,data.n_obs,'single_cell')['local_gate_pass']: raise ValueError('Large matrix belongs on server')
            matrix=data.X if layer=='X' else data.layers[layer]
            cells=list(data.obs_names);genes=list(data.var_names);meta=data.obs.copy()
            if hasattr(matrix,'to_memory'): matrix=matrix.to_memory()
            array=matrix.toarray() if hasattr(matrix,'toarray') else np.asarray(matrix)
        finally: data.file.close()
        hashes=_hashes(source=input_path)
    elif input_format=='10x_mtx':
        from scipy.io import mmread
        import gzip
        directory=Path(tenx_directory or input_path).resolve(strict=True)
        selected=[]
        for base in ['matrix.mtx','features.tsv','barcodes.tsv']:
            p=directory/base
            if not p.is_file(): p=directory/(base+'.gz')
            if not p.is_file() or p.stat().st_size>100000000: raise ValueError('Missing or oversized 10x input')
            selected.append(p)
        def lines(p):
            opener=gzip.open if p.suffix=='.gz' else open
            with opener(p,'rt',encoding='utf8') as f:
                out=[];total=0
                for line in f:
                    total+=len(line)
                    if total>100000000 or len(out)>100000: raise ValueError('Expanded 10x metadata exceeds limits')
                    out.append(line.rstrip('\n').split('\t'))
                return out
        features=lines(selected[1]);barcodes=lines(selected[2]);genes=[x[0] for x in features];cells=[x[0] for x in barcodes]
        if any(len(x)>=3 and x[2]!='Gene Expression' for x in features): raise ValueError('Select gene-expression features explicitly; mixed feature modalities are unsupported')
        from transcriptomics_ext import inspect_local_compute
        if not inspect_local_compute(len(genes),len(cells),'single_cell')['local_gate_pass']: raise ValueError('10x dimensions route to server')
        # Read only bounded expanded bytes, then validate declared matrix dimensions before allocation.
        import io
        opener=gzip.open if selected[0].suffix=='.gz' else open
        with opener(selected[0],'rb') as f: raw=f.read(200000001)
        if len(raw)>200000000: raise ValueError('Expanded MTX exceeds local limit')
        dimensions=next((line for line in raw.splitlines()[1:] if line.strip() and not line.startswith(b'%')),b'')
        dims=[int(x) for x in dimensions.split()]
        if len(dims)!=3 or dims[:2]!=[len(genes),len(cells)] or dims[2]>20000000: raise ValueError('MTX dimensions disagree with metadata or exceed limits')
        matrix=mmread(io.BytesIO(raw));array=matrix.toarray().T if hasattr(matrix,'toarray') else np.asarray(matrix).T;meta=pd.DataFrame(index=cells)
        hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in selected}
    else: raise ValueError('Supported inputs are h5ad or 10x_mtx; CSV already has a direct analysis route')
    if len(set(cells))!=len(cells) or len(set(genes))!=len(genes) or any(not x for x in cells+genes): raise ValueError('Identifiers must be nonempty and unique; no automatic renaming')
    if array.shape!=(len(cells),len(genes)) or not np.isfinite(array).all() or (array<0).any() or (array!=np.floor(array)).any() or array.max()>2147483647: raise ValueError('Declared raw layer is not a bounded finite nonnegative integer count matrix')
    from transcriptomics_ext import inspect_local_compute
    if not inspect_local_compute(len(genes),len(cells),'single_cell')['local_gate_pass']: raise ValueError('Input routes to server')
    folder=_folder('expression_import');pd.DataFrame(array.T,index=genes,columns=cells).to_csv(folder/'counts.csv');meta.to_csv(folder/'metadata.csv')
    return _finish(folder,{'workflow':'expression_import','input_format':input_format,'layer':layer,'genes':len(genes),'cells':len(cells),'input_hashes':hashes,'context':context,'limitations':['Integer values do not prove raw-count provenance; review source processing.','10x feature IDs are retained; symbols are not silently substituted.','Add and verify biological-unit/condition/cell-type metadata before formal inference.']})


@_workflow
def analyze_cell_composition(metadata_path: str, unit_key: str, condition_key: str, cell_type_key: str, context: dict, min_cells: int = 20) -> dict:
    """Aggregate cell composition at the independent-unit level with explicit denominators; descriptive proportions, not cell-level inference."""
    require_local();_context(context)
    h,r=_read(metadata_path)
    import pandas as pd
    meta=pd.DataFrame([x[1:] for x in r],index=[x[0] for x in r],columns=h[1:])
    if len(meta)>100000 or not {unit_key,condition_key,cell_type_key}<=set(meta) or min_cells<1: raise ValueError('Provide bounded cell metadata and explicit unit/condition/type columns')
    if meta[[unit_key,condition_key,cell_type_key]].eq('').any().any(): raise ValueError('Missing labels require annotation review')
    if meta.groupby(unit_key)[condition_key].nunique().max()>1: raise ValueError('Repeated-condition units require a repeated composition model')
    table=meta.groupby([unit_key,condition_key,cell_type_key]).size().unstack(fill_value=0)
    total=table.sum(axis=1);proportions=table.div(total,axis=0);folder=_folder('cell_composition')
    table.to_csv(folder/'cell_counts.csv');proportions.to_csv(folder/'cell_proportions.csv');pd.DataFrame({'total_cells':total,'eligible':total>=min_cells}).to_csv(folder/'unit_qc.csv')
    return _finish(folder,{'workflow':'cell_composition','independent_units':len(table),'cell_types':len(table.columns),'min_cells':min_cells,'excluded_low_cell_units':int((total<min_cells).sum()),'context':context,'input_hashes':_hashes(metadata=metadata_path),'limitations':['Proportions depend on capture and annotation; denominator changes can induce apparent differences.','Zero observed cells do not prove biological absence.','No p-values are computed; group inference needs a design-aware compositional model.']})


@_workflow
def score_regulatory_activity(expression_path: str, metadata_path: str, network_path: str, context: dict, min_targets: int = 5) -> dict:
    """Score signed weighted target expression after within-sample gene standardization; retain coverage, no significance or causal activity claim."""
    require_local();_context(context)
    for key in ['network_source','network_version','gene_namespace']:
        if not context.get(key): raise ValueError('Record regulatory network source/version/namespace')
    if not 5<=min_targets<=1000: raise ValueError('min_targets must be 5..1000')
    matrix,meta=_frames(expression_path,metadata_path,False);_capacity(matrix,'normalized')
    h,r=_read(network_path)
    if not {'regulator','target','weight'}<=set(h[1:]) or len(r)>100000: raise ValueError('Network needs unique edge IDs and regulator,target,weight columns')
    import numpy as np
    import pandas as pd
    network=pd.DataFrame([x[1:] for x in r],columns=h[1:]);network.weight=network.weight.astype(float)
    if not np.isfinite(network.weight).all() or (network.weight==0).any() or network[['regulator','target']].eq('').any().any() or network.duplicated(['regulator','target']).any(): raise ValueError('Invalid or duplicated weighted regulatory edges')
    sd=matrix.std(axis=0,ddof=1)
    if (sd==0).any(): raise ValueError('Constant expression sample')
    z=matrix.sub(matrix.mean(axis=0),axis=1).div(sd,axis=1);coverage=[];scores={}
    for reg,edges in network.groupby('regulator'):
        matched=edges[edges.target.isin(matrix.index)];eligible=len(matched)>=min_targets
        coverage.append({'regulator':reg,'total_targets':len(edges),'measured_targets':len(matched),'eligible':eligible})
        if eligible: scores[reg]=(z.loc[matched.target].to_numpy()*matched.weight.to_numpy()[:,None]).sum(axis=0)/matched.weight.abs().sum()
    if not scores: raise ValueError('No regulator passes target coverage')
    folder=_folder('regulatory_activity');pd.DataFrame(scores,index=matrix.columns).T.to_csv(folder/'regulatory_scores.csv');pd.DataFrame(coverage).to_csv(folder/'coverage.csv',index=False)
    return _finish(folder,{'workflow':'signed_weighted_regulatory_score','regulators':len(scores),'context':context,'input_hashes':_hashes(expression=expression_path,metadata=metadata_path,network=network_path),'limitations':['This is a descriptive signed weighted score, not decoupler ULM/MLM or a statistical test.','Gene-wise target dependence and network uncertainty are not modeled.','Expression of targets does not establish regulator activation or causality.','Scores depend on the measured gene universe; compare matched pipelines, not arbitrary datasets.']})


def summarize_pathway_overlap(gene_sets_path: str, selected_terms: list, threshold: float = 0.5, leading_edges: dict = None) -> dict:
    """Describe selected pathway redundancy and explicit leading-edge genes; no automatic deletion or re-ranking of enrichment tests."""
    from omics_ext import _gene_sets
    sets=_gene_sets(gene_sets_path)
    if not 1<=len(selected_terms)<=200 or len(set(selected_terms))!=len(selected_terms) or not set(selected_terms)<=set(sets) or not 0<threshold<=1: raise ValueError('Select up to 200 distinct known terms and a Jaccard threshold')
    pairs=[]
    for i,a in enumerate(selected_terms):
        for b in selected_terms[i+1:]:
            x,y=set(sets[a]),set(sets[b]);j=len(x&y)/len(x|y) if x|y else 0.
            if j>=threshold: pairs.append({'term1':a,'term2':b,'jaccard':j,'shared_genes':sorted(x&y)})
    for term,genes in (leading_edges or {}).items():
        if term not in selected_terms or not isinstance(genes,list) or not set(genes)<=set(sets[term]): raise ValueError('Leading edges must be explicit genes belonging to selected sets')
    return {'success':True,'pairs_above_threshold':pairs,'leading_edges':leading_edges or {},'input_sha256':hashlib.sha256(Path(gene_sets_path).read_bytes()).hexdigest(),'limitations':['Overlap is descriptive; redundant terms are retained and not silently removed from multiplicity families.','Leading edges must come from the actual enrichment result; they are not inferred from set overlap.']}


@_workflow
def audit_network_stability(edges_path: str, context: dict, thresholds: list, resolutions: list = None, seed: int = 42, null_permutations: int = 0) -> dict:
    """Measure PPI threshold/community sensitivity and optional degree-preserving modularity nulls with fixed nodes; synthetic nulls are not biological replication."""
    require_local();_context(context)
    import networkx as nx
    import numpy as np
    import pandas as pd
    from sklearn.metrics import adjusted_rand_score
    h,r=_read(edges_path)
    if not {'source','target','score'}<=set(h[1:]) or len(r)>10000 or not 1<=len(thresholds)<=8 or any(not 0<x<=1 for x in thresholds): raise ValueError('Provide bounded edges and 1..8 confidence thresholds')
    resolutions=resolutions or [1.]
    if not 1<=len(resolutions)<=5 or any(not 0<x<=5 for x in resolutions) or type(null_permutations) is not int or not 0<=null_permutations<=20: raise ValueError('Invalid community/null settings')
    base=nx.Graph();excluded=0
    for row in r:
        d=dict(zip(h,row));v=float(d['score']);a,b=d['source'],d['target']
        if not math.isfinite(v) or not 0<=v<=1 or not a or not b: raise ValueError('Invalid edge')
        if a==b: excluded+=1;continue
        base.add_edge(a,b,weight=max(v,base.get_edge_data(a,b,{}).get('weight',0)))
    if len(base)>2000: raise ValueError('Large network belongs on server')
    nodes=sorted(base);rows=[];partitions={};nulls=[]
    for threshold in thresholds:
        g=nx.Graph();g.add_nodes_from(nodes);g.add_edges_from((a,b,d) for a,b,d in base.edges(data=True) if d['weight']>=threshold)
        for resolution in resolutions:
            communities=nx.community.louvain_communities(g,weight='weight',resolution=resolution,seed=seed) if g.number_of_edges() else [{n} for n in nodes]
            labels={n:i for i,c in enumerate(communities) for n in c};key=str(threshold)+':'+str(resolution);partitions[key]=[labels[n] for n in nodes]
            modularity=nx.community.modularity(g,communities,weight='weight',resolution=resolution) if g.number_of_edges() else None
            rows.append({'setting':key,'nodes':len(g),'edges':g.number_of_edges(),'isolates':len(list(nx.isolates(g))),'communities':len(communities),'modularity':modularity})
            if null_permutations and g.number_of_edges()>=4 and len(g)>=4:
                # Unweighted null avoids assigning confidence weights to artificial edges.
                observed=nx.community.modularity(g,communities,weight=None,resolution=resolution)
                values=[];failed=0
                for i in range(null_permutations):
                    surrogate=nx.Graph(g)
                    try: nx.double_edge_swap(surrogate,nswap=min(1000,2*g.number_of_edges()),max_tries=max(100,20*g.number_of_edges()),seed=seed+i)
                    except (nx.NetworkXAlgorithmError,nx.NetworkXError): failed+=1;continue
                    cc=nx.community.louvain_communities(surrogate,weight=None,resolution=resolution,seed=seed+i)
                    values.append(nx.community.modularity(surrogate,cc,weight=None,resolution=resolution))
                nulls.append({'setting':key,'observed_unweighted_modularity':observed,'null_values':values,'failed_permutations':failed,'empirical_p':(1+sum(v>=observed for v in values))/(1+len(values)) if values else None})
    agreement=[{'setting1':a,'setting2':b,'ARI':float(adjusted_rand_score(partitions[a],partitions[b]))} for i,a in enumerate(partitions) for b in list(partitions)[i+1:]]
    folder=_folder('network_stability');pd.DataFrame(rows).to_csv(folder/'settings.csv',index=False);pd.DataFrame(agreement).to_csv(folder/'partition_agreement.csv',index=False)
    return _finish(folder,{'workflow':'network_stability','excluded_self_edges':excluded,'fixed_node_universe':len(nodes),'nulls':nulls,'seed':seed,'context':context,'input_hashes':_hashes(edges=edges_path),'limitations':['Threshold stability is sensitivity analysis, not independent validation.','Degree-preserving nulls test a limited graph property and do not establish mechanistic modules.','Few null permutations give coarse p-values; failed swaps are retained.','Node selection, database coverage and confidence calibration remain external assumptions.']})


def audit_redocking_coordinates(reference_path: str, predicted_path: str, atom_mapping: list, same_coordinate_frame: bool) -> dict:
    """Compute heavy-atom RMSD against an explicit reference using reviewed atom correspondences in the same receptor frame; no silent alignment or symmetry guessing."""
    if same_coordinate_frame is not True or not isinstance(atom_mapping,list) or not 3<=len(atom_mapping)<=300: raise ValueError('Explicit same-frame confirmation and 3..300 mapped heavy atoms are required')
    def atoms(path):
        p=Path(path).resolve(strict=True)
        if p.stat().st_size>10000000: raise ValueError('Structure exceeds limit')
        result={};models=0
        for line in p.read_text(encoding='utf8').splitlines():
            if line.startswith('MODEL'): models+=1
            if models>1: break
            if line.startswith(('ATOM  ','HETATM')):
                key=line[6:11].strip();element=line[76:78].strip().upper() or line[12:16].strip()[0].upper()
                if element.startswith('H'): continue
                xyz=[float(line[a:b]) for a,b in [(30,38),(38,46),(46,54)]]
                if key in result or not all(math.isfinite(v) for v in xyz): raise ValueError('Duplicate atom serial or nonfinite coordinates')
                result[key]=xyz
        return result
    ref,pred=atoms(reference_path),atoms(predicted_path);seen1=set();seen2=set();squared=[]
    for pair in atom_mapping:
        if not isinstance(pair,list) or len(pair)!=2: raise ValueError('Atom mapping is a list of reference/prediction serial pairs')
        a,b=map(str,pair)
        if a not in ref or b not in pred or a in seen1 or b in seen2: raise ValueError('Mapping must be one-to-one over present heavy atoms')
        seen1.add(a);seen2.add(b);squared.append(sum((x-y)**2 for x,y in zip(ref[a],pred[b])))
    return {'success':True,'heavy_atom_rmsd_angstrom':math.sqrt(sum(squared)/len(squared)),'mapped_atoms':len(squared),'reference_atoms':len(ref),'predicted_atoms':len(pred),'reference_coverage':len(seen1)/len(ref),'predicted_coverage':len(seen2)/len(pred),'input_hashes':_hashes(reference=reference_path,predicted=predicted_path),'limitations':['Only the first predicted model is inspected.','A partial mapping is not full-ligand redocking validation; inspect coverage.','Caller must verify atom chemistry, equivalent atoms, protonation and common receptor frame.','No universal pass threshold or binding-affinity claim is inferred from RMSD.']}


def audit_md_summary(path: str, time_key: str, metric_ranges: dict, window: list, block_width: float, time_unit: str) -> dict:
    """Audit returned MD summary time series and block stability; frames and blocks are not declared independent simulation replicates."""
    from workflow_ext import _table,_hash
    h,rows=_table(path,20000000)
    from statistics_ext import _finite
    if time_key not in h or not set(metric_ranges)<=set(h) or not metric_ranges or len(rows)>100000 or len(window)!=2 or not window[0]<window[1] or block_width<=0 or not time_unit: raise ValueError('Declare metrics, review ranges, time window and block width')
    times=[_finite(r[time_key]) for r in rows]
    if any(b<=a for a,b in zip(times,times[1:])): raise ValueError('Time must increase strictly; duplicate or concatenated segments need review')
    selected=[r for r,t in zip(rows,times) if window[0]<=t<=window[1]]
    if len(selected)<10: raise ValueError('Too few selected frames for a stability summary')
    summaries={};issues=[]
    for key,bounds in metric_ranges.items():
        if len(bounds)!=2 or not bounds[0]<bounds[1]: raise ValueError('Declare increasing review bounds')
        values=[_finite(r[key]) for r in selected];blocks={}
        for r,value in zip(selected,values):
            index=math.floor((_finite(r[time_key])-window[0])/block_width);blocks.setdefault(index,[]).append(value)
        means=[{'block':i,'frames':len(v),'mean':sum(v)/len(v)} for i,v in sorted(blocks.items())]
        outside=sum(not bounds[0]<=v<=bounds[1] for v in values)
        if outside: issues.append(key+':outside_declared_review_range')
        summaries[key]={'mean':sum(values)/len(values),'min':min(values),'max':max(values),'outside_review_range':outside,'block_means':means}
    deltas=[b-a for a,b in zip(times,times[1:])]
    return {'success':True,'review_gate_pass':not issues,'issues':issues,'time_unit':time_unit,'window':window,'selected_frames':len(selected),'step_min':min(deltas) if deltas else None,'step_max':max(deltas) if deltas else None,'metrics':summaries,'input_sha256':_hash(path),'limitations':['Metric units and scientifically justified bounds are supplied by the caller.','Blocks are descriptive; independence, convergence and effective sample size are not established.','A stable RMSD alone does not establish adequate sampling or binding.','Compare multiple independent simulations separately; do not treat MD frames as biological replicates.']}


def audit_batch_embedding(embedding_path: str, metadata_path: str, batch_key: str, biology_key: str) -> dict:
    """Inspect bounded embedding batch/biology silhouettes and batch-label confounding; descriptive integration diagnostics only."""
    require_local()
    import pandas as pd
    import numpy as np
    from sklearn.metrics import silhouette_score
    h,r=_read(embedding_path,True);mh,mr=_read(metadata_path)
    x=pd.DataFrame([v[1:] for v in r],index=[v[0] for v in r]);meta=pd.DataFrame([v[1:] for v in mr],index=[v[0] for v in mr],columns=mh[1:])
    if len(x)>10000 or x.shape[1]>100 or set(x.index)!=set(meta.index) or not {batch_key,biology_key}<=set(meta): raise ValueError('Provide matched bounded embedding and curated metadata')
    meta=meta.loc[x.index];table=pd.crosstab(meta[batch_key],meta[biology_key]);confounded=bool((table.gt(0).sum(axis=0)==1).all())
    scores={}
    for key in [batch_key,biology_key]:
        labels=meta[key]
        scores[key]=float(silhouette_score(x,labels,sample_size=min(2000,len(x)),random_state=42)) if 1<labels.nunique()<len(x) else None
    return {'success':True,'silhouette':scores,'batch_biology_table':table.to_dict(),'complete_label_confounding':confounded,'input_hashes':_hashes(embedding=embedding_path,metadata=metadata_path),'limitations':['Silhouettes are descriptive and depend on embedding geometry, sampling and cell composition.','Good batch mixing can erase real biology; evaluate before and after integration.','Confounded labels cannot identify batch and biological effects from this dataset alone.','This tool performs no integration or automatic cell annotation.']}


@_workflow
def run_donor_differential_state(counts_path: str, metadata_path: str, unit_key: str, condition_key: str, cell_type_key: str, cell_types: list, case: str, control: str, context: dict, method: str = 'edgeR_ql', min_cells: int = 20, paired: bool = False, covariates: list = None) -> dict:
    """Execute donor-level pseudobulk and differential expression for explicitly curated cell types; retain failed/low-coverage types and a combined test family."""
    require_local();_context(context)
    if not isinstance(cell_types,list) or not 1<=len(cell_types)<=10 or len(set(cell_types))!=len(cell_types): raise ValueError('Select 1..10 distinct curated cell types')
    from transcriptomics_ext import aggregate_pseudobulk,run_bulk_rnaseq
    import pandas as pd
    outcomes=[];tables=[]
    for cell_type in cell_types:
        try:
            aggregate=aggregate_pseudobulk(counts_path,metadata_path,unit_key,condition_key,cell_type_key,cell_type,context,min_cells,covariates)
            directory=Path(aggregate['output_directory'])
            analysis=run_bulk_rnaseq(str(directory/'counts.csv'),str(directory/'metadata.csv'),'condition','unit',case,control,context,paired=paired,covariates=covariates,method=method,threads=2)
            tab=pd.read_csv(Path(analysis['output_directory'])/'differential_expression.csv',index_col=0);tab['cell_type']=cell_type;tables.append(tab)
            outcomes.append({'cell_type':cell_type,'state':'succeeded','aggregation_report':aggregate['report_file'],'analysis_report':analysis['report_file']})
        except (ValueError,RuntimeError) as exc:
            outcomes.append({'cell_type':cell_type,'state':'failed','error':str(exc)})
    folder=_folder('donor_differential_state')
    if tables:
        combined=pd.concat(tables);valid=combined.pvalue.notna()
        from statistics_ext import adjust_pvalues
        combined['padj_across_tested_cell_types']=float('nan')
        if valid.any(): combined.loc[valid,'padj_across_tested_cell_types']=adjust_pvalues(combined.loc[valid,'pvalue'].tolist(),'all successfully tested gene by selected cell type hypotheses')['adjusted_pvalues']
        combined.to_csv(folder/'all_cell_type_tests.csv')
    return _finish(folder,{'workflow':'donor_differential_state','outcomes':outcomes,'all_requested_types_succeeded':all(x['state']=='succeeded' for x in outcomes),'completed_types':len(tables),'context':context,'input_hashes':_hashes(counts=counts_path,metadata=metadata_path),'limitations':['Cell types must be curated and independently reviewed; automatic identities are not assigned.','Repeated cells are aggregated; donors define independent units.','Failed cell types remain visible and reduce coverage; completed types are not an exhaustive atlas.','Per-type and across-tested-type BH columns describe different families; failed hypotheses are not successful null results.']})


@_workflow
def infer_diffusion_pseudotime(h5ad_path: str, root_cells: list, unit_key: str, context: dict) -> dict:
    """Run exploratory Scanpy diffusion pseudotime on an existing QC-reviewed neighbor graph with explicit root-cell sensitivity."""
    require_local();_context(context)
    import anndata as ad
    import scanpy as sc
    import numpy as np
    import pandas as pd
    from scipy.stats import spearmanr
    p=Path(h5ad_path).resolve(strict=True)
    if p.stat().st_size>200000000: raise ValueError('Large trajectory task belongs on server')
    data=ad.read_h5ad(p)
    if data.n_obs>10000 or data.n_obs*data.n_vars>20000000 or unit_key not in data.obs or data.obs[unit_key].isna().any() or 'neighbors' not in data.uns or 'connectivities' not in data.obsp: raise ValueError('Provide a bounded, QC-reviewed neighbor graph with independent-unit metadata')
    if not 1<=len(root_cells)<=5 or len(set(root_cells))!=len(root_cells) or not set(root_cells)<=set(data.obs_names): raise ValueError('Provide 1..5 reviewed root cells')
    if data.n_obs<20: raise ValueError('Too few cells for this exploratory trajectory adapter')
    sc.tl.diffmap(data,n_comps=min(10,data.n_obs-2),random_state=42);results={}
    for root in root_cells:
        data.uns['iroot']=int(data.obs_names.get_loc(root));sc.tl.dpt(data,n_dcs=min(9,data.obsm['X_diffmap'].shape[1]-1),n_branchings=0)
        values=data.obs.dpt_pseudotime.to_numpy();results[root]=values
    folder=_folder('diffusion_pseudotime');table=pd.DataFrame(results,index=data.obs_names);table.to_csv(folder/'root_sensitivity.csv');data.obs.to_csv(folder/'cell_metadata.csv')
    agreements=[]
    for i,a in enumerate(root_cells):
        for b in root_cells[i+1:]:
            valid=np.isfinite(table[a])&np.isfinite(table[b]);corr=float(spearmanr(table.loc[valid,a],table.loc[valid,b]).statistic) if valid.sum()>3 and table.loc[valid,a].nunique()>1 and table.loc[valid,b].nunique()>1 else None
            agreements.append({'root1':a,'root2':b,'finite_shared_cells':int(valid.sum()),'spearman':corr})
    return _finish(folder,{'workflow':'diffusion_pseudotime','roots':root_cells,'root_agreement':agreements,'unreachable_cells':{k:int((~np.isfinite(v)).sum()) for k,v in results.items()},'context':context,'input_hashes':_hashes(h5ad=h5ad_path),'limitations':['Pseudotime is not observed time, lineage tracing or a causal trajectory.','Disconnected cells may have infinite distances and are retained as unreachable.','Root choice and neighborhood construction influence ordering; donor consistency needs further review.','No condition-level inference treats cells as independent replicates.']})


def audit_cell_communication(records: list, conditions: list, min_donors: int = 3) -> dict:
    """Review returned ligand/receptor communication scores for donor coverage and provenance; expression scores do not establish signaling."""
    if not isinstance(records,list) or not 1<=len(records)<=10000 or not 2<=len(conditions)<=5 or min_donors<3: raise ValueError('Provide bounded donor-level scores and explicit conditions')
    from statistics_ext import _finite
    required={'donor','condition','sender','receiver','ligand','receptor','score','source','method'};groups={};seen=set()
    for row in records:
        if not required<=set(row) or any(not str(row[k]).strip() for k in required) or row['condition'] not in conditions: raise ValueError('Missing donor/condition/pair/method provenance')
        key=(row['sender'],row['receiver'],row['ligand'],row['receptor'],row['method'],row['source']);unique=(key,row['donor'],row['condition'])
        if unique in seen: raise ValueError('Duplicated donor-level pair result')
        seen.add(unique);groups.setdefault(key,{}).setdefault(row['condition'],[]).append((row['donor'],_finite(row['score'])))
    reports=[]
    for key,values in groups.items():
        coverage={g:len({u for u,v in values.get(g,[])}) for g in conditions};issues=[]
        if min(coverage.values())<min_donors: issues.append('insufficient_donor_coverage')
        donor_sets=[{u for u,v in values.get(g,[])} for g in conditions]
        if any(donor_sets[i]&donor_sets[j] for i in range(len(donor_sets)) for j in range(i+1,len(donor_sets))): issues.append('paired_or_repeated_donors_need_explicit_model')
        reports.append({'pair':key,'donor_coverage':coverage,'group_mean_scores':{g:sum(v for u,v in values[g])/len(values[g]) if values.get(g) else None for g in conditions},'issues':issues,'eligible_for_independent_donor_comparison':not issues})
    return {'success':True,'pairs':reports,'limitations':['Scores from different methods or scales are not pooled.','Ligand/receptor expression or inferred communication does not establish physical interaction or functional signaling.','Cell abundance, annotation and capture biases need separate review.','This reviews returned results and does not execute a communication inference package.']}


def evaluate_binary_prediction(records: list, outcome_key: str, probability_key: str, unit_key: str, threshold: float, split_review: dict) -> dict:
    """Evaluate independent validation predictions with discrimination, Brier score, fixed-threshold counts and calibration bins after an explicit split audit."""
    require_local()
    import numpy as np
    from sklearn.metrics import roc_auc_score,average_precision_score,brier_score_loss
    from statistics_ext import _finite
    if not isinstance(split_review,dict) or split_review.get('leakage_gate_pass') is not True or not 10<=len(records)<=10000 or not 0<threshold<1: raise ValueError('A passed independent-unit split review and explicit threshold are required')
    units=[r[unit_key] for r in records]
    if len(set(units))!=len(units) or any(not isinstance(u,str) or not u for u in units): raise ValueError('Validation rows require distinct nonempty independent units')
    fingerprint=hashlib.sha256(json.dumps(sorted(set(units)),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    if split_review.get('unit_set_hashes',{}).get('validation')!=fingerprint: raise ValueError('Prediction units do not match the audited validation split')
    y=np.array([_finite(r[outcome_key]) for r in records]);p=np.array([_finite(r[probability_key]) for r in records])
    if set(y)!={0.,1.} or (p<0).any() or (p>1).any(): raise ValueError('Provide both binary classes and probabilities in [0,1]')
    pred=p>=threshold;bins=[]
    for i in range(10):
        mask=(p>=i/10)&((p<(i+1)/10) if i<9 else (p<=1))
        bins.append({'lower':i/10,'upper':(i+1)/10,'n':int(mask.sum()),'mean_probability':float(p[mask].mean()) if mask.any() else None,'observed_fraction':float(y[mask].mean()) if mask.any() else None})
    tp=int(((y==1)&pred).sum());fn=int(((y==1)&~pred).sum());tn=int(((y==0)&~pred).sum());fp=int(((y==0)&pred).sum())
    return {'success':True,'independent_units':len(y),'prevalence':float(y.mean()),'roc_auc':float(roc_auc_score(y,p)),'average_precision':float(average_precision_score(y,p)),'brier_score':float(brier_score_loss(y,p)),'threshold':threshold,'confusion_counts':{'TP':tp,'FN':fn,'TN':tn,'FP':fp},'sensitivity':tp/(tp+fn),'specificity':tn/(tn+fp),'calibration_bins':bins,'limitations':['A passed split review does not verify the truth of supplied provenance or IDs.','No threshold optimization is performed on validation outcomes.','Metrics without uncertainty and external validation do not establish deployable clinical performance.','Calibration bins are descriptive and can be unstable with small validation samples.']}


def audit_colocalization_results(records: list, min_variant_coverage: float = 0.9) -> dict:
    """Audit returned colocalization evidence for assembly, locus coverage, priors, tissue, signal model and posterior consistency; no gene causality inferred."""
    if not isinstance(records,list) or not 1<=len(records)<=1000 or not 0<min_variant_coverage<=1: raise ValueError('Provide bounded colocalization records')
    results=[]
    for row in records:
        required={'locus','assembly1','assembly2','trait1','trait2','tissue','method','signal_model','matched_variants','variants_trait1','variants_trait2','priors','posterior','source'}
        issues=[]
        if not required<=set(row):
            results.append({'locus':row.get('locus'),'eligible_for_interpretation':False,'issues':['missing_required_context']});continue
        if row['assembly1']!=row['assembly2']: issues.append('assembly_mismatch')
        matched=int(row['matched_variants']);n1=int(row['variants_trait1']);n2=int(row['variants_trait2'])
        if min(n1,n2,matched)<1 or matched>min(n1,n2): raise ValueError('Invalid variant coverage counts')
        coverage=min(matched/n1,matched/n2)
        if coverage<min_variant_coverage: issues.append('incomplete_locus_variant_coverage')
        posterior=row['posterior']
        if set(posterior)!={'H0','H1','H2','H3','H4'} or any(not 0<=float(x)<=1 or not math.isfinite(float(x)) for x in posterior.values()) or abs(sum(map(float,posterior.values()))-1)>1e-5: issues.append('invalid_posterior_probabilities')
        if not isinstance(row['priors'],dict) or not {'p1','p2','p12'}<=set(row['priors']) or any(not 0<float(v)<1 for v in row['priors'].values()): issues.append('missing_or_invalid_priors')
        if row['signal_model'] not in {'single_causal_variant','multiple_signals_LD'}: issues.append('unspecified_signal_assumption')
        if not row['source'] or not row['tissue']: issues.append('missing_source_or_tissue')
        results.append({'locus':row['locus'],'coverage':coverage,'posterior':posterior,'issues':issues,'eligible_for_interpretation':not issues})
    return {'success':True,'records':results,'limitations':['This inspects returned posteriors and context; it does not run coloc or SuSiE.','A high H4 depends on priors, signal assumptions and dense locus coverage; perform prior sensitivity.','Colocalization does not establish tissue specificity, mediation or a causal gene.','For multiple signals inspect LD ancestry, reference compatibility and conditional analysis.']}
