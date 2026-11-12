"""Fixed native execution for DIA-NN Academia, MAGPIE and DOCKovalent 3.7."""
from pathlib import Path
import csv
import gzip
import math
import re
import shutil
import sys
from runtime import read,write,selected,sha
from completion_common import table,native_command,checked_executable

def _dest(root,name):
    if not isinstance(name,str) or '\\' in name or ':' in name or name.startswith('/') or any(x in {'','..','.'} for x in name.split('/')):raise ValueError('Safe native staging-relative path required')
    path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise ValueError('Duplicate native staging destination')
    return path

def stage_inputs(ids,manifest,stage):
    mapping=read(ids[manifest]);entries=mapping.get('files')
    if not isinstance(entries,list) or not entries:raise ValueError('Explicit complete native file manifest required')
    for row in entries:
        if set(row)!={'input_id','destination'} or row['input_id'] not in ids:raise ValueError('Native staging file is not a selected hash-bound input')
        # Hard links prevent a large data copy; input hashes are checked again
        # after execution. The native tool may only write its fresh output tree.
        path=_dest(stage,row['destination']);path.symlink_to(ids[row['input_id']])
    return mapping

def diann(ids,p,out):
    import numpy as np
    import pandas as pd
    header,runs=table(ids['run_manifest'],'run_id')
    if not {'raw_input_id','sample_id','unit_id','assay'}<=set(header) or {r['raw_input_id'] for r in runs}!=set(p['raw_input_ids']) or len(runs)!=len(p['raw_input_ids']):raise ValueError('One actual native run mapping per selected raw file required')
    if any(not r[k] for r in runs for k in ['run_id','sample_id','unit_id','assay']):raise ValueError('Incomplete run identity')
    if any(ids[k].suffix.lower() not in {'.mzml','.raw','.dia'} for k in p['raw_input_ids']):raise ValueError('This portable fixed route selects individual native DIA files; directory-based formats require a separately reviewed manifest')
    exe=checked_executable(p);report=out/'native_report.parquet'
    argv=[exe]
    for k in p['raw_input_ids']:argv+=['--f',ids[k]]
    argv+=['--lib',ids['spectral_library'],'--out',report,'--qvalue',p['qvalue'],'--mass-acc',p['mass_accuracy_ms2_ppm'],'--mass-acc-ms1',p['mass_accuracy_ms1_ppm'],'--window',p['scan_window'],'--threads',p['threads']]
    log=native_command(argv,out,'diann')
    version=re.search(r'\d+\.\d+(?:\.\d+)?',p['native_version'])
    if not version or version.group() not in log.read_text(encoding='utf8',errors='replace'):raise ValueError('Actual native execution log does not establish the selected DIA-NN version')
    x=pd.read_parquet(report)
    required={'Run','Precursor.Id','Protein.Group','Q.Value','Global.Q.Value','Precursor.Normalised'}
    if not required<=set(x) or x.empty or len(x)*len(x.columns)>p['maximum_output_entries']:raise ValueError('Native DIA-NN report schema/size differs from the selected contract')
    if not set(x.Run.astype(str))<=set(r['run_id'] for r in runs):raise ValueError('Native Run labels must match the explicit run mapping; no basename or suffix guessing')
    if x[['Run','Precursor.Id']].duplicated().any():raise ValueError('Repeated run/precursor identity requires explicit channel-aware handling, not averaging')
    for col in ['Q.Value','Global.Q.Value','PG.Q.Value','Global.PG.Q.Value']:
        if col in x:
            a=pd.to_numeric(x[col],errors='raise').to_numpy(dtype=float)
            if not np.isfinite(a).all() or (a<0).any() or (a>1).any():raise ValueError('Invalid native q-value channel')
    quantity=pd.to_numeric(x['Precursor.Normalised'],errors='raise')
    if np.isinf(quantity).any() or (quantity.dropna()<0).any():raise ValueError('Invalid native intensity')
    # Preserve absent quantities and native zeros separately; no imputation,
    # protein-level significance or differential test is invented here.
    mapping=pd.DataFrame(runs);x=x.merge(mapping,left_on='Run',right_on='run_id',validate='many_to_one',how='left')
    path=out/'quantification_report.tsv';x.to_csv(path,sep='\t',index=False);outputs=[(path,'quantification_report'),(report,'native_quantification_report'),(log,'native_engine_log')]
    qc=[]
    for r in runs:
        sub=x[x.Run.astype(str)==r['run_id']];q=sub['Precursor.Normalised']
        qc.append({**r,'report_rows':len(sub),'identified_precursors':sub['Precursor.Id'].nunique(),'protein_groups_in_precursor_report':sub['Protein.Group'].nunique(),'missing_quantity':int(q.isna().sum()),'native_zero_quantity':int(q.eq(0).sum()),'state':'native_report_present' if len(sub) else 'NO_NATIVE_RESULTS_REQUIRES_REVIEW','precursor_qvalue_threshold':p['qvalue']})
    path=out/'run_qc.tsv';pd.DataFrame(qc).to_csv(path,sep='\t',index=False);outputs.append((path,'run_qc'))
    path=out/'primary_results.tsv';pd.DataFrame([{'native_report_rows':len(x),'input_runs':len(runs),'runs_with_results':sum(v['report_rows']>0 for v in qc),'quantification_scope':'native_precursor_intensity','differential_analysis':'not_performed'}]).to_csv(path,sep='\t',index=False);outputs.append((path,'primary_results'))
    return outputs,{'input_runs':len(runs),'runs_with_results_fraction':sum(v['report_rows']>0 for v in qc)/len(runs),'report_rows':len(x),'missing_quantity_fraction':float(quantity.isna().mean())}

def magpie(ids,p,out,repo):
    import numpy as np
    import pandas as pd
    from scipy.spatial import Delaunay
    if p['registration_scope']!='author_default_affine_TPS':raise ValueError('This route preserves original no-HE affine / MSI-to-HE affine / HE-to-HE TPS defaults')
    stage=out/'magpie_stage';stage.mkdir();mapping=stage_inputs(ids,'registration_inputs',stage)
    samples=mapping.get('samples',[])
    if not samples or len({r['sample_id'] for r in samples})!=len(samples) or any(not r.get('unit_id') or not re.fullmatch('[A-Za-z0-9_-]+',r.get('sample_id','')) for r in samples):raise ValueError('Exact distinct section/sample and specimen-unit mapping required')
    if any(not str(row['destination']).startswith('input/') for row in mapping['files']):raise ValueError('MAGPIE manifest only stages selected input files')
    shutil.copyfile(repo/'Snakefile',stage/'Snakefile');shutil.copytree(repo/'scripts',stage/'scripts')
    (stage/'input'/'selected.txt').write_text(''.join(r['sample_id']+'\n' for r in samples),encoding='utf8')
    validation=pd.read_csv(ids['landmark_validation'],sep='\t',dtype={'sample_id':str,'spot_id':str})
    if not {'sample_id','spot_id','target_x','target_y','coordinate_unit'}<=set(validation) or validation[['sample_id','spot_id']].duplicated().any() or set(validation.sample_id)!={r['sample_id'] for r in samples} or set(validation.coordinate_unit)!={'target_hires_pixel'}:raise ValueError('Independent heldout pixel correspondences in actual target-image pixel units required for every section')
    for sample in samples:
        directory=stage/'input'/sample['sample_id'];meta=pd.read_csv(directory/'msi/MSI_metadata.csv',dtype={'spot_id':str})
        if not {'spot_id','x','y'}<=set(meta) or meta.spot_id.duplicated().any():raise ValueError('Exact measured MSI pixel identities required')
        coords=meta[['x','y']].to_numpy(dtype=float)
        if not np.isfinite(coords).all() or len(coords)>p['maximum_output_entries'] or np.linalg.matrix_rank(np.c_[np.ones(len(coords)),coords])<3:raise ValueError('Insufficient or singular measured pixel geometry')
        train=directory/('landmarks_MSI2HE.csv' if any((directory/'msi').glob('MSI_HE.*')) else 'landmarks_noHE.csv')
        points=pd.read_csv(train).iloc[:,:2].to_numpy(dtype=float)
        held=validation[validation.sample_id==sample['sample_id']].merge(meta,on='spot_id',validate='one_to_one',how='left')
        if len(held)<3 or not np.isfinite(held[['x','y','target_x','target_y']].to_numpy()).all():raise ValueError('At least three actual independent heldout correspondences required per section')
        if any(np.any(np.all(np.isclose(points,row,rtol=0,atol=0),axis=1)) for row in held[['x','y']].to_numpy()):raise ValueError('A validation correspondence was used as a training landmark')
        if np.linalg.matrix_rank(np.c_[np.ones(len(points)),points])<3:raise ValueError('Singular registration training landmarks')
        target_points=pd.read_csv(train).iloc[:,2:4].to_numpy(dtype=float)
        if target_points.shape!=points.shape or not np.isfinite(target_points).all() or np.linalg.matrix_rank(np.c_[np.ones(len(points)),target_points])<3:raise ValueError('Singular or invalid target registration landmarks')
    log=native_command([sys.executable,'-m','snakemake','--snakefile',stage/'Snakefile','--directory',stage,'--cores',p['cores']],out,'magpie',cwd=stage)
    results=[];validation_rows=[];folds=[]
    outputs=[(log,'native_engine_log')]
    for sample in samples:
        name=sample['sample_id'];path=stage/'output'/name/'transformed.csv';native=pd.read_csv(path,dtype={'spot_id':str});origin=pd.read_csv(stage/'input'/name/'msi/MSI_metadata.csv',dtype={'spot_id':str})
        if list(native.spot_id)!=list(origin.spot_id) or not np.isfinite(native[['x','y']]).all().all():raise ValueError('MAGPIE changed measured pixel identities or returned invalid coordinates')
        held=validation[validation.sample_id==name].merge(native,on='spot_id',validate='one_to_one',how='left');held['target_error_pixels']=np.hypot(held.x-held.target_x,held.y-held.target_y)
        if not np.isfinite(held.target_error_pixels).all():raise ValueError('Unmapped heldout registration pixels')
        validation_rows.extend(held.to_dict('records'))
        src=origin[['x','y']].to_numpy();dst=native[['x','y']].to_numpy();tri=Delaunay(src).simplices
        # Compare local orientation with the dominant orientation, allowing an
        # explicitly chosen global image-axis reversal. Mixed signs flag folding.
        cross=lambda a:a[:,0,0]*a[:,1,1]-a[:,0,1]*a[:,1,0]
        a=src[tri[:,1:]]-src[tri[:,0,None]];b=dst[tri[:,1:]]-dst[tri[:,0,None]];den=cross(a);valid=np.abs(den)>np.finfo(float).eps;jac=cross(b[valid])/den[valid]
        if not len(jac) or not np.isfinite(jac).all() or np.median(jac)==0:raise ValueError('Registration locally collapsed or has invalid transform geometry')
        dominant=np.sign(np.median(jac));mixed=float(np.mean(np.sign(jac)!=dominant));folds.append(mixed)
        results.append({**sample,'pixels':len(native),'heldout_landmarks':len(held),'heldout_TRE_mean_pixels':held.target_error_pixels.mean(),'heldout_TRE_max_pixels':held.target_error_pixels.max(),'mixed_local_orientation_fraction':mixed,'global_orientation_sign':int(dominant),'measurement':'registered_MSI_intensities_not_RNA_counts'})
        native['sample_id']=name;native['unit_id']=sample['unit_id'];target=out/(name+'_registered_pixels.tsv');native.to_csv(target,sep='\t',index=False);outputs.append((target,'registration_coordinates'))
        expected=stage/'output'/name/'spaceranger_aggregated/filtered_feature_bc_matrix.h5'
        if not expected.is_file():raise ValueError('Native MSI-to-Visium aggregation output absent')
    primary=out/'primary_results.tsv';pd.DataFrame(results).to_csv(primary,sep='\t',index=False);outputs.append((primary,'primary_results'))
    path=out/'registration_validation.tsv';pd.DataFrame(validation_rows).to_csv(path,sep='\t',index=False);outputs.append((path,'registration_validation'))
    manifest=out/'registration_outputs.private.json';native_files=[{'path':q.relative_to(out).as_posix(),'sha256':sha(q),'data_kind':'registered_measured_MSI_or_registration_diagnostic'} for q in (stage/'output').rglob('*') if q.is_file()];write(manifest,{'files':native_files,'not_RNA_counts':True});outputs.append((manifest,'registration_outputs'))
    outputs.extend((out/r['path'],'native_registration_artifact') for r in native_files)
    return outputs,{'sections':len(samples),'heldout_TRE_mean_pixels':float(pd.DataFrame(validation_rows).target_error_pixels.mean()),'maximum_mixed_orientation_fraction':max(folds),'registered_pixels':sum(r['pixels'] for r in results)}

def _mol2_blocks(path):
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'rt',encoding='utf8',errors='strict') as f:
        block=[]
        for line in f:
            if line.startswith('@<TRIPOS>MOLECULE') and block:
                yield ''.join(block);block=[]
            if block or line.startswith('@<TRIPOS>MOLECULE'):block.append(line)
        if block:yield ''.join(block)

def dockovalent(ids,p,out):
    import numpy as np
    import pandas as pd
    exe=checked_executable(p);stage=out/'dock_stage';stage.mkdir();mapping=stage_inputs(ids,'dock_inputs',stage)
    if set(r['input_id'] for r in mapping['files'])!=set(p['prepared_input_ids']):raise ValueError('Complete exact prepared receptor/grid/DB2 manifest required')
    indock=stage/'INDOCK'
    params={}
    for line in indock.read_text(encoding='utf8').splitlines():
        a=line.split('#',1)[0].split()
        if len(a)>=2:params[a[0]]=' '.join(a[1:])
    if params.get('dockovalent','').lower()!='yes' or params.get('chemical_matching','').lower()!='no':raise ValueError('Native covalent sampling must be enabled explicitly; ordinary docking is not substituted')
    for key in ['bond_len','len_range','len_step','bond_ang1','bond_ang2','ang1_range','ang2_range','ang1_step','ang2_step']:
        if key not in params or not math.isfinite(float(params[key])):raise ValueError('Explicit reviewed reaction-specific covalent sampling parameters required')
    destinations={r['destination'] for r in mapping['files']}
    if p['score_file'] in destinations or any(stage.glob(p['pose_glob'])):raise ValueError('Fresh native score/pose outputs cannot be supplied as prepared inputs')
    for key,value in mapping.get('indock_file_references',{}).items():
        if params.get(key)!=value or value not in destinations:raise ValueError('Prepared INDOCK file reference is not bound to the selected source manifest')
    if not mapping.get('indock_file_references'):raise ValueError('Explicit native INDOCK input reference audit required')
    reactions=read(ids['reaction_mapping']);ligands=reactions.get('ligands')
    if reactions.get('chemistry_reviewed') is not True or reactions.get('receptor_sha256')!=sha(ids['receptor']) or not isinstance(ligands,list) or not ligands or len({r['ligand_id'] for r in ligands})!=len(ligands):raise ValueError('Actual receptor/reaction atom mapping and complete ligand inventory required')
    atoms={}
    for line in ids['receptor'].read_text(encoding='utf8').splitlines():
        if line.startswith(('ATOM  ','HETATM')):
            key=int(line[6:11]);xyz=tuple(float(line[a:b]) for a,b in [(30,38),(38,46),(46,54)])
            if key in atoms:raise ValueError('Ambiguous receptor atom serial across models')
            atoms[key]=xyz
    if any(r.get('receptor_atom_serial') not in atoms or not r.get('ligand_atom_name') for r in ligands):raise ValueError('Mapped covalent receptor/ligand atom absent')
    log=native_command([exe],out,'dockovalent',cwd=stage)
    score=stage/p['score_file']
    if not score.resolve().is_relative_to(stage) or not score.is_file():raise ValueError('Native OUTDOCK score output absent')
    columns=p['native_score_columns']
    if len(columns)!=len(set(columns)) or not {'ligand_id','total'}<=set(columns):raise ValueError('Explicit actual native OUTDOCK field order required')
    records=[]
    for line in score.read_text(encoding='utf8').splitlines():
        a=line.split()
        if len(a)!=len(columns) or not a[0].isdigit():continue
        row=dict(zip(columns,a));value=float(row['total'])
        if not math.isfinite(value):raise ValueError('Nonfinite native docking energy')
        row['total']=value;records.append(row)
    if not records or len(records)*len(columns)>p['maximum_output_entries']:raise ValueError('No supported actual native OUTDOCK rows or declared output budget exceeded')
    expected={r['ligand_id']:r for r in ligands}
    if not {r['ligand_id'] for r in records}<=set(expected):raise ValueError('Native ligand identities differ from the reviewed DB2 inventory')
    outputs=[(log,'native_engine_log'),(score,'native_score_log')];geometry=[];pose_index=[]
    for path in sorted(stage.glob(p['pose_glob'])):
        if not path.is_file() or not path.resolve().is_relative_to(stage):raise ValueError('Pose leaves fresh native output directory')
        outputs.append((path,'pose_files'))
        for block in _mol2_blocks(path):
            lines=block.splitlines();name=lines[1]
            if name not in expected:raise ValueError('Native MOL2 pose name is not a literal selected ligand identity')
            start=lines.index('@<TRIPOS>ATOM')+1;coords={}
            for line in lines[start:]:
                if line.startswith('@<TRIPOS>'):break
                a=line.split()
                if len(a)<6:raise ValueError('Malformed actual native pose atom')
                if a[1] in coords:raise ValueError('Ambiguous ligand atom names in native pose')
                coords[a[1]]=tuple(map(float,a[2:5]))
            r=expected[name]
            if r['ligand_atom_name'] not in coords:raise ValueError('Actual covalent warhead atom absent in returned pose')
            distance=float(np.linalg.norm(np.asarray(coords[r['ligand_atom_name']])-atoms[r['receptor_atom_serial']]))
            if not math.isfinite(distance):raise ValueError('Invalid actual returned pose coordinates')
            geometry.append({'ligand_id':name,'pose_file':path.relative_to(out).as_posix(),'pose_index':len(geometry)+1,'bond_distance_angstrom':distance,'within_prespecified_distance':p['bond_distance_angstrom'][0]<=distance<=p['bond_distance_angstrom'][1],'topology_acceptance':'requires_independent_chemical_review'})
    if not geometry:raise ValueError('Native covalent pose coordinates required; scores alone do not complete docking')
    coverage=[{'ligand_id':name,'native_score_rows':sum(r['ligand_id']==name for r in records),'native_pose_rows':sum(r['ligand_id']==name for r in geometry),'status':'RETURNED' if any(r['ligand_id']==name for r in geometry) else 'NO_POSE_NOT_A_BIOLOGICAL_NEGATIVE'} for name in expected]
    for filename,data,role in [('docking_scores.tsv',records,'docking_scores'),('covalent_geometry.tsv',geometry,'covalent_geometry'),('ligand_coverage.tsv',coverage,'ligand_coverage')]:
        path=out/filename;pd.DataFrame(data).to_csv(path,sep='\t',index=False);outputs.append((path,role))
    path=out/'primary_results.tsv';pd.DataFrame([{'input_ligands':len(expected),'ligands_with_pose':sum(r['native_pose_rows']>0 for r in coverage),'returned_poses':len(geometry),'scores_meaning':'native_docking_energy_not_measured_affinity_or_reactivity'}]).to_csv(path,sep='\t',index=False);outputs.append((path,'primary_results'))
    return outputs,{'input_ligands':len(expected),'ligands_with_pose_fraction':sum(r['native_pose_rows']>0 for r in coverage)/len(expected),'poses_outside_declared_distance':sum(not r['within_prespecified_distance'] for r in geometry)}
