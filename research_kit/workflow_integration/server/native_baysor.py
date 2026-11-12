"""Exact existing Baysor C++ molecule segmentation; no invented cell assignments."""
from pathlib import Path
import subprocess,re
from runtime import read,write,sha

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate
    validate(mode,p,verify_versions=True)
    import pandas as pd,numpy as np
    from native_genetics import existing_file
    exe=existing_file(p['baysor_executable'],p['baysor_executable_sha256'])
    version=subprocess.run([str(exe),'--version'],capture_output=True,text=True,check=True).stdout.strip()
    if version!=p['baysor_version_output']:raise ValueError('Existing Baysor version/implementation differs from the reviewed C++ CLI')
    data=pd.read_csv(inputs['molecules'],dtype={'transcript_id':str,'gene':str},keep_default_na=False)
    axes=['x','y']+(['z'] if p['dimensions']==3 else [])
    if not {'transcript_id','gene',*axes}<=set(data) or not len(data) or len(data)>p['maximum_molecules']:raise ValueError('Bounded actual molecule table with exact numeric source transcript IDs required')
    ids=data.transcript_id
    if ids.duplicated().any() or not ids.str.fullmatch(r'(0|[1-9][0-9]*)').all() or any(int(x)>2**53-1 for x in ids):raise ValueError('This native numeric-ID route requires unique canonical safe integers; no invented or rewritten transcript IDs')
    if (data.gene=='').any() or not np.isfinite(data[axes].to_numpy(float)).all() or p['dimensions']==2 and 'z' in data and data.z.nunique()>1:raise ValueError('Actual complete gene and finite physical coordinate channels of the declared dimension required')
    argv=[str(exe),'run','-m',str(p['minimum_molecules']),'-s',str(p['cell_radius']),'-o',str(out/'native'),'--threads',str(p['threads']),'--output-style','legacy','--count-matrix-format','tsv','--polygon-format','FeatureCollection','--cluster-method',p['cluster_method'],'--n-clusters',str(p['n_clusters']),'--min-molecules-per-gene','1',str(inputs['molecules'])]
    if p['prior_column'] is not None:
        key=p['prior_column']
        if key not in data or not re.fullmatch('[A-Za-z][A-Za-z0-9_]*',key):raise ValueError('Exact existing prior-label column required')
        argv+=[':'+key,'--prior-segmentation-confidence',str(p['prior_confidence'])]
    write(out/'baysor_command.private.json',{'argv':argv,'coordinate_unit':p['coordinate_unit'],'version_output':version,'filtering_scope':'no gene/crop/quality filtering requested; exact molecule identity must be retained'})
    with (out/'baysor.stdout.log').open('xb') as so,(out/'baysor.stderr.log').open('xb') as se:proc=subprocess.run(argv,stdout=so,stderr=se,check=False)
    if proc.returncode:raise RuntimeError('Native Baysor failed; retain actual partial output and never automatically retry')
    root=out/'native';assigned=pd.read_csv(root/'segmentation.csv',dtype={'transcript_id':str,'gene':str,'cell':str},keep_default_na=False);stats=pd.read_csv(root/'segmentation_cell_stats.csv',dtype={'cell':str});counts=pd.read_csv(root/'segmentation_counts.tsv',sep='\t',index_col=0,dtype={'gene':str})
    if not {'transcript_id','gene','cell','is_noise',*axes}<=set(assigned) or assigned.transcript_id.duplicated().any() or set(assigned.transcript_id)!=set(ids):raise ValueError('Native segmentation filtered, duplicated or lost source molecule IDs; inspect explicitly, never align positionally')
    original=data.set_index('transcript_id');assigned=assigned.set_index('transcript_id').loc[ids]
    if not assigned.gene.equals(original.loc[ids,'gene']) or not np.allclose(assigned[axes].to_numpy(float),original.loc[ids,axes].to_numpy(float),rtol=0,atol=p['coordinate_roundtrip_tolerance']):raise ValueError('Native source gene/coordinate identity changed')
    noise=assigned.cell.eq('0');flag=assigned.is_noise.astype(str).str.lower().map({'true':True,'false':False,'1':True,'0':False})
    if flag.isna().any() or not noise.equals(flag):raise ValueError('Native noise-cell assignment semantics differ')
    retained=assigned.loc[~noise];actual=pd.crosstab(retained.gene,retained.cell)
    if not len(retained) or stats.cell.duplicated().any() or set(stats.cell)!=set(actual.columns) or set(counts.columns)!=set(actual.columns) or not set(counts.index)<=set(data.gene) or not set(actual.index)<=set(counts.index):raise ValueError('Native cell statistics/count axes differ from source molecular assignments')
    expected=actual.reindex(index=counts.index,columns=counts.columns,fill_value=0)
    if not np.array_equal(counts.to_numpy(),expected.to_numpy()):raise ValueError('Native expression counts do not equal the observed assigned molecules')
    if not np.array_equal(stats.set_index('cell').loc[actual.columns,'n_transcripts'].to_numpy(float),actual.sum(0).to_numpy(float)):raise ValueError('Native per-cell transcript counts differ')
    boundaries=read(root/'segmentation_polygons_2d.json');polygons=boundaries.get('features',[])
    if boundaries.get('type')!='FeatureCollection' or {q.get('properties',{}).get('cell') for q in polygons}!=set(actual.columns):raise ValueError('Native polygon/cell identity differs; fallback rectangles require visual review')
    outputs=[(out/'baysor_command.private.json','native_command')]
    for file,role in [('segmentation.csv','molecule_assignments'),('segmentation_cell_stats.csv','cell_segmentation_qc'),('segmentation_counts.tsv','segmented_counts'),('segmentation_polygons_2d.json','cell_polygons'),('segmentation_params.dump.toml','native_parameters'),('segmentation_log.log','native_segmentation_log')]:outputs.append((root/file,role))
    if p['dimensions']==3:outputs.append((root/'segmentation_polygons_3d.json','layer_polygons'))
    for fn,role in [('baysor.stdout.log','backend_stdout'),('baysor.stderr.log','backend_stderr')]:
        if (out/fn).stat().st_size:outputs.append((out/fn,role))
    write(out/'diagnostics.json',{'mode':mode,'software_versions':p['software_versions'],'n_molecules':len(data),'n_cells':len(stats),'unassigned_fraction':float(noise.mean()),'source_molecule_identity_preserved':True,'counts_equal_molecule_assignments':True,'coordinate_unit':p['coordinate_unit'],'scientific_acceptance':'NOT_ESTABLISHED','interpretation':'Native Baysor C++ segmentation only; minimum molecules is a modeling parameter, not automatic sample QC. Keep unassigned/noise molecules. Boundaries may use fallback rectangles and require actual imaging/visual validation; no cell-type or biological-quality acceptance inferred.'});outputs.append((out/'diagnostics.json','diagnostics'));write(out/'versions.json',p['software_versions']);outputs.append((out/'versions.json','backend_versions'));return outputs
