"""Guarded, weight-free native evaluation, distinct from fixed-pose constraint QC.

Scientific imports are deferred until the allocated-server guard. Every origin
attempt is retained, including sampling failures without raw molecular output.
"""
from pathlib import Path
from contextlib import contextmanager
import ast,csv,importlib.metadata,json,math,os,re,shutil,struct,zipfile
from contracts import read,write,sha,digest,selected

RAW_KEYS={'atoms','positions','formal_charges','bonds','surface','esp','pharm_types','pharm_positions','pharm_vectors'}
SCORES=('sims_surf_target','sims_esp_target','sims_pharm_target','sims_surf_target_relax','sims_esp_target_relax','sims_pharm_target_relax','sims_surf_target_relax_optimal','sims_esp_target_relax_optimal','sims_pharm_target_relax_optimal','sims_pharm_priority_target_relax_optimal','sims_pharm_nonpriority_target_relax_optimal')

def _json_safe(value):
    """Native missing/nonfinite becomes null, never a manufactured zero."""
    if value is None or isinstance(value,(str,bool,int)):return value
    if isinstance(value,float):return value if math.isfinite(value) else None
    if isinstance(value,dict):return {str(k):_json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_json_safe(v) for v in value]
    if hasattr(value,'tolist'):return _json_safe(value.tolist())
    if hasattr(value,'item'):return _json_safe(value.item())
    raise TypeError('Unsupported native export value: '+type(value).__name__)

def _table(path,rows,fields):
    with Path(path).open('x',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,delimiter='\t',extrasaction='raise');writer.writeheader();writer.writerows(rows)

def _archive(path,max_bytes,keys):
    """Bound ZIP expansion before numpy reads; pickle is never allowed."""
    if path.stat().st_size>max_bytes:raise ValueError('NPZ compressed size exceeds approved budget')
    with zipfile.ZipFile(path) as z:
        files=z.infolist();names=[x.filename for x in files]
        if len(names)!=len(set(names)) or set(names)!={x+'.npy' for x in keys}:raise ValueError('NPZ keys differ from exact native schema')
        if any(x.flag_bits&1 for x in files) or sum(x.file_size for x in files)>max_bytes:raise ValueError('NPZ encrypted/expanded size exceeds approved budget')
        # ZIP size alone cannot bound a forged NPY shape: numpy can allocate the
        # advertised array before discovering a short payload. Inspect headers
        # without numpy before handing any member to its loader.
        for info in files:
            with z.open(info) as f:
                if f.read(6)!=b'\x93NUMPY':raise ValueError('Native NPZ member is not an NPY array')
                version=f.read(2)
                if version==b'\x01\x00':width=2
                elif version in (b'\x02\x00',b'\x03\x00'):width=4
                else:raise ValueError('Unsupported NPY header version')
                length_bytes=f.read(width)
                if len(length_bytes)!=width:raise ValueError('Truncated NPY header')
                length=struct.unpack('<H' if width==2 else '<I',length_bytes)[0]
                if length>65536:raise ValueError('Oversized NPY header')
                text=f.read(length)
                if len(text)!=length:raise ValueError('Truncated NPY header')
                header=ast.literal_eval(text.decode('utf8' if version==b'\x03\x00' else 'latin1'))
                if not isinstance(header,dict) or set(header)!={'descr','fortran_order','shape'} or type(header['fortran_order']) is not bool:raise ValueError('Unexpected NPY metadata')
                shape=header['shape'];dtype=header['descr']
                if not isinstance(shape,tuple) or len(shape)>8 or any(type(x) is not int or x<0 for x in shape) or not isinstance(dtype,str) or not re.fullmatch(r'[<>=|]?[biuf][0-9]+',dtype):raise ValueError('Object/structured/invalid NPY shape or dtype refused')
                width_bytes=int(re.search(r'[0-9]+$',dtype)[0]);payload=math.prod(shape)*width_bytes
                if not 0<width_bytes<=16 or payload>max_bytes or payload!=info.file_size-(8+width+length):raise ValueError('NPY advertised allocation/payload exceeds bounded source bytes')

def _origin_attempts(origin):
    try:from .lineage import bound_output
    except ImportError:from lineage import bound_output
    n=origin['origin']['parameters']['n_samples'];names=['generated_'+str(i) for i in range(n)]
    if type(n) is not int or n<1:raise ValueError('Positive origin requested denominator required')
    f=bound_output(origin,origin['variant']+'/candidate_denominator.tsv')
    with f.open(encoding='utf8',newline='') as stream:rows=list(csv.DictReader(stream,delimiter='\t'))
    if len(rows)!=n or any(None in x or any(v is None for v in x.values()) for x in rows):raise ValueError('Origin attempt denominator ragged/incomplete')
    if len({x['candidate_id'] for x in rows})!=n or {x['candidate_id'] for x in rows}!=set(names):raise ValueError('Origin denominator must include every candidate exactly once')
    counts=origin['contract']['resolved_sample_counts']
    if len(counts)!=n or {x['candidate_id'] for x in counts}!=set(names):raise ValueError('Generation count schedule changed')
    return names,{x['candidate_id']:x for x in rows},{x['candidate_id']:x for x in counts},f

def _capture_pipeline(base,sink):
    """Keep audit state outside attrs consumed by native to_pandas."""
    class AuditedConditionalEvalPipeline(base):
        def _process_single_result(self,res,i):
            if type(i) is not int or res.get('i')!=i or i in sink:raise ValueError('Duplicate/mismatched native callback')
            for key in ('is_valid','is_valid_post_opt','is_graph_consistent'):
                if type(res.get(key)) is not bool:raise ValueError('Native callback validity schema changed')
            sink[i]=_json_safe(res)
            return super()._process_single_result(res,i)
    return AuditedConditionalEvalPipeline

def _native_input(np,path,budget,max_atoms,expected_count):
    _archive(path,budget,RAW_KEYS)
    with np.load(path,allow_pickle=False) as raw:atoms=raw['atoms'].copy();positions=raw['positions'].copy()
    if atoms.ndim!=1 or atoms.shape!=(expected_count,) or atoms.dtype.kind not in 'iu' or positions.dtype.kind not in 'fiu' or positions.shape!=(len(atoms),3):raise ValueError('Raw atom/coordinate axis differs from generation schedule')
    if not np.isfinite(positions).all() or len(atoms)>max_atoms or not ((atoms>=0)&(atoms<=118)).all():raise ValueError('Raw atom scope/coordinates invalid')
    keep=atoms!=0
    if not keep.any():raise ValueError('No real atoms in native output')
    return (atoms[keep],positions[keep]),{'raw_slots':len(atoms),'dummy_atoms_removed':int((~keep).sum()),'evaluated_atoms':int(keep.sum()),'coordinates_unit':'angstrom','source_coordinate_state':'generation_raw_source_frame'}

def _reference(np,Chem,Molecule,origin,reference_id,budget,tolerance,out):
    try:from .lineage import bound_output
    except ImportError:from lineage import bound_output
    rows=[x for x in origin['structures']['molecules'] if x['id']==reference_id and x['role']=='reference'];snapshots=[x for x in origin['contract']['reference_snapshots'] if x['reference_id']==reference_id]
    if len(rows)!=1 or len(snapshots)!=1:raise ValueError('One exact full generation reference required')
    row,snapshot=rows[0],snapshots[0];sdf=selected(origin['origin_root'],row['sdf']['path'])
    if sha(sdf)!=row['sdf']['sha256'] or snapshot['source_sdf_sha256']!=sha(sdf):raise ValueError('Reference SDF differs from generation lineage')
    axes_file=bound_output(origin,origin['variant']+'/'+reference_id+'.axes.private.json');axes=read(axes_file)
    profile_file=bound_output(origin,origin['variant']+'/profile_'+reference_id+'.npz')
    _archive(profile_file,budget,{'surface','esp','charges','pharm_types','pharm_positions','pharm_vectors'})
    with np.load(profile_file,allow_pickle=False) as stored:q=stored['charges'].copy()
    loaded=list(Chem.SDMolSupplier(str(sdf),removeHs=False,sanitize=True))
    if len(loaded)!=1 or loaded[0] is None:raise ValueError('Reference must be one sanitized source state')
    mol=loaded[0]
    if mol.GetNumConformers()!=1 or not mol.GetConformer().Is3D() or q.dtype.kind not in 'fiu' or q.shape!=(mol.GetNumAtoms(),) or not np.isfinite(q).all():raise ValueError('Reference geometry/charge axis invalid')
    if Chem.GetFormalCharge(mol)!=row['formal_charge'] or abs(float(q.sum())-row['formal_charge'])>tolerance:raise ValueError('Reference chemical state/charge sum changed')
    atom_axis=[{'atomic_number':a.GetAtomicNum(),'formal_charge':a.GetFormalCharge(),'isotope':a.GetIsotope()} for a in mol.GetAtoms()]
    if digest(atom_axis)!=snapshot['atom_axis_sha256'] or axes.get('atom_axis_sha256')!=digest(atom_axis) or axes.get('source_sdf_sha256')!=sha(sdf):raise ValueError('Reference exact atom axis changed')
    ref=Molecule(Chem.Mol(mol),num_surf_points=400,probe_radius=1.2,partial_charges=q,pharm_multi_vector=False)
    if not np.array_equal(np.asarray(ref.partial_charges),q):raise ValueError('Native reference changed selected charge model')
    points=[{'type':int(t),'position_angstrom':[round(float(x),6) for x in pos],'direction':[round(float(x),6) for x in vec]} for t,pos,vec in zip(ref.pharm_types,ref.pharm_ancs,ref.pharm_vecs)]
    if digest(points)!=snapshot['pharmacophore_axis_sha256'] or axes.get('pharmacophore_axis_sha256')!=digest(points):raise ValueError('Full reference pharmacophore ordering changed')
    if np.asarray(ref.surf_pos).shape!=(400,3) or np.asarray(ref.surf_esp).shape!=(400,) or not np.isfinite(ref.surf_pos).all() or not np.isfinite(ref.surf_esp).all():raise ValueError('Native reference surface/ESP extraction failed')
    binding={'schema':'private-native-evaluation-reference/1','reference_id':reference_id,'source_sdf_sha256':sha(sdf),'source_axes_sha256':sha(axes_file),'source_profile_sha256':sha(profile_file),'atom_axis_sha256':digest(atom_axis),'pharmacophore_axis_sha256':digest(points),'full_pharmacophore_count':len(points),'surface_points':400,'probe_radius_angstrom':1.2,'partial_charges_from_exact_origin_profile':True,'conditioning_neutralized_ESP':snapshot['conditioning_ESP_neutralized'],'evaluation_ESP':'raw_GFN2_xTB_atomic_charge_Coulomb_surface','surface_resampled_for_evaluation':True,'coordinates_unit':'angstrom','scientific_acceptance':'NOT_ESTABLISHED'}
    write(out/'reference_binding.private.json',binding)
    np.savez_compressed(out/'reference_evaluation_profile.npz',surface=ref.surf_pos,esp=ref.surf_esp,charges=q,pharm_types=ref.pharm_types,pharm_positions=ref.pharm_ancs,pharm_vectors=ref.pharm_vecs)
    return ref,snapshot,[(sdf,sha(sdf)),(axes_file,sha(axes_file)),(profile_file,sha(profile_file))]

def _priority(snapshot,reference,policy,condition):
    if policy=='none':return None,'NOT_REQUESTED'
    mask=snapshot['resolved_priority_mask_on_full_reference_axis'];n=len(reference.pharm_types)
    if condition not in ('all','pharm') or len(mask)!=n or any(type(x) is not int or x not in (0,1) for x in mask):raise ValueError('Priority mask differs from complete reference axis')
    if not any(mask):return None,'NO_PRIORITY_SUBSET_IN_ORIGIN_MASK'
    if all(mask):return None,'NO_NONPRIORITY_COMPLEMENT_IN_ORIGIN_MASK'
    return [i for i,x in enumerate(mask) if x],'FULL_PHARM_ALIGNMENT_THEN_REFERENCE_TVERSKY_FOR_BOTH_SUBSETS'

@contextmanager
def _owned_native_work(out,modules):
    """Cover native module constants and defaults that captured Path('./')."""
    work=(Path(out)/'native_work').resolve();work.mkdir(exist_ok=False)
    previous_cwd=Path.cwd();marker=object();previous_env={k:os.environ.get(k,marker) for k in ('TMPDIR','TEMP','TMP')}
    previous_modules=[(module,getattr(module,'TMPDIR',marker)) for module in modules]
    try:
        for key in previous_env:os.environ[key]=str(work)
        for module,_ in previous_modules:module.TMPDIR=work
        os.chdir(work);yield work
    finally:
        os.chdir(previous_cwd)
        for module,value in previous_modules:
            if value is marker:delattr(module,'TMPDIR')
            else:module.TMPDIR=value
        for key,value in previous_env.items():
            if value is marker:os.environ.pop(key,None)
            else:os.environ[key]=value

def run_native_evaluation(request,ids,root,output,seed):
    """Return one variant summary; runtime owns variant loop and outer receipt."""
    try:
        from .runtime import guard
        from .lineage import load_origin,bound_output
        from .identity import verify
        from .xtb_audit import XtbAudit,identify_xtb
    except ImportError:
        from runtime import guard
        from lineage import load_origin,bound_output
        from identity import verify
        from xtb_audit import XtbAudit,identify_xtb
    guard(request)
    if request['method']!='paper_native_evaluation' or request['parameters']['workers']!=1:raise ValueError('One-worker native evaluation route required')
    out=Path(output).resolve(strict=True);p=request['parameters'];origin=load_origin(request,ids,root)
    if p['solvent']!=origin['origin']['parameters']['solvent']:raise ValueError('Origin reference charges use another solvent; regenerate/review reference explicitly')
    if not out.is_dir() or any(out.iterdir()):raise ValueError('Fresh runtime-owned empty variant directory required')
    variants={'primary':p['seed'],**{x['label']:x['seed'] for x in request['sensitivity_variants']}}
    if out.name not in variants or variants[out.name]!=seed:raise ValueError('Runtime variant/seed differs from approval')
    software=read(ids['software']);identities=verify(software,['shepherd-score'])
    versions={key:importlib.metadata.version(key) for key in p['expected_versions']}
    if versions!=p['expected_versions']:raise ValueError('Actual server dependency versions differ from review')
    xtb=identify_xtb(p['expected_xtb_sha256'],p['expected_xtb_version'],out)
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import numpy as np,torch,open3d as o3d,shepherd_score
    from rdkit import Chem
    from shepherd_score.container import Molecule
    from shepherd_score.evaluations.evaluate import pipelines
    from shepherd_score.evaluations.evaluate import evals,_pipeline_eval_single
    import shepherd_score.conformer_generation as conformer_generation
    if torch.cuda.is_available():raise ValueError('CPU native evaluation cannot silently use CUDA')
    if Path(shepherd_score.__file__).resolve().parent!=Path(software['source_roots']['shepherd-score']).resolve():raise ValueError('Imported score module differs from pinned root')
    np.random.seed(seed);torch.manual_seed(seed);o3d.utility.random.seed(seed)
    names,source_rows,counts,denom_file=_origin_attempts(origin)
    contract_file=bound_output(origin,origin['variant']+'/generation_contract.private.json')
    if read(contract_file)!=origin['contract']:raise ValueError('Origin contract changed while loading')
    snapshots={'origin_request_snapshot.private.json':origin['origin_path'],'origin_receipt_snapshot.private.json':selected(origin['returned'],'receipt.private.json'),'origin_generation_contract_snapshot.private.json':contract_file}
    for name,f in snapshots.items():shutil.copyfile(f,out/name)
    if sha(out/'origin_request_snapshot.private.json')!=origin['spec']['origin_request_sha256'] or sha(out/'origin_receipt_snapshot.private.json')!=origin['spec']['origin_receipt_sha256']:raise ValueError('Origin snapshot hashes changed')
    bound=[(denom_file,sha(denom_file)),(contract_file,sha(contract_file))]+[(f,sha(f)) for f in snapshots.values()]
    for filename,key in (('source_context.private.json','context'),('source_structures.private.json','structures')):
        f=bound_output(origin,filename)
        if read(f)!=origin[key]:raise ValueError('Origin source context/manifest changed')
        bound.append((f,sha(f)))
    ref,snapshot,reference_bound=_reference(np,Chem,Molecule,origin,origin['spec']['reference_id'],p['max_native_npz_bytes'],p['charge_sum_tolerance'],out);bound.extend(reference_bound)
    priority,priority_scope=_priority(snapshot,ref,p['priority_policy'],p['condition'])
    inputs=[];native_to_source={};records=[];callbacks={};origin_charge=origin['origin']['parameters']['generated_formal_charge']
    for name in names:
        record={'candidate_id':name,'origin_generation_variant':origin['variant'],'origin_generation_state':source_rows[name]['state'],'state':'INPUT_UNAVAILABLE','native_i':None,'input_error':None,'error':None,'native_is_valid':None,'native_is_valid_post_opt':None,'native_is_graph_consistent':None,'raw_path':None,'raw_sha256':None,'source_report_sha256':None,'expected_raw_atom_slots':counts[name]['N_x1'],'origin_reconstruction_formal_charge':origin_charge,'engine_evidence_complete':False,'native_reconstruction_charge_matches_origin_declared':None}
        raw_name=origin['variant']+'/'+name+'.raw.npz';report_name=origin['variant']+'/'+name+'.constraints.private.json'
        if report_name not in origin['outputs']:raise ValueError('Every requested attempt needs an exact source candidate report')
        f=bound_output(origin,report_name);bound.append((f,sha(f)));report=read(f)
        if report.get('candidate_id')!=name or report.get('generation_contract_sha256')!=sha(contract_file) or report.get('generation_options_sha256')!=origin['contract']['generation_options_sha256']:raise ValueError('Source candidate contract lineage changed')
        record['source_report_sha256']=sha(f)
        if raw_name not in origin['outputs']:
            record['input_error']='ORIGIN_ATTEMPT_HAS_NO_REGISTERED_RAW_NPZ'
            if (origin['returned']/raw_name).exists():raise ValueError('Unregistered raw output outside origin receipt')
        else:
            f=bound_output(origin,raw_name);bound.append((f,sha(f)));record.update(raw_path=raw_name,raw_sha256=sha(f))
            try:
                value,details=_native_input(np,f,p['max_native_npz_bytes'],p['max_atoms'],counts[name]['N_x1'])
                record.update(details);record['native_i']=len(inputs);record['state']='AWAITING_NATIVE_CALLBACK';native_to_source[len(inputs)]=name;inputs.append(value)
            except (ValueError,TypeError,KeyError,OSError,zipfile.BadZipFile) as error:record['input_error']=type(error).__name__+': '+str(error);record['state']='INPUT_INVALID'
        records.append(record)
    lineage={'schema':'private-paper-native-lineage/1','lineage_spec':origin['spec'],'source_review':origin['source_review'],'frame_id':origin['context']['frame_id'],'origin_request_sha256':origin['spec']['origin_request_sha256'],'origin_receipt_sha256':origin['spec']['origin_receipt_sha256'],'origin_generation_contract_sha256':sha(contract_file),'origin_variant':origin['variant'],'reference_id':origin['spec']['reference_id'],'expected_attempts':len(names),'candidate_ids':names,'priority_indices_full_reference_axis':priority,'priority_scope':priority_scope,'native_evaluation_condition':p['condition'],'origin_declared_modalities':origin['origin']['parameters']['generation_options']['condition_modalities'],'native_i_to_candidate_id':{str(k):v for k,v in native_to_source.items()},'eligible_only_filter_used':False,'scientific_acceptance':'NOT_ESTABLISHED'}
    write(out/'origin_lineage.private.json',lineage)
    write(out/'software_identity.private.json',{'python_sources':identities,'versions':versions,'xtb_identity':xtb,'generation_weights_loaded':False,'scientific_acceptance':'NOT_ESTABLISHED'})
    failure=None;global_values={};native_rows=[];original_single=pipelines._eval_conditional_single
    pipeline_invoked=False;pipeline_completed=False;pandas_export_completed=False
    with _owned_native_work(out,[conformer_generation,evals,_pipeline_eval_single]) as work,XtbAudit(conformer_generation,out/'xtb_audit',xtb,p['xtb_timeout_seconds'],p['charge_sum_tolerance'],p['max_atoms'],work) as audit:
        try:
            if inputs:
                def audited_single(*args,**kwargs):
                    i=args[0]
                    with audit.candidate(native_to_source[i],i):return original_single(*args,**kwargs)
                pipelines._eval_conditional_single=audited_single
                Pipeline=_capture_pipeline(pipelines.ConditionalEvalPipeline,callbacks)
                evaluator=Pipeline(ref_molec=ref,generated_mols=inputs,condition=p['condition'],num_surf_points=400,pharm_multi_vector=False,solvent=p['solvent'],priority_pharm_indices=priority)
                pipeline_invoked=True
                evaluator.evaluate(num_processes=p['xtb_cores'],num_workers=1,verbose=False,timeout_minutes=p['xtb_timeout_seconds']/60,mp_context='spawn')
                pipeline_completed=True
                global_series,frame=evaluator.to_pandas();global_values=_json_safe(global_series.to_dict());native_rows=_json_safe(frame.to_dict(orient='records'))
                if len(native_rows)!=len(inputs):raise ValueError('Native pandas row denominator changed')
                pandas_export_completed=True
        except Exception as error:failure=type(error).__name__+': '+str(error)
        finally:pipelines._eval_conditional_single=original_single
    mandatory={'surface':['sims_surf_target_relax_optimal'],'esp':['sims_esp_target_relax_optimal'],'pharm':['sims_pharm_target_relax_optimal'],'all':['sims_surf_target_relax_optimal','sims_esp_target_relax_optimal','sims_pharm_target_relax_optimal']}[p['condition']]
    if priority is not None:mandatory=mandatory+['sims_pharm_priority_target_relax_optimal','sims_pharm_nonpriority_target_relax_optimal']
    callback_rows=[]
    molecules=out/'native_molecules';molecules.mkdir()
    for record in records:
        i=record['native_i'];result=callbacks.get(i) if i is not None else None
        calls=[x for x in audit.records if x['candidate_id']==record['candidate_id']]
        record['engine_calls']=len(calls);record['engine_failures']=sum(x.get('returncode')!=0 or x.get('exception_type') is not None for x in calls)
        record['engine_evidence_complete']=len(calls)==2 and {x['stage'] for x in calls}=={'single_point','relaxation'} and all(x.get('evidence_complete') is True for x in calls)
        record['native_reconstruction_charge_matches_origin_declared']=all(x['requested_formal_charge']==origin_charge for x in calls) if calls else None
        record['pipeline_failure']=failure;record['error']=result.get('error') if result else record['input_error'] or failure or 'NATIVE_CALLBACK_MISSING'
        for key in ('is_valid','is_valid_post_opt','is_graph_consistent'):record['native_'+key]=result[key] if result else None
        for key in SCORES:record[key]=result.get('sim'+key[4:]) if result else None
        for key in ('strain_energy','rmsd','smiles','smiles_post_opt'):record[key]=result.get(key) if result else None
        record['native_scoring_complete']=all(type(record[k]) in (int,float) and math.isfinite(record[k]) for k in mandatory)
        record['strain_energy_unit']='hartree';record['rmsd_unit']='angstrom';record['eligible_for_docking']=False
        if result:
            if not result['is_valid'] or not result['is_valid_post_opt']:record['state']='NATIVE_EVALUATION_FAILED_OR_PARTIAL'
            elif not result['is_graph_consistent'] or not record['engine_evidence_complete'] or not record['native_reconstruction_charge_matches_origin_declared'] or not record['native_scoring_complete']:record['state']='NATIVE_EVALUATION_AUDIT_HOLD'
            else:record['state']='NATIVE_EVALUATED_REQUIRES_SCIENTIFIC_REVIEW'
        elif i is not None:record['state']='NATIVE_CALLBACK_MISSING'
        # Keep native molecular material as hash-bound files, not large JSON cells.
        native_result=dict(result) if result else None;native_artifacts={}
        if native_result:
            for key in ('molblock','molblock_post_opt'):
                text=native_result.pop(key,None)
                if text is not None:
                    path=molecules/(record['candidate_id']+'.'+key+'.mol');path.write_text(text,encoding='utf8')
                    native_artifacts[key]={'path':path.relative_to(out).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size}
                else:native_artifacts[key]=None
        callback_rows.append({'candidate_id':record['candidate_id'],'state':record['state'],'native_i':i,'error':record['error'],'native_result':native_result,'native_artifacts':native_artifacts,'native_large_fields_externalized':['molblock','molblock_post_opt'] if result else [],'raw_sha256':record['raw_sha256'],'source_report_sha256':record['source_report_sha256'],'origin_generation_state':record['origin_generation_state'],'engine_call_indices':[x['call_index'] for x in calls],'missing_scopes':(['RAW_INPUT_UNAVAILABLE_OR_INVALID'] if i is None else ['NATIVE_CALLBACK_UNAVAILABLE'] if result is None else [])+(['ENGINE_EVIDENCE_INCOMPLETE'] if not record['engine_evidence_complete'] else [])+(['REQUESTED_NATIVE_SCORES_INCOMPLETE'] if not record['native_scoring_complete'] else [])})
    # A list, in original requested order, is deliberate: no lost failures, no
    # appearance of a complete denominator from valid-only native pandas exports.
    write(out/'callback_results.private.json',callback_rows)
    write(out/'native_records.private.json',records)
    write(out/'native_dataframe.private.json',native_rows)
    write(out/'engine_audit.private.json',{'schema':'private-paper-native-engine-audit/1','calls':audit.records,'capture_errors':audit.capture_errors,'xtb_identity':xtb,'single_worker':True,'method_cli_explicit':False,'energy_unit':'hartree','timeout_scope':'each_xtb_subprocess_not_whole_molecule_or_batch','scientific_acceptance':'NOT_ESTABLISHED'})
    write(out/'native_global_metrics.private.json',{'schema':'private-native-global-metrics/1','native_metrics':global_values,'native_denominator':len(inputs),'all_requested_denominator':len(names),'priority_scope':priority_scope,'energy_unit':'hartree','timeout_scope':'each_xtb_subprocess_not_whole_molecule_or_batch','independent_modality_optimal_alignment':True,'one_joint_docking_pose_established':False,'native_dataframe_complete':pandas_export_completed,'scientific_acceptance':'NOT_ESTABLISHED'})
    write(out/'evaluation_metadata.private.json',{'schema':'private-paper-native-evaluation/1','origin_generation_contract_sha256':sha(contract_file),'reference_binding_sha256':sha(out/'reference_binding.private.json'),'expected_attempts':len(names),'native_input_count':len(inputs),'native_callback_count':len(callbacks),'required_score_fields':mandatory,'native_pandas_columns':list(native_rows[0]) if native_rows else [],'native_pandas_rows':len(native_rows),'native_dataframe_artifact':{'path':'native_dataframe.private.json','sha256':sha(out/'native_dataframe.private.json')},'native_dataframe_is_full_export':pandas_export_completed,'pipeline_invoked':pipeline_invoked,'pipeline_completed':pipeline_completed,'pipeline_failure':failure,'priority_scope':priority_scope,'condition':p['condition'],'pharm_multi_vector':False,'surface_points':400,'probe_radius_angstrom':1.2,'reference_pharmacophore_axis':'full_origin_axis_not_trimmed_priority_only_condition','relaxation':'native_xtb_default_method_expected_GFN2_requires_version_review','energy_unit':'hartree','method_cli_explicit':False,'independently_aligned_modalities':True,'post_opt_molblock_frame':'RMSD_aligned_to_original_generated_geometry_not_one_pose_for_independent_modal_scores','fixed_pose_constraints_reassessed':False,'docking_eligibility_established':False,'timeout_seconds':p['xtb_timeout_seconds'],'timeout_scope':'each_xtb_subprocess_not_whole_molecule_or_batch','generation_weights_loaded':False,'seed':seed,'precision_scope':'technical_seed_variability_not_biological_replication','native_nonfinite_or_missing_serialized_as_null':True,'scientific_acceptance':'NOT_ESTABLISHED'})
    fields=list(dict.fromkeys(k for row in records for k in row));_table(out/'native_evaluation.tsv',records,fields)
    for f,h in bound:
        if sha(f)!=h:raise ValueError('Exact origin scientific artifact changed during evaluation')
    verify(software,['shepherd-score'])
    if sha(xtb['executable'])!=p['expected_xtb_sha256']:raise ValueError('xTB binary changed during evaluation')
    n=len(names);complete=sum(row['state']=='NATIVE_EVALUATED_REQUIRES_SCIENTIFIC_REVIEW' for row in records)
    metrics={'requested_attempts':n,'input_evaluable_count':len(inputs),'input_evaluable_fraction':len(inputs)/n,'native_callback_count':len(callbacks),'native_valid_count':sum(row['native_is_valid'] is True for row in records),'native_post_opt_valid_count':sum(row['native_is_valid_post_opt'] is True for row in records),'native_graph_consistent_count':sum(row['native_is_graph_consistent'] is True for row in records),'engine_evidence_complete_count':sum(row['engine_evidence_complete'] for row in records),'native_evaluation_audit_complete_count':complete,'native_evaluation_audit_complete_fraction':complete/n,'pipeline_completed':pipeline_completed}
    for key in ('native_valid','native_post_opt_valid','native_graph_consistent'):metrics[key+'_fraction_all_requested']=metrics[key+'_count']/n
    return {'metrics':metrics,'expected_attempts':n,'eligible_outputs':[],'origin_variant':origin['variant'],'origin_request_sha256':origin['spec']['origin_request_sha256'],'origin_receipt_sha256':origin['spec']['origin_receipt_sha256'],'reference_id':origin['spec']['reference_id'],'priority_scope':priority_scope,'minimum_evaluable_fraction_met':metrics['input_evaluable_fraction']>=p['minimum_evaluable_fraction'],'pipeline_failure':failure,'runtime_execution':'EXECUTED_ON_APPROVED_SERVER' if pipeline_invoked else 'NOT_RUN_NO_EVALUABLE_INPUT_OR_INITIALIZATION_FAILED','score_semantics':'native_relaxation_and_independently_optimal_modality_similarities_not_docking_or_binding_energy','energy_unit':'hartree','method_cli_explicit':False,'default_gfn_mode_independently_verified':False,'scientific_acceptance':'NOT_ESTABLISHED','biological_replication_established':False}
