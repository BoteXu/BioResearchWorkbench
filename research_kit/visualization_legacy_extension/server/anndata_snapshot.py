"""Read explicitly selected stored AnnData values on an authorized server; never fit analysis."""
from pathlib import Path
import sys,os,socket,platform,importlib.metadata,json,hashlib,math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contracts import read,write,sha,validate
def guard(p):
    if sys.platform!='linux' or 'microsoft' in platform.release().lower():raise RuntimeError('AnnData extraction runs only on the existing server, never this computer/WSL')
    if p.get('dispatch_authorized') is not True or p.get('expected_host')!=socket.gethostname() or p.get('node_role')!='compute' or not (os.getenv('SLURM_JOB_ID') or os.getenv('SSH_CONNECTION')):raise RuntimeError('Actual approved compute host and explicit existing-server dispatch required')
    if any(x in socket.gethostname().lower() for x in ('login','headnode')):raise RuntimeError('Do not read large objects on login nodes')
def extract(plan_path,out):
    p=read(plan_path);guard(p);root=Path(plan_path).resolve().parent
    if set(p)!={'schema','dispatch_authorized','expected_host','node_role','input','expected_anndata_version','object_ids','marker_ids','embedding_key','group_key','donor_key','representation','summaries','figure_template'} or p['schema']!='anndata-frozen-display/1':raise ValueError('Exact frozen-display extraction contract required')
    if len(p['object_ids'])>50000 or not p['object_ids'] or len(set(p['object_ids']))!=len(p['object_ids']) or not p['marker_ids'] or len(set(p['marker_ids']))!=len(p['marker_ids']):raise ValueError('Explicit bounded unique display subset required')
    def selected(row):
        f=(root/row['path']).resolve(strict=True)
        if not f.is_relative_to(root) or not f.is_file() or sha(f)!=row['sha256']:raise ValueError('Selected source changed or escaped approved project')
        return f
    file=selected(p['input']);summary=selected(p['summaries'])
    if importlib.metadata.version('anndata')!=p['expected_anndata_version']:raise ValueError('Existing AnnData version differs from reviewed server version')
    import anndata
    ad=anndata.read_h5ad(file,backed='r')
    try:
        ids=p['object_ids'];genes=p['marker_ids'];rep=p['representation']
        if not ad.obs_names.is_unique or any(x not in ad.obs_names for x in ids) or p['embedding_key'] not in ad.obsm:raise ValueError('Exact stored embedding and selected identities required')
        if set(rep)!={'kind','layer','unit'} or rep['kind'] not in ('raw','X','layer'):raise ValueError('Explicit raw/X/layer representation required')
        if rep['kind']=='raw':
            if ad.raw is None or rep['layer'] is not None:raise ValueError('Requested raw snapshot absent or layer ignored')
            obj=ad.raw
        else:
            if rep['kind']=='X' and rep['layer'] is not None or rep['kind']=='layer' and rep['layer'] not in ad.layers:raise ValueError('Requested expression layer differs')
            obj=ad
        if not obj.var_names.is_unique or any(x not in obj.var_names for x in genes):raise ValueError('Use exact unique gene IDs from selected representation, not silently resolved symbols')
        view=obj[ids,genes];mat=view.X if rep['kind']!='layer' else view.layers[rep['layer']]
        idx=ad.obs_names.get_indexer(ids);embedding=ad.obsm[p['embedding_key']][idx,:2]
        observations=ad.obs.loc[ids];rows=[]
        for i,cid in enumerate(ids):
            group=observations.iloc[i][p['group_key']];donor=observations.iloc[i][p['donor_key']]
            if not isinstance(group,str) or not group or not isinstance(donor,str) or not donor:raise ValueError('Stored group/donor identities must be explicit nonmissing strings')
            values={gene:float(mat[i,j]) for j,gene in enumerate(genes)}
            if any(not math.isfinite(v) for v in values.values()):raise ValueError('Nonfinite supplied expression')
            rows.append({'id':cid,'group':group,'donor':donor,'x':float(embedding[i,0]),'y':float(embedding[i,1]),'values':values})
        spec=p['figure_template'];spec['provenance'].update(source_id=file.name,source_sha256=p['input']['sha256'],selection='Exact object_ids and marker_ids recorded in extraction receipt',transformations='Stored values and embedding subset only; no fit or normalization')
        spec['data'].update(objects=rows,markers=genes,summaries=read(summary),representation=rep['kind']+(':'+rep['layer'] if rep['layer'] else '')+' ['+rep['unit']+']');validate(spec)
        out=Path(out);out.mkdir(parents=True,exist_ok=False);write(out/'frozen_markers.figure.json',spec)
        if sha(file)!=p['input']['sha256'] or sha(summary)!=p['summaries']['sha256']:raise ValueError('Source changed during extraction')
        write(out/'receipt.private.json',{'state':'STORED_VALUES_EXTRACTED_UNREVIEWED','input_sha256':sha(file),'selected_ids':ids,'selected_gene_ids':genes,'representation':rep,'embedding_key':p['embedding_key'],'output_sha256':sha(out/'frozen_markers.figure.json'),'analysis_fitted':False,'summaries_recomputed':False,'scientific_acceptance':'NOT_ESTABLISHED','public_upload':False})
    finally:ad.file.close()
if __name__=='__main__':extract(sys.argv[1],sys.argv[2])
