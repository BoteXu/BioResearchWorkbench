"""Observed-layer Seurat to AnnData exchange with exact axes and source checks."""
from pathlib import Path
import subprocess
from runtime import write,read,sha

def analyze(inputs,p,out,mode):
    if mode!='seurat_to_anndata':raise ValueError('Unknown fixed exchange')
    from native_teaching_contracts import validate
    validate(mode,p,verify_versions=True)
    import anndata as ad,pandas as pd,numpy as np
    from scipy.io import mmread
    from scipy import sparse
    exe=Path(p['rscript'])
    if not exe.is_absolute() or not exe.is_file() or exe.name!='Rscript':raise ValueError('Existing selected server Rscript required')
    folder=out/'exchange';folder.mkdir();request=out/'exchange_request.private.json';write(request,{'input':str(inputs['object']),'out':str(folder),'parameters':p})
    with (out/'exchange.stdout.log').open('xb') as log,(out/'exchange.stderr.log').open('xb') as err:
        completed=subprocess.run([str(exe),str(Path(__file__).with_name('native_seurat_exchange.R')),str(request)],stdout=log,stderr=err,check=False)
    if completed.returncode:raise RuntimeError('Native observed-layer export failed; preserve logs and inspect without automatic retry')
    axes=read(folder/'axes.json');cells=axes['cell_ids'];genes=axes['gene_ids'];metadata=read(folder/'metadata.json')
    if not all(isinstance(v,str) and v for v in cells+genes) or len(set(cells))!=len(cells) or len(set(genes))!=len(genes):raise ValueError('Native exchange requires unique nonempty literal identities')
    counts=sparse.csr_matrix(mmread(folder/'counts.mtx').T);expression=sparse.csr_matrix(mmread(folder/'log_expression.mtx').T)
    if counts.shape!=(len(cells),len(genes)) or expression.shape!=counts.shape or len(metadata)!=len(cells):raise ValueError('Exchange matrix/metadata dimensions differ from exact exported axes')
    if not np.isfinite(counts.data).all() or (counts.data<0).any() or (counts.data!=np.floor(counts.data)).any() or not np.isfinite(expression.data).all() or (expression.data<0).any():raise ValueError('Observed-layer numerical identity failed')
    obs=pd.DataFrame(metadata,index=cells)
    if not set([p['unit_key'],p['sample_key'],p['condition_key']])<=set(obs) or obs[[p['unit_key'],p['sample_key'],p['condition_key']]].isna().any().any():raise ValueError('Scientific metadata lost during conversion')
    for key in p['categorical_keys']:
        if key not in obs:raise ValueError('Declared categorical field absent')
        obs[key]=pd.Categorical(obs[key])
    a=ad.AnnData(X=expression,obs=obs,var=pd.DataFrame(index=genes));a.layers['counts']=counts;a.layers['log1p_normalized']=expression.copy()
    reductions=read(folder/'reductions.json')
    if reductions==[]:reductions={}
    if set(reductions)!=set(p['reduction_names']):raise ValueError('Reduction catalogue differs from requested native reductions')
    for key,filename in reductions.items():
        if Path(filename).name!=filename:raise ValueError('Reduction filename escapes fixed exchange')
        z=pd.read_csv(folder/filename,sep='\t',header=None).to_numpy(float)
        if z.shape[0]!=len(cells) or not np.isfinite(z).all():raise ValueError('Nonfinite or misaligned native reduction')
        a.obsm[key]=z
    a.uns['observed_source_seurat_sha256']=sha(inputs['object']);a.uns['normalization_scale']='log1p_normalized';a.uns['conversion_method']='Observed Matrix Market/JSON exchange; no model fitting, rescaling, neighbor reconstruction or gene alias mapping'
    result=out/'observed_anndata.h5ad';a.write_h5ad(result)
    # Full read-back happens on the server, not a local download of scientific matrices.
    back=ad.read_h5ad(result)
    if list(back.obs_names)!=cells or list(back.var_names)!=genes or (back.layers['counts']!=counts).nnz or (back.X!=expression).nnz:raise ValueError('AnnData write/read changed observed values or exact feature/cell axes')
    diagnostic={'mode':mode,'software_versions':p['software_versions'],'r_software_versions':p['r_software_versions'],'n_cells':len(cells),'n_features':len(genes),'count_nnz':counts.nnz,'normalized_nnz':expression.nnz,'counts_and_expression_readback_equal':True,'literal_cell_gene_axes_preserved':True,'reductions':list(reductions),'source_seurat_sha256':sha(inputs['object']),'scientific_acceptance':'NOT_ESTABLISHED','interpretation':'Exact selected observed-layer/metadata/reduction exchange only; does not validate upstream analysis or make integrated expression suitable for count inference'}
    write(out/'exchange_diagnostics.json',diagnostic);outputs=[(result,'processed_object'),(out/'exchange_diagnostics.json','diagnostics')]
    for filename,role in [('exchange.stdout.log','backend_stdout'),('exchange.stderr.log','backend_stderr')]:
        if (out/filename).stat().st_size:outputs.append((out/filename,role))
    for f in folder.iterdir():
        if f.is_file():outputs.append((f,'exchange_source_material'))
    write(out/'native_versions.json',p['software_versions']);outputs.append((out/'native_versions.json','backend_versions'));return outputs
