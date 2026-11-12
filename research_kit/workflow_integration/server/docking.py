"""Fixed Vina campaign execution on the verified compute host; preserve all states/failures."""
from pathlib import Path
import subprocess
import re
from runtime import read,write,sha

def analyze(inputs,p,out,mode):
    import pandas as pd
    exe=Path(p['vina_executable'])
    if not exe.is_absolute() or not exe.is_file() or exe.name not in {'vina','vina_1.2.5','vina_1.2.7'}:raise ValueError('Select an existing reviewed Vina executable')
    probe=subprocess.run([str(exe),'--version'],capture_output=True,text=True,check=True)
    if p['expected_version'] not in probe.stdout+probe.stderr:raise ValueError('Vina runtime version differs from reviewed version')
    qc=pd.read_csv(inputs['chemical_qc'],sep='\t');campaign=read(inputs['campaign'])
    receptor_qc=read(inputs['receptor_qc']);preparation=read(inputs['preparation_manifest'])
    if receptor_qc.get('numerical_identity_qc_pass') is not True:raise ValueError('Receptor structural QC not passed')
    if preparation.get('source_structure_sha256')!=receptor_qc.get('structure_sha256') or preparation.get('prepared_receptor_sha256')!=sha(inputs['receptor']):
        raise ValueError('Prepared receptor is not bound to this actual structural QC')
    if preparation.get('reviewed_by_host') is not True:raise ValueError('Charge/protonation/atom mapping preparation review required')
    prepared={row['state_id']:row for row in preparation['ligands']}
    if qc.state_id.dropna().duplicated().any():raise ValueError('Ambiguous state QC')
    qc=qc.set_index('state_id');rows=[]
    if len({r['state_id'] for r in campaign})!=len(campaign):raise ValueError('Duplicate campaign state')
    if not {'reference','negative_control'}<={r['role'] for r in campaign}:raise ValueError('Explicit positive/reference and negative controls required')
    if not all(type(x) in (int,float) for x in p['center_angstrom']+p['size_angstrom']) or len(p['center_angstrom'])!=3 or len(p['size_angstrom'])!=3 or any(x<=0 for x in p['size_angstrom']):raise ValueError('Invalid angstrom docking box')
    pose_dir=out/'poses';pose_dir.mkdir()
    for state in campaign:
        sid=state['state_id']
        if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',sid):raise ValueError('Unsafe state identity')
        if state['ligand_input_id'] not in inputs:raise ValueError('Missing bound prepared ligand input')
        record=prepared.get(sid,{})
        if record.get('prepared_ligand_sha256')!=sha(inputs[state['ligand_input_id']]):raise ValueError('Prepared chemical state source mismatch')
        eligible=sid in qc.index and qc.loc[sid,'status']=='parsed'
        if eligible and record.get('canonical_isomeric_smiles')!=qc.loc[sid,'canonical_isomeric_smiles']:raise ValueError('Chemical preparation changed stereochemical identity')
        for seed in p['seeds']:
            row={'state_id':sid,'parent_id':state['parent_id'],'role':state['role'],'seed':seed,'state':'QC_FAILED','score':None,
                 'prepared_ligand_sha256':sha(inputs[state['ligand_input_id']]),'receptor_sha256':sha(inputs['receptor']),
                 'engine_version':p['expected_version'],'score_unit':'kcal/mol','score_interpretation':'Vina ranking score, not measured affinity'}
            if not eligible:rows.append(row);continue
            pose=pose_dir/(sid+'_'+str(seed)+'.pdbqt');log=out/(sid+'_'+str(seed)+'.log')
            argv=[str(exe),'--receptor',str(inputs['receptor']),'--ligand',str(inputs[state['ligand_input_id']]),'--cpu',str(p['cpu']),
              '--exhaustiveness',str(p['exhaustiveness']),'--num_modes',str(p['num_modes']),'--seed',str(seed),'--out',str(pose)]
            for axis,value in zip(('x','y','z'),p['center_angstrom']):argv+=['--center_'+axis,str(value)]
            for axis,value in zip(('x','y','z'),p['size_angstrom']):argv+=['--size_'+axis,str(value)]
            with log.open('xb') as f:proc=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,check=False)
            row.update(exit_code=proc.returncode,log_file=log.name,state='FAILED')
            if proc.returncode==0 and pose.is_file():
                scores=[float(m.group(1)) for m in re.finditer(r'REMARK VINA RESULT:\s+([-+0-9.eE]+)',pose.read_text(encoding='utf8'))]
                if scores:row.update(state='SCORED_REQUIRES_POSE_QC',score=scores[0],pose_file=pose.relative_to(out).as_posix(),pose_sha256=sha(pose))
            rows.append(row)
    pd.DataFrame(rows).to_csv(out/'docking_campaign.tsv',sep='\t',index=False)
    write(out/'diagnostics.json',{'planned_states':len(campaign),'planned_seeds':len(p['seeds']),'returned_state_seed_records':len(rows),
      'scored_records':sum(r['state']=='SCORED_REQUIRES_POSE_QC' for r in rows),'failed_or_qc_blocked_records':sum(r['state']!='SCORED_REQUIRES_POSE_QC' for r in rows),
      'physical_pose_qc_required':True,'score_domains_mixed':False,'box_center_angstrom':p['center_angstrom'],'box_size_angstrom':p['size_angstrom'],
      'qc_source_sha256':sha(inputs['chemical_qc']),'partial_failures_retained':True,'binding_activity_established':False})
    outputs=[(out/'docking_campaign.tsv','docking_campaign'),(out/'diagnostics.json','diagnostics')]
    outputs += [(q,'docked_pose') for q in pose_dir.glob('*.pdbqt')]
    outputs += [(q,'backend_log') for q in out.glob('*.log') if q.stat().st_size]
    return outputs
