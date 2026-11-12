"""Existing allocated-server entry. Refuses local/WSL execution before scientific imports."""
from pathlib import Path
import sys,os,platform,socket,subprocess,datetime,traceback,csv,math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contracts import read,sha,write,digest,validate,selected,sources
def guard(r):
    if sys.platform!='linux' or 'microsoft' in platform.release().lower():raise RuntimeError('No local scientific execution; use the existing allocated server')
    if r.get('expected_host')!=socket.gethostname() or r.get('node_role')!='compute' or any(x in socket.gethostname().lower() for x in ('login','headnode')):raise RuntimeError('Fresh current compute host required')
    if r.get('server_execution_authorized') is not True or not (os.getenv('SLURM_JOB_ID') or os.getenv('SSH_CONNECTION')):raise RuntimeError('Explicit dispatch through existing authorized server route required')
    body={k:v for k,v in r.items() if k!='plan_sha256'};body['server_execution_authorized']=False
    if r.get('submission_state')!='NOT_SUBMITTED' or digest(body)!=r['plan_sha256'] or sources()!=r['source_sha256']:raise RuntimeError('Approved source/plan changed or submission unknown; never retry automatically')
    validate({**r,'server_execution_authorized':False})
    cpus=r['resource_budget']['cpus']
    if 'SLURM_CPUS_PER_TASK' in os.environ and cpus>int(os.environ['SLURM_CPUS_PER_TASK']):raise RuntimeError('CPU request exceeds actual allocation')
    for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]=str(cpus)
def offline():
    for k,v in {'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','WANDB_MODE':'disabled'}.items():os.environ[k]=v
    original=socket.socket.connect
    def connect(s,address):
        if s.family in (socket.AF_INET,socket.AF_INET6):raise RuntimeError('Scientific worker cannot download or upload data')
        return original(s,address)
    def connect_ex(s,address):raise RuntimeError('Outbound network disabled')
    def sendto(s,*a):raise RuntimeError('Outbound datagrams disabled')
    socket.socket.connect=connect;socket.socket.connect_ex=connect_ex;socket.socket.sendto=sendto
def run(request,out):
    request=Path(request).resolve();r=read(request);guard(r);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False);root=request.parent
    receipt={'schema':'private-interaction-receipt/1','state':'RUNNING','run_id':r['run_id'],'method':r['method'],'host':socket.gethostname(),'request_sha256':sha(request),'plan_sha256':r['plan_sha256'],'source_sha256':r['source_sha256'],'inputs':[],'outputs':[],'public_upload':False,'automatic_retry':False,'scientific_acceptance':'NOT_ESTABLISHED','started':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        ids={}
        for x in r['inputs']:
            f=selected(root,x['path'])
            if sha(f)!=x['sha256']:raise ValueError('Selected scientific input changed')
            ids[x['id']]=f;receipt['inputs'].append({**x,'bytes':f.stat().st_size})
        import shutil
        shutil.copyfile(ids['context'],out/'source_context.private.json');shutil.copyfile(ids['structure_manifest'],out/'source_structures.private.json')
        if r['method']=='shepherd2_generate':shutil.copyfile(ids['checkpoint_manifest'],out/'source_checkpoint_manifest.private.json')
        offline()
        from worker import execute
        summaries=[];eligible=[]
        for label,seed in [('primary',r['parameters']['seed'])]+[(v['label'],v['seed']) for v in r['sensitivity_variants']]:
            folder=out/label;folder.mkdir();summary=execute(r,ids,root,folder,seed);entries=summary.pop('eligible_outputs')
            for x in entries:
                entry={**x,'variant':label,'path':label+'/'+x['path']}
                for key in ('constraint_report_path','identity_report_path','source_constraint_report_path'):
                    if key in x:entry[key]=label+'/'+x[key]
                eligible.append(entry)
            summaries.append({'variant':label,'seed':seed,**summary})
            if r['method']=='prepare_reference_profiles':
                manifest=read(ids['structure_manifest'])
                write(folder/'reference_axis_index.private.json',[read(folder/(row['id']+'.axes.private.json')) for row in manifest['molecules']])
        write(out/'variant_diagnostics.private.json',summaries)
        write(out/'eligible_candidate_outputs.private.json',eligible)
        if r['method'] in ('paper_native_evaluation','prepare_generated_identities'):
            write(out/'boundaries.private.json',{'method':r['method'],'postanalysis_of_exact_generation_origin':True,'paper_evaluation_scores_do_not_grant_docking_eligibility':True,'identity_grouping_preserves_original_chemical_state_and_pose':r['method']=='prepare_generated_identities','computed_parent_is_not_physiological_state_prediction':True,'technical_rechecks_are_not_independent_molecules':True,'scientific_acceptance':'NOT_ESTABLISHED','public_upload':False})
        else:
            write(out/'boundaries.private.json',{'score_semantics':'ligand_shape_ESP_pharmacophore_similarity_not_protein_ligand_binding_energy','potential_model':'GFN2_xTB_atomic_partial_charge_Coulomb_surface','not_DFT_density_ESP':True,'not_APBS_PB_energy':True,'generation_samples_are_biological_replicates':False,'experimental_binding_or_selectivity_established':False,'moved_or_generated_pose_requires_new_docking_and_pose_QC':r['method'] in ('align_profiles','shepherd2_generate'),'public_upload':False})
        proof=[]
        for v in summaries:
            folder=out/v['variant']
            for f in sorted(folder.glob('*.tsv')):
                with f.open(encoding='utf8',newline='') as stream:
                    reader=csv.DictReader(stream,delimiter='\t');columns=reader.fieldnames;rows=[];n=0;identities={};statuses={};pairs={};states={};full_rows=[];identity_rows=[];value_rows=[];value_issues=set()
                    for row in reader:
                        if None in row or any(x is None for x in row.values()):raise ValueError('Ragged scientific result')
                        n+=1;identity=row.get('candidate_id','');identities[identity]=identities.get(identity,0)+1
                        full_rows.append(row)
                        if f.stem=='profile_scores':
                            identity_rows.append({k:row[k] for k in ('candidate_id','reference_id','parent_id','microstate_id','coordinate_mode')})
                            for key in ('shape_similarity','esp_surface_similarity','pharmacophore_similarity'):
                                value=row[key]
                                if key=='pharmacophore_similarity' and value=='':
                                    if row['pharmacophore_assessed'].lower()!='false':value_issues.add('unassessed_pharmacophore_was_claimed_assessed')
                                    continue
                                try:
                                    num=float(value)
                                    if not math.isfinite(num) or not -1e-6<=num<=1.000001:raise ValueError('Outside similarity domain')
                                except ValueError:value_issues.add('invalid_dimensionless_similarity')
                                if key=='pharmacophore_similarity' and row['pharmacophore_assessed'].lower()!='true':value_issues.add('pharmacophore_value_and_assessment_disagree')
                            if row['protein_ligand_energy_estimated'].lower()!='false':value_issues.add('ligand_similarity_misrepresented_as_binding_energy')
                            try:
                                value_rows.append({'candidate_id':row['candidate_id'],'reference_id':row['reference_id'],'shape_similarity':float(row['shape_similarity']),'esp_surface_similarity':float(row['esp_surface_similarity']),'pharmacophore_similarity':None if row['pharmacophore_similarity']=='' else float(row['pharmacophore_similarity']),'pharmacophore_assessed':row['pharmacophore_assessed'].lower()=='true','protein_ligand_energy_estimated':row['protein_ligand_energy_estimated'].lower()=='true'})
                            except ValueError:value_issues.add('invalid_dimensionless_similarity')
                        if 'state' in row:statuses[row['state']]=statuses.get(row['state'],0)+1
                        if 'reference_id' in row:
                            by_reference=pairs.setdefault(identity,{});ref=row['reference_id'];by_reference[ref]=by_reference.get(ref,0)+1
                        if f.stem in ('candidate_denominator','constraint_results','identity_preparation','native_evaluation'):
                            if identity in states:raise ValueError('Duplicate candidate state in complete denominator')
                            states[identity]=row['state']
                        if len(rows)<40:rows.append(row)
                preview=folder/(f.stem+'.preview.private.json');write(preview,{'full_result_sha256':sha(f),'full_rows':n,'preview_rows':rows,'is_full_result':n<=40});proof.append({'variant':v['variant'],'role':f.stem,'path':f.relative_to(out).as_posix(),'sha256':sha(f),'bytes':f.stat().st_size,'rows':n,'columns':columns,'preview_path':preview.relative_to(out).as_posix(),'preview_sha256':sha(preview),'candidate_row_counts':identities,'status_counts':statuses,'candidate_reference_row_counts':pairs,'candidate_states':states,'identity_binding_sha256':digest(sorted(identity_rows,key=lambda x:(x['candidate_id'],x['reference_id']))),'profile_values_binding_sha256':digest(sorted(value_rows,key=lambda x:(x['candidate_id'],x['reference_id']))),'full_value_audit_issues':sorted(value_issues),'row_values_binding_sha256':digest(full_rows),'scope':'full_server_stream_scan_not_independent_scientific_validation'})
        write(out/'full_result_audit.private.json',proof)
        for x in r['inputs']:
            if sha(ids[x['id']])!=x['sha256']:raise ValueError('Scientific input changed during run')
        receipt.update(state='COMPLETED',exit_code=0)
    except Exception as e:receipt.update(state='FAILED',exit_code=1,error=str(e));(out/'failure.private.log').write_text(traceback.format_exc(),encoding='utf8')
    receipt['outputs']=[{'path':f.relative_to(out).as_posix(),'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(out.rglob('*')) if f.is_file() and f.stat().st_size]
    receipt['finished']=datetime.datetime.now(datetime.timezone.utc).isoformat();write(out/'receipt.private.json',receipt);return receipt
if __name__=='__main__':r=run(sys.argv[1],sys.argv[2]);print(r['state']);sys.exit(r['exit_code'])
