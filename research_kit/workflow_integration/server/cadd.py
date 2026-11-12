"""Actual server-side molecule, pose, trajectory, free-energy and kinetic diagnostics."""
from runtime import write,read,sha

def analyze(inputs,p,out,mode):
    import numpy as np
    import pandas as pd
    if mode in {'molecular_qc','pose_qc'}:
        from rdkit import Chem
        from rdkit.Chem import Descriptors,rdMolAlign
        supplier=Chem.SDMolSupplier(str(inputs['ligands']),removeHs=False,sanitize=False)
        rows=[];molecules=[]
        for index,mol in enumerate(supplier):
            row={'source_record':index,'parent_id':None,'status':'failed'}
            if mol is None:row['error']='unreadable_record';rows.append(row);continue
            try:
                Chem.SanitizeMol(mol)
                ident=mol.GetProp(p['id_property']) if mol.HasProp(p['id_property']) else None
                if not ident:raise ValueError('Missing declared ligand state identity')
                coords=mol.GetConformer().GetPositions()
                if not np.isfinite(coords).all() or not mol.GetConformer().Is3D():raise ValueError('Missing finite 3D coordinates')
                unknown=Chem.FindMolChiralCenters(mol,includeUnassigned=True)
                if p['require_assigned_stereochemistry'] and any(v=='?' for _,v in unknown):raise ValueError('Unassigned stereochemistry')
                row.update(state_id=ident,parent_id=mol.GetProp(p['parent_property']) if mol.HasProp(p['parent_property']) else None,
                           formal_charge=Chem.GetFormalCharge(mol),fragments=len(Chem.GetMolFrags(mol)),
                           molecular_weight=Descriptors.MolWt(mol),canonical_isomeric_smiles=Chem.MolToSmiles(mol,isomericSmiles=True),status='parsed')
                if row['fragments']!=1:raise ValueError('Disconnected state; salts/fragment policies must be resolved before docking')
                molecules.append((index,mol))
            except Exception as exc:row.update(status='failed',error=str(exc))
            rows.append(row)
        if not rows:raise ValueError('Empty ligand file')
        ids=[r.get('state_id') for r in rows if r.get('state_id')]
        if len(ids)!=len(set(ids)):raise ValueError('Duplicate chemical state IDs')
        pd.DataFrame(rows).to_csv(out/'chemical_qc.tsv',sep='\t',index=False)
        outputs=[(out/'chemical_qc.tsv','chemical_qc')]
        if mode=='pose_qc':
            from posebusters import PoseBusters
            table=pd.DataFrame({'mol_pred':[str(inputs['ligands'])],'mol_cond':[str(inputs['receptor'])]})
            if 'reference_ligand' in inputs:table['mol_true']=str(inputs['reference_ligand'])
            bust=PoseBusters(config=p['posebusters_config']).bust(table,full_report=True)
            bust.to_csv(out/'posebusters.tsv',sep='\t')
            outputs.append((out/'posebusters.tsv','pose_physical_checks'))
            if 'reference_ligand' in inputs:
                references=[m for m in Chem.SDMolSupplier(str(inputs['reference_ligand']),removeHs=False) if m is not None]
                if len(references)!=1:raise ValueError('Select one exact reference ligand')
                values=[]
                for i,mol in molecules:
                    # CalcRMS preserves the protein coordinate frame; no independent ligand superposition.
                    value=rdMolAlign.CalcRMS(Chem.RemoveHs(mol),Chem.RemoveHs(references[0]),maxMatches=p['maximum_symmetry_matches'])
                    values.append({'source_record':i,'symmetry_aware_rmsd_angstrom':float(value),'superposition':'none; common receptor frame required'})
                pd.DataFrame(values).to_csv(out/'pose_rmsd.tsv',sep='\t',index=False);outputs.append((out/'pose_rmsd.tsv','pose_rmsd'))
        write(out/'diagnostics.json',{'input_records':len(rows),'failed_records':sum(r['status']=='failed' for r in rows),
          'failed_denominator_retained':True,'chemical_repair_performed':False,'pose_score_is_affinity':False,
          'reference_frame_review_required':mode=='pose_qc','binding_activity_established':False})
        return outputs+[(out/'diagnostics.json','diagnostics')]
    if mode=='md_analysis':
        import MDAnalysis as mda
        from MDAnalysis.analysis import align,rms
        from MDAnalysis.lib.distances import distance_array
        if p['pbc_policy']!='preprocessed_whole_complex':raise ValueError('Supply separately reviewed whole/recentered complex trajectory; no silent PBC repair')
        prep=read(inputs['preprocessing_receipt'])
        if prep.get('trajectory_sha256')!=sha(inputs['trajectory']) or prep.get('topology_sha256')!=sha(inputs['topology']):raise ValueError('PBC preparation receipt is bound to other files')
        if prep.get('whole_molecules') is not True or prep.get('complex_recentered') is not True:raise ValueError('Explicit whole and recentered-complex evidence required')
        u=mda.Universe(str(inputs['topology']),str(inputs['trajectory']));native_reference=mda.Universe(str(inputs['reference']))
        if u.atoms.n_atoms!=native_reference.atoms.n_atoms or list(u.atoms.names)!=list(native_reference.atoms.names) or list(u.atoms.resnames)!=list(native_reference.atoms.resnames):
            raise ValueError('Independent reference structure does not preserve actual topology atom/residue order; supply a reviewed mapped reference')
        ref=mda.Universe(str(inputs['topology']),str(inputs['reference']))
        if u.atoms.n_atoms!=ref.atoms.n_atoms or list(u.atoms.names)!=list(ref.atoms.names):raise ValueError('Reference atom mapping differs')
        fit=u.select_atoms(p['fit_selection']);analysis=u.select_atoms(p['analysis_selection']);ref_analysis=ref.select_atoms(p['analysis_selection'])
        ligand=u.select_atoms(p['ligand_selection']);target=u.select_atoms(p['contact_target_selection'])
        if min(len(fit),len(analysis),len(ligand),len(target))==0:raise ValueError('Empty explicit atom selection')
        if not np.isfinite(analysis.masses).all() or analysis.masses.sum()<=0:raise ValueError('Missing physical masses for Rg/alignment')
        records=[];mean=np.zeros((len(analysis),3));m2=np.zeros_like(mean);n=0;occupancy=np.zeros(len(target))
        previous_time=None
        for ts in u.trajectory[::p['stride']]:
            if ts.time<p['discard_ps']:continue
            if previous_time is not None and ts.time<=previous_time:raise ValueError('Trajectory time discontinuity/restart overlap')
            previous_time=ts.time
            align.alignto(u,ref,select=p['fit_selection'],weights='mass',match_atoms=False)
            xyz=analysis.positions.copy();n+=1;delta=xyz-mean;mean+=delta/n;m2+=delta*(xyz-mean)
            d=distance_array(target.positions,ligand.positions,box=ts.dimensions).min(axis=1)
            occupancy+=(d<=p['contact_cutoff_angstrom'])
            records.append({'frame':ts.frame,'time_ps':float(ts.time),'rmsd_angstrom':float(rms.rmsd(xyz,ref_analysis.positions,center=False,superposition=False)),
                            'radius_gyration_angstrom':float(analysis.radius_of_gyration()),'target_ligand_min_angstrom':float(d.min()),'contacts':int((d<=p['contact_cutoff_angstrom']).sum())})
        if n<3:raise ValueError('Insufficient post-equilibration trajectory frames')
        pd.DataFrame(records).to_csv(out/'trajectory_observables.tsv',sep='\t',index=False)
        pd.DataFrame({'atom_index':analysis.indices,'atom_name':analysis.names,'rmsf_angstrom':np.sqrt(m2.sum(axis=1)/n)}).to_csv(out/'rmsf.tsv',sep='\t',index=False)
        pd.DataFrame({'atom_index':target.indices,'residue':target.resids,'contact_occupancy':occupancy/n}).to_csv(out/'contacts.tsv',sep='\t',index=False)
        diagnostic={'frames':n,'independent_start_id':p['independent_start_id'],'frame_is_independent_replicate':False,'discard_ps':p['discard_ps'],
                    'length_unit':'angstrom','time_unit':'ps','fit_selection':p['fit_selection'],'convergence':'not_established_by_rmsd_plateau'}
        try:
            from pymbar import timeseries
            x=np.array([r['rmsd_angstrom'] for r in records]);g=float(timeseries.statistical_inefficiency(x))
            diagnostic.update(statistical_inefficiency=g,effective_samples=n/g)
        except (ImportError,ValueError,ZeroDivisionError) as exc:diagnostic.update(effective_samples=None,ess_state=type(exc).__name__)
        write(out/'diagnostics.json',diagnostic)
        return [(out/'trajectory_observables.tsv','trajectory_observables'),(out/'rmsf.tsv','rmsf'),(out/'contacts.tsv','contacts'),(out/'diagnostics.json','diagnostics')]
    if mode=='free_energy':
        # Recompute a signed correction ledger from actual selected numerical estimates; no FEP engine substitute.
        ledger=pd.read_csv(inputs['ledger'],sep='\t')
        required=['estimate_id','microstate','term','value','unit','sign','variance','covariance_group']
        if not set(required)<=set(ledger) or ledger['estimate_id'].duplicated().any():raise ValueError('Thermodynamic ledger identity invalid')
        if ledger.microstate.nunique()!=1:raise ValueError('Separate chemical microstates; a correction ledger cannot silently combine their free energies')
        if not np.isfinite(ledger[['value','variance']].to_numpy()).all() or (ledger.variance<0).any() or not set(ledger.sign)<={-1,1}:raise ValueError('Invalid signed estimate/variance')
        factors=ledger.unit.map({'kcal/mol':4.184,'kJ/mol':1.0})
        if factors.isna().any():raise ValueError('Mixed/unknown free-energy units')
        ledger['signed_kJ_mol']=ledger.value*factors*ledger.sign;ledger['variance_kJ2_mol2']=ledger.variance*factors**2
        covariance=pd.read_csv(inputs['covariance'],sep='\t')
        ids=ledger.estimate_id.tolist();C=np.diag(ledger.variance_kJ2_mol2.to_numpy());lookup={k:i for i,k in enumerate(ids)};seen=set()
        for row in covariance.to_dict('records'):
            i,j=lookup[row['estimate_a']],lookup[row['estimate_b']]
            if i==j or tuple(sorted((i,j))) in seen:raise ValueError('Duplicate/diagonal covariance')
            seen.add(tuple(sorted((i,j))));v=float(row['covariance_kJ2_mol2'])
            if not np.isfinite(v):raise ValueError('Nonfinite covariance')
            C[i,j]=C[j,i]=v
        for i in range(len(ledger)):
            for j in range(i+1,len(ledger)):
                if ledger.iloc[i]['covariance_group']==ledger.iloc[j]['covariance_group'] and (i,j) not in seen:
                    raise ValueError('Within-group covariance must be supplied explicitly, not silently assumed zero')
        if np.linalg.eigvalsh(C).min() < -p['covariance_tolerance']:raise ValueError('Covariance matrix is not positive semidefinite')
        if p['missing_covariance_policy']!='explicit_independence_reviewed':raise ValueError('Unprovided covariance is not automatically zero')
        signs=ledger.sign.to_numpy();variance=float(signs@C@signs)
        ledger.to_csv(out/'converted_ledger.tsv',sep='\t',index=False)
        write(out/'free_energy_summary.json',{'signed_total_kJ_mol':float(ledger.signed_kJ_mol.sum()),'standard_error_kJ_mol':float(np.sqrt(max(variance,0))),
          'estimand':p['estimand'],'standard_state':p['standard_state'],'microstates_combined':False,
          'limitation':'Ledger aggregation only; incompatible microstates must be separated and physically justified before combination'})
        return [(out/'converted_ledger.tsv','thermodynamic_ledger'),(out/'free_energy_summary.json','free_energy_uncertainty')]
    if mode=='kinetics':
        from scipy.stats import chi2
        events=pd.read_csv(inputs['events'],sep='\t')
        if events['independent_start_id'].duplicated().any() or not set(events['event'])<={0,1}:raise ValueError('One first-passage record per independent start with explicit censoring')
        if not np.isfinite(events['at_risk_time_ns']).all() or (events.at_risk_time_ns<=0).any():raise ValueError('Invalid risk time')
        if p['model']!='constant_hazard_first_passage' or p['unbiased_physical_time'] is not True:raise ValueError('Explicit exponential model and unbiased kinetics qualification required')
        k=int(events.event.sum());T=float(events.at_risk_time_ns.sum());alpha=1-p['confidence']
        lower=0. if k==0 else float(chi2.ppf(alpha/2,2*k)/(2*T));upper=float(chi2.ppf(1-alpha/2,2*(k+1))/(2*T))
        write(out/'kinetics.json',{'events':k,'independent_starts':len(events),'risk_time_ns':T,'rate_per_ns':k/T,
          'poisson_exposure_interval':[lower,upper],'censored':int((events.event==0).sum()),'exact_residence_time_reported':False,
          'qualification':'Constant hazard/independent starts; not valid for biased exchange time or arbitrary heterogeneous event processes'})
        return [(out/'kinetics.json','kinetics_uncertainty')]
    raise ValueError('Unknown CADD scientific analysis')
