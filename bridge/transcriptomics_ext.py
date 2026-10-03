"""Bounded local transcriptomics with explicit scale, design and biological units."""
import csv
import hashlib
import html
import json
import math
import re
import shutil
import subprocess
import uuid
import warnings
from pathlib import Path
from importlib.metadata import version
from contextvars import ContextVar
from functools import wraps

from compute_policy import require_local

HERE = Path(__file__).resolve().parent
LIMIT_ENTRIES = 20000000
LIMIT_BYTES = 200000000
CONTEXT = {'species','model','assay','biological_unit','contrast','limitations','input_source','input_processing'}
CURRENT_FOLDER = ContextVar('compute_folder',default=None)


def _workflow(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        token = CURRENT_FOLDER.set(None)
        try:
            with warnings.catch_warnings(record=True) as observed:
                warnings.simplefilter('always')
                result = function(*args,**kwargs)
            folder = CURRENT_FOLDER.get()
            if folder and isinstance(result,dict) and result.get('success'):
                captured=[{'type':w.category.__name__,'message':str(w.message)} for w in observed[:1000]]
                (folder/'backend_warnings.json').write_text(json.dumps(captured,indent=2),encoding='utf8')
                result['backend_warning_count']=len(observed)
                result['backend_warnings_truncated']=len(observed)>1000
                return _finish(folder,{k:v for k,v in result.items() if k not in {'success','outputs','output_directory','report_file'}})
            return result
        except Exception as exc:
            folder = CURRENT_FOLDER.get()
            if folder:
                (folder/'state.json').write_text(json.dumps({'state':'failed','error_type':type(exc).__name__})+'\n',encoding='utf8')
                (folder/'failure.txt').write_text(str(exc),encoding='utf8')
            raise
        finally:
            CURRENT_FOLDER.reset(token)
    return wrapped


def _context(context):
    if not isinstance(context,dict) or any(not context.get(k) for k in CONTEXT):
        raise ValueError('Provide species/model/assay/biological_unit/contrast/limitations/input_source/input_processing')


def _read(path,numeric=False,counts=False):
    file = Path(path).resolve(strict=True)
    if file.stat().st_size>LIMIT_BYTES:
        raise ValueError('Input exceeds local size limit; use the server')
    with file.open(encoding='utf-8-sig',newline='') as stream:
        reader = csv.reader(stream,delimiter='\t' if file.suffix.lower()=='.tsv' else ',')
        header = next(reader,[])
        if len(header)<2 or any(not x.strip() for x in header[1:]) or len(set(header))!=len(header):
            raise ValueError('Missing or duplicate column identifiers')
        rows,ids = [],set()
        for row in reader:
            if len(row)!=len(header) or not row[0].strip() or row[0] in ids:
                raise ValueError('Malformed row or duplicate row identifier')
            ids.add(row[0])
            if len(ids)*(len(header)-1)>LIMIT_ENTRIES:
                raise ValueError('Matrix exceeds local entry limit; use the server')
            if numeric:
                values = [float(v) for v in row[1:]]
                if any(not math.isfinite(v) for v in values):
                    raise ValueError('Nonfinite or missing numeric value')
                if counts and any(v<0 or v!=round(v) or v>2147483647 for v in values):
                    raise ValueError('Counts must be bounded nonnegative integers; never round normalized expression')
                row = [row[0]]+values
            rows.append(row)
    if not rows:
        raise ValueError('Input is empty')
    return header,rows


def _frames(path,metadata_path,counts=True):
    import pandas as pd
    h,r = _read(path,True,counts)
    mh,mr = _read(metadata_path)
    matrix = pd.DataFrame([v[1:] for v in r],index=[v[0] for v in r],columns=h[1:])
    meta = pd.DataFrame([v[1:] for v in mr],index=[v[0] for v in mr],columns=mh[1:])
    if set(matrix.columns)!=set(meta.index):
        raise ValueError('Matrix samples and metadata must match exactly')
    return matrix,meta.loc[matrix.columns].copy()


def _folder(name):
    folder = HERE/'outputs'/(name+'_'+uuid.uuid4().hex)
    folder.mkdir(parents=True)
    CURRENT_FOLDER.set(folder)
    (folder/'state.json').write_text('{"state":"running"}\n',encoding='utf8')
    return folder


def _finish(folder,data):
    files = []
    for file in sorted(folder.iterdir()):
        if file.is_file() and file.name not in {'report.html','state.json','summary.json'}:
            files.append({'name':file.name,'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
    data.update(output_directory=str(folder),outputs=files,scientific_validity_established=False)
    (folder/'summary.json').write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    (folder/'report.html').write_text('<!doctype html><meta charset="utf-8"><title>Analysis report</title><h1>Analysis report</h1><pre>'+html.escape(json.dumps(data,ensure_ascii=False,indent=2))+'</pre>',encoding='utf8')
    (folder/'state.json').write_text('{"state":"succeeded"}\n',encoding='utf8')
    return {'success':True,**data,'report_file':str(folder/'report.html')}


def _design(meta,condition_key,unit_key,case,control,paired,covariates,min_units):
    import numpy as np
    import pandas as pd
    if case==control or type(paired) is not bool or not 3<=min_units<=50:
        raise ValueError('Use distinct groups and at least three biological units per group')
    if condition_key not in meta or unit_key not in meta:
        raise ValueError('Condition and biological-unit columns are required')
    if set(meta[condition_key])!={case,control} or meta[[condition_key,unit_key]].eq('').any().any():
        raise ValueError('Provide exactly the two requested groups with nonempty units; select other contrasts explicitly')
    units = {g:set(meta.loc[meta[condition_key]==g,unit_key]) for g in (case,control)}
    if min(map(len,units.values()))<min_units:
        raise ValueError('Insufficient independent biological units')
    if meta.duplicated([unit_key,condition_key]).any():
        raise ValueError('Repeated samples per unit/condition require explicit aggregation or another model')
    if paired and units[case]!=units[control] or not paired and units[case]&units[control]:
        raise ValueError('Incomplete paired design or repeated units in an unpaired model')
    d = pd.DataFrame(index=meta.index)
    d['condition'] = pd.Categorical(meta[condition_key],categories=[control,case])
    if paired:
        d['unit'] = pd.Categorical(meta[unit_key])
    names = ['unit'] if paired else []
    if not isinstance(covariates,list) or len(set(covariates))!=len(covariates):
        raise ValueError('Specify distinct categorical covariates')
    for name in covariates:
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,30}',name) or name in {'unit','condition',condition_key,unit_key} or name not in meta:
            raise ValueError('Invalid categorical covariate name')
        if meta[name].eq('').any() or meta[name].nunique()<2:
            raise ValueError('Missing or constant covariate')
        d[name] = pd.Categorical(meta[name])
        names.append(name)
    names.append('condition')
    x = pd.get_dummies(d[names],drop_first=True,dtype=float)
    x.insert(0,'Intercept',1.)
    if np.linalg.matrix_rank(x.to_numpy())!=x.shape[1] or len(d)-x.shape[1]<2:
        raise ValueError('Confounded or saturated design; no automatic batch correction')
    return d,'~ '+ ' + '.join(names),x, {g:len(u) for g,u in units.items()}


def inspect_local_compute(genes: int, observations: int, workflow: str = 'bulk') -> dict:
    """Estimate local matrix footprint and route large work to server preparation; execute nothing."""
    import psutil
    if type(genes) is not int or type(observations) is not int or genes<1 or observations<1 or workflow not in {'bulk','normalized','single_cell'}:
        raise ValueError('Specify positive matrix dimensions and a supported workflow')
    estimate = genes*observations*8*(12 if workflow=='single_cell' else 8)
    available = psutil.virtual_memory().available
    bound = 10000 if workflow=='single_cell' else 500
    allowed = observations<=bound and genes<=60000 and genes*observations<=LIMIT_ENTRIES and estimate<=min(available//2,4000000000)
    return {'state':'plan_only','recommended_placement':'local' if allowed else 'server','estimated_working_bytes':estimate,'available_memory_bytes':available,'local_gate_pass':allowed,'limitations':['A conservative estimate, not a guarantee of peak memory or runtime.','A server recommendation does not submit a job.']}


def _capacity(matrix,workflow):
    gate = inspect_local_compute(matrix.shape[0],matrix.shape[1],workflow)
    if not gate['local_gate_pass']:
        raise ValueError('Resource gate routes this matrix to the server')
    return gate


def _plots(expression,results,folder):
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from sklearn.decomposition import PCA
    scores = PCA(n_components=2,svd_solver='full').fit_transform(expression.T)
    pd.DataFrame(scores,index=expression.columns,columns=['PC1','PC2']).to_csv(folder/'pca_scores.csv')
    fig,ax = plt.subplots()
    ax.scatter(scores[:,0],scores[:,1])
    for i,name in enumerate(expression.columns): ax.annotate(str(name),scores[i],fontsize=7)
    ax.set(xlabel='PC1',ylabel='PC2',title='Exploratory PCA; inspect metadata and outliers')
    fig.savefig(folder/'pca.png',dpi=150,bbox_inches='tight');plt.close(fig)
    fig,ax = plt.subplots()
    ax.scatter(results['log2FoldChange'],-np.log10(results['padj'].clip(lower=1e-300)),s=8)
    ax.set(xlabel='log2 fold change: case / control',ylabel='-log10 BH adjusted p',title='Volcano; missing tests are retained in the full table')
    fig.savefig(folder/'volcano.png',dpi=150,bbox_inches='tight');plt.close(fig)


def _enrichment(results,gene_sets_path,folder,alpha):
    if not gene_sets_path: return {'state':'not_requested'}
    from omics_ext import local_gene_set_enrichment,preranked_gsea
    background = results.index[results['pvalue'].notna()].tolist()
    selected = results.index[(results['padj']<alpha)].tolist()
    ora = {}
    for direction,mask in [('up',results.log2FoldChange>0),('down',results.log2FoldChange<0)]:
        genes = results.index[(results.padj<alpha)&mask].tolist()
        ora[direction] = local_gene_set_enrichment(genes,background,gene_sets_path) if genes else {'state':'no_selected_genes'}
    ranks = results[['stat']].dropna()
    ranks.to_csv(folder/'ranking.csv')
    gsea = preranked_gsea(str(folder/'ranking.csv'),gene_sets_path,permutation_num=1000) if len(ranks)>=15 else {'state':'insufficient_ranked_genes'}
    result = {'ora':ora,'gsea':gsea,'gene_sets_sha256':hashlib.sha256(Path(gene_sets_path).read_bytes()).hexdigest(),'limitations':['Provide gene sets with matching species and identifiers; pathway scores do not establish causal activity.']}
    (folder/'enrichment.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf8')
    return {'state':'completed','file':str(folder/'enrichment.json')}


def _run_count_r(matrix,x,folder,method,rscript,context,formula,units,case,control,alpha,gene_sets_path,qc):
    import pandas as pd
    import os
    from software_ext import resolve
    executable = resolve('rscript',rscript)
    if not executable or Path(executable).stem.lower()!='rscript': raise ValueError('Install Rscript with edgeR and limma before using this count method')
    matrix.to_csv(folder/'counts.csv'); x.to_csv(folder/'design_matrix.csv')
    with (folder/'backend.log').open('w',encoding='utf8') as log:
        run = subprocess.run([executable,'--vanilla',str(HERE/'count_models.R'),str(folder),method],stdout=log,stderr=subprocess.STDOUT,timeout=600,env={**os.environ,'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if run.returncode: raise RuntimeError('Count backend failed; inspect private backend.log')
    results = pd.read_csv(folder/'differential_expression.csv',index_col=0)
    expression = pd.read_csv(folder/'log_cpm.csv',index_col=0)
    _plots(expression,results,folder)
    enrichment = _enrichment(results,gene_sets_path,folder,alpha)
    return _finish(folder,{'workflow':'bulk_rnaseq','method':method,'backend':'R '+method,'backend_version':(folder/'backend_version.txt').read_text().strip(),'formula':formula,'case':case,'control':control,'biological_units':units,'alpha':alpha,'context':context,'preanalysis_qc':qc,'enrichment':enrichment,'significant_genes':int((results.padj<alpha).sum()),'limitations':['Raw counts and unit provenance must be independently verified.','TMM normalization and model covariates are explicit; no sample is automatically removed.','The stat ranking is signed square-root F for edgeR QL and moderated t for voom.','PCA uses exploratory log CPM; model agreement is not independent replication.']})


@_workflow
def run_bulk_rnaseq(counts_path: str, metadata_path: str, condition_key: str, unit_key: str, case: str, control: str, context: dict, paired: bool = False, covariates: list = None, min_units: int = 3, min_count: int = 10, alpha: float = 0.05, threads: int = 2, gene_sets_path: str = '', method: str = 'pydeseq2_wald', rscript: str = 'Rscript') -> dict:
    """PyDESeq2 on declared raw integer gene counts with biological-unit and design checks; no network."""
    require_local()
    _context(context)
    if method not in {'pydeseq2_wald','edgeR_ql','limma_voom'}: raise ValueError('Unsupported count analysis method')
    if type(threads) is not int or not 1<=threads<=4 or type(min_count) is not int or min_count<1 or not 0<alpha<1:
        raise ValueError('Invalid CPU, count filter or FDR threshold')
    matrix,meta = _frames(counts_path,metadata_path)
    capacity = _capacity(matrix,'bulk')
    d,formula,x,units = _design(meta,condition_key,unit_key,case,control,paired,covariates or [],min_units)
    from qc_ext import require_qc
    qc = require_qc(matrix,meta,{'matrix':counts_path,'metadata':metadata_path},'raw_counts',context,formula,units)
    import numpy as np
    import pandas as pd
    if (matrix.sum(axis=0)<=0).any(): raise ValueError('Empty count library')
    keep = (matrix>=min_count).sum(axis=1)>=min_units
    if keep.sum()<20: raise ValueError('Fewer than twenty genes pass the declared expression filter')
    folder = _folder('bulk_rnaseq')
    x.to_csv(folder/'design_matrix.csv')
    pd.DataFrame({'kept':keep}).to_csv(folder/'gene_filter.csv')
    if method!='pydeseq2_wald':
        return _run_count_r(matrix.loc[keep],x,folder,method,rscript,context,formula,units,case,control,alpha,gene_sets_path,qc)
    from pydeseq2.dds import DeseqDataSet
    from pydeseq2.ds import DeseqStats
    from pydeseq2.default_inference import DefaultInference
    dds = DeseqDataSet(counts=matrix.loc[keep].T.astype('int64'),metadata=d,design=formula,refit_cooks=True,inference=DefaultInference(n_cpus=threads),quiet=True)
    dds.deseq2()
    stats = DeseqStats(dds,contrast=['condition',case,control],alpha=alpha,inference=DefaultInference(n_cpus=threads),quiet=True)
    stats.summary()
    results = stats.results_df.copy()
    results.index.name = 'gene'
    results.to_csv(folder/'differential_expression.csv')
    normalized = pd.DataFrame(dds.layers['normed_counts'].T,index=results.index,columns=matrix.columns)
    normalized.to_csv(folder/'normalized_counts.csv')
    dds.obs[['size_factors']].to_csv(folder/'sample_qc.csv')
    dds.vst()
    transformed = pd.DataFrame(dds.layers['vst_counts'].T,index=results.index,columns=matrix.columns)
    _plots(transformed,results,folder)
    enrichment = _enrichment(results,gene_sets_path,folder,alpha)
    return _finish(folder,{'workflow':'bulk_rnaseq','preanalysis_qc':qc,'method':method,'backend':'PyDESeq2','backend_version':version('pydeseq2'),'formula':formula,'case':case,'control':control,'positive_log2fc_means':case+' higher than '+control,'biological_units':units,'genes_input':len(matrix),'genes_kept':int(keep.sum()),'missing_adjusted_tests':int(results.padj.isna().sum()),'significant_genes':int((results.padj<alpha).sum()),'alpha':alpha,'threads':threads,'capacity':capacity,'context':context,'enrichment':enrichment,'limitations':['Raw-count provenance is caller-declared; integer values alone do not prove raw counts.','Technical replicates and cells are not independent biological replicates.','No LFC shrinkage is applied; retain failed/filtered/undefined tests.','PCA is exploratory and does not automatically remove outliers or correct batches.']})


@_workflow
def aggregate_pseudobulk(counts_path: str, metadata_path: str, unit_key: str, condition_key: str, cell_type_key: str, cell_type: str, context: dict, min_cells: int = 20, covariates: list = None) -> dict:
    """Sum raw cell counts within one cell type and biological unit/condition; retain excluded groups."""
    require_local()
    _context(context)
    if type(min_cells) is not int or min_cells<1: raise ValueError('Specify a positive minimum cell count')
    matrix,meta = _frames(counts_path,metadata_path)
    _capacity(matrix,'single_cell')
    keys = [unit_key,condition_key,cell_type_key]+(covariates or [])
    if any(k not in meta for k in keys) or meta[keys].eq('').any().any(): raise ValueError('Missing unit, condition, cell type or covariate')
    chosen = meta[meta[cell_type_key]==cell_type]
    if chosen.empty: raise ValueError('Requested cell type is absent')
    import pandas as pd
    aggregates,rows,excluded = {},[],[]
    for (unit,condition),group in chosen.groupby([unit_key,condition_key],sort=True):
        if any(group[k].nunique()!=1 for k in covariates or []): raise ValueError('Mixed covariates within a biological unit/condition require an explicit design')
        if len(group)<min_cells:
            excluded.append({'unit':unit,'condition':condition,'cells':len(group),'reason':'below_min_cells'})
            continue
        key = 'sample_'+str(len(rows)+1)
        aggregates[key] = matrix[group.index].sum(axis=1).astype('int64')
        rows.append({'sample':key,'unit':unit,'condition':condition,'cells':len(group),'cell_type':cell_type,**{k:group.iloc[0][k] for k in covariates or []}})
    if not rows: raise ValueError('No pseudobulk group passes the cell threshold')
    folder = _folder('pseudobulk')
    pd.DataFrame(aggregates).to_csv(folder/'counts.csv')
    pd.DataFrame(rows).set_index('sample').to_csv(folder/'metadata.csv')
    return _finish(folder,{'workflow':'pseudobulk_aggregation','context':context,'excluded_groups':excluded,'retained_groups':len(rows),'min_cells':min_cells,'limitations':['Aggregation is not differential-expression analysis. Feed the output into the bulk workflow using unit/condition keys and the appropriate paired design.','Supply curated cell labels; this tool does not verify their biological identity.','Cells are summed within units, not treated as independent replicates.']})


@_workflow
def run_normalized_expression(expression_path: str, metadata_path: str, condition_key: str, unit_key: str, case: str, control: str, context: dict, matrix_kind: str, rscript: str = 'Rscript', paired: bool = False, covariates: list = None, min_units: int = 3, alpha: float = 0.05, gene_sets_path: str = '', test: str = 'ebayes', lfc_threshold: float = 1.) -> dict:
    """Native R limma empirical-Bayes analysis for declared log2 normalized expression; no silent scale conversion."""
    require_local()
    _context(context)
    if test not in {'ebayes','treat'} or not 0<=lfc_threshold<=5: raise ValueError('Specify ebayes or treat and a bounded log2 effect threshold')
    if matrix_kind!='log2_normalized' or not 0<alpha<1: raise ValueError('Provide verified log2 normalized expression and a valid FDR threshold; TPM/counts are not accepted here')
    matrix,meta = _frames(expression_path,metadata_path,False)
    capacity = _capacity(matrix,'normalized')
    d,formula,x,units = _design(meta,condition_key,unit_key,case,control,paired,covariates or [],min_units)
    from qc_ext import require_qc
    qc = require_qc(matrix,meta,{'matrix':expression_path,'metadata':metadata_path},'log2_normalized',context,formula,units)
    from software_ext import resolve
    executable = resolve('rscript',rscript)
    if not executable or Path(executable).stem.lower()!='rscript': raise ValueError('Provide an installed Rscript with limma; no substitute model is used')
    folder = _folder('normalized_expression')
    matrix.to_csv(folder/'expression.csv')
    x.to_csv(folder/'design_matrix.csv')
    import pandas as pd
    import numpy as np
    import os
    contrast = np.zeros(x.shape[1]); contrast[-1] = 1.
    # The last dummy coefficient is case versus control, because condition is last with explicit levels.
    pd.DataFrame({'weight':contrast},index=x.columns).to_csv(folder/'contrast.csv')
    command = [executable,'--vanilla',str(HERE/'limma_pipeline.R'),str(folder),test,str(lfc_threshold)]
    env = {**os.environ,'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'}
    with (folder/'backend.log').open('w',encoding='utf8') as log:
        run = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=600,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if run.returncode: raise RuntimeError('limma failed; inspect preserved private backend.log and partial files')
    results = pd.read_csv(folder/'differential_expression.csv',index_col=0)
    _plots(matrix,results,folder)
    enrichment = _enrichment(results,gene_sets_path,folder,alpha)
    return _finish(folder,{'workflow':'normalized_expression','preanalysis_qc':qc,'test':test,'lfc_threshold':lfc_threshold if test=='treat' else None,'backend':'R limma','backend_version':(folder/'backend_version.txt').read_text().strip(),'formula':formula,'case':case,'control':control,'biological_units':units,'alpha':alpha,'context':context,'capacity':capacity,'enrichment':enrichment,'significant_genes':int((results.padj<alpha).sum()),'limitations':['Scale and platform normalization are caller-declared. No CEL preprocessing, RMA, quantile normalization or automatic probe-to-gene collapse is performed.','Repeated biological units require an explicit paired design; categorical covariates only.','Already normalized RNA-seq values need separate methodological justification; raw counts should use the count workflow.','limma version is recorded from the installed R library.']})


@_workflow
def run_small_single_cell(counts_path: str, metadata_path: str, unit_key: str, context: dict, mitochondrial_prefix: str, min_genes: int = 200, max_mito_percent: float = 20., min_cells_per_gene: int = 3, hvg_genes: int = 2000, neighbors: int = 15, resolution: float = 1., seed: int = 42, resolution_grid: list = None, marker_method: str = 'wilcoxon', doublet_batch_key: str = '', remove_predicted_doublets: bool = False) -> dict:
    """Bounded Scanpy QC, log normalization, HVG, PCA, neighbors, UMAP and Leiden; clustering is exploratory."""
    require_local()
    _context(context)
    if not mitochondrial_prefix or min_genes<1 or not 0<=max_mito_percent<=100 or min_cells_per_gene<1 or not 20<=hvg_genes<=5000 or not 2<=neighbors<=50 or not 0<resolution<=5:
        raise ValueError('Invalid explicit QC or clustering thresholds')
    matrix,meta = _frames(counts_path,metadata_path)
    capacity = _capacity(matrix,'single_cell')
    if unit_key not in meta or meta[unit_key].eq('').any(): raise ValueError('Cell metadata requires nonempty biological-unit identifiers')
    import scanpy as sc
    import anndata as ad
    import numpy as np
    if marker_method not in {'wilcoxon','t-test'} or type(remove_predicted_doublets) is not bool: raise ValueError('Choose an exploratory marker method and explicit doublet-removal flag')
    resolutions = resolution_grid or [resolution]
    if not isinstance(resolutions,list) or not 1<=len(resolutions)<=5 or any(not 0<float(r)<=5 for r in resolutions): raise ValueError('Specify one to five bounded clustering resolutions')
    sc.settings.n_jobs = 2
    import numba
    numba.set_num_threads(2)
    data = ad.AnnData(matrix.T.to_numpy(dtype='float64'),obs=meta,var=__import__('pandas').DataFrame(index=matrix.index))
    data.layers['counts'] = data.X.copy()
    data.var['mitochondrial'] = data.var_names.str.startswith(mitochondrial_prefix)
    if not data.var.mitochondrial.any(): raise ValueError('Mitochondrial prefix matched no genes; resolve identifiers before QC')
    sc.pp.calculate_qc_metrics(data,qc_vars=['mitochondrial'],percent_top=None,log1p=False,inplace=True)
    folder = _folder('small_single_cell')
    keep = (data.obs.n_genes_by_counts>=min_genes)&(data.obs.pct_counts_mitochondrial<=max_mito_percent)&(data.obs.total_counts>0)
    if doublet_batch_key:
        if doublet_batch_key not in meta or meta[doublet_batch_key].eq('').any() or meta.groupby(doublet_batch_key).size().min()<30: raise ValueError('Scrublet requires an explicit library key with at least thirty cells per library')
        sc.pp.scrublet(data,batch_key=doublet_batch_key,random_state=seed)
        if remove_predicted_doublets: keep &= ~data.obs.predicted_doublet
    elif remove_predicted_doublets: raise ValueError('Specify a doublet library key before requesting removal')
    data.obs['retained_by_qc'] = keep
    data.obs.to_csv(folder/'all_cell_qc.csv')
    if keep.mean()<0.5: raise ValueError('More than half the cells fail QC; review the preserved audit before revising inputs or thresholds')
    data = data[keep].copy()
    if data.n_obs<10: raise ValueError('Fewer than ten cells pass QC; retained audit remains on the host')
    sc.pp.filter_genes(data,min_cells=min_cells_per_gene)
    if data.n_vars<20: raise ValueError('Fewer than twenty genes pass QC')
    sc.pp.normalize_total(data,target_sum=10000)
    sc.pp.log1p(data)
    sc.pp.highly_variable_genes(data,flavor='seurat',n_top_genes=min(hvg_genes,data.n_vars))
    selected = data[:,data.var.highly_variable].copy()
    pcs = min(30,selected.n_obs-1,selected.n_vars-1)
    if pcs<2: raise ValueError('Insufficient varying genes or cells for PCA')
    sc.pp.scale(selected,max_value=10)
    sc.tl.pca(selected,n_comps=pcs,svd_solver='arpack',random_state=seed)
    sc.pp.neighbors(selected,n_neighbors=min(neighbors,selected.n_obs-1),n_pcs=pcs,random_state=seed)
    sc.tl.umap(selected,random_state=seed)
    for index,r in enumerate(resolutions):
        key = 'leiden_r'+str(index)
        sc.tl.leiden(selected,resolution=float(r),random_state=seed,flavor='igraph',n_iterations=2,directed=False,key_added=key)
        data.obs[key] = selected.obs[key]
    selected.obs['leiden'] = selected.obs['leiden_r0']
    data.obs['leiden'] = selected.obs.leiden
    data.obsm['X_pca'] = selected.obsm['X_pca']; data.obsm['X_umap'] = selected.obsm['X_umap']
    from sklearn.metrics import adjusted_rand_score
    stability = [{'left':i,'right':i+1,'adjusted_rand_index':float(adjusted_rand_score(data.obs['leiden_r'+str(i)],data.obs['leiden_r'+str(i+1)]))} for i in range(len(resolutions)-1)]
    (folder/'resolution_stability.json').write_text(json.dumps(stability,indent=2),encoding='utf8')
    if data.obs.leiden.nunique()>1 and data.obs.groupby('leiden',observed=True).size().min()>=2:
        sc.tl.rank_genes_groups(data,'leiden',method=marker_method,use_raw=False,layer=None)
        sc.get.rank_genes_groups_df(data,group=None).to_csv(folder/'exploratory_cluster_markers.csv',index=False)
    data.obs.to_csv(folder/'cell_clusters.csv')
    data.write_h5ad(folder/'processed.h5ad')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax = plt.subplots()
    ax.scatter(data.obsm['X_umap'][:,0],data.obsm['X_umap'][:,1],c=data.obs.leiden.cat.codes,s=5)
    ax.set(title='Exploratory UMAP / Leiden',xlabel='UMAP1',ylabel='UMAP2')
    fig.savefig(folder/'umap.png',dpi=150,bbox_inches='tight');plt.close(fig)
    return _finish(folder,{'workflow':'small_single_cell','backend':'Scanpy','backend_version':version('scanpy'),'input_cells':len(meta),'retained_cells':data.n_obs,'retained_genes':data.n_vars,'biological_units':int(data.obs[unit_key].nunique()),'seed':seed,'resolution_grid':resolutions,'marker_method':marker_method,'doublet_batch_key':doublet_batch_key,'doublet_removal_requested':remove_predicted_doublets,'qc_input_hashes':{'counts':hashlib.sha256(Path(counts_path).read_bytes()).hexdigest(),'metadata':hashlib.sha256(Path(metadata_path).read_bytes()).hexdigest()},'qc':{'min_genes':min_genes,'max_mito_percent':max_mito_percent,'mitochondrial_prefix':mitochondrial_prefix,'mitochondrial_genes_found':int(data.var.mitochondrial.sum())},'capacity':capacity,'context':context,'limitations':['QC thresholds require species/platform review; an unmatched mitochondrial prefix disables meaningful mitochondrial QC.','Doublet screening/removal occurs only when explicitly requested with a library key; no batch integration or automated cell identity is performed.', 'Cluster-marker p-values are exploratory cell-level comparisons and do not establish replicated condition effects.','Clusters and UMAP proximity do not establish cell types, trajectories or mechanisms.','Use the preserved raw counts layer and donor-aware pseudobulk for condition comparisons.']})
