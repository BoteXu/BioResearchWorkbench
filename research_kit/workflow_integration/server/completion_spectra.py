"""Offline spectra and author-result routes. No public spectrum submission."""
import csv
import importlib.util
import math
from pathlib import Path
from runtime import read,write,sha
from completion_common import table,native_command,checked_executable

def read_mgf(path):
    spectra=[];current=None
    with Path(path).open(encoding='utf-8-sig') as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith('#'):continue
            if line=='BEGIN IONS':
                if current is not None:raise ValueError('Nested MGF spectrum')
                current={'peaks':[]};continue
            if line=='END IONS':
                if current is None:raise ValueError('Unmatched MGF spectrum end')
                if not current.get('TITLE') or not current.get('PEPMASS') or not current['peaks']:raise ValueError('Actual MGF title, precursor and peak channels required')
                current['precursor_mz']=float(current['PEPMASS'].split()[0]);current['peaks'].sort()
                if not math.isfinite(current['precursor_mz']) or current['precursor_mz']<=0:raise ValueError('Invalid measured precursor m/z')
                spectra.append(current);current=None;continue
            if current is None:raise ValueError('Unexpected MGF content outside a spectrum')
            if '=' in line:
                k,v=line.split('=',1)
                if k in current:raise ValueError('Duplicate MGF metadata field')
                current[k]=v
            else:
                a=line.split()
                if len(a)!=2:raise ValueError('MGF peaks require actual m/z and intensity')
                mz,intensity=map(float,a)
                if not math.isfinite(mz) or not math.isfinite(intensity) or mz<=0 or intensity<0:raise ValueError('Invalid measured MS/MS peak')
                current['peaks'].append((mz,intensity))
    if current is not None or not spectra:raise ValueError('Truncated or empty MGF')
    names=[s['TITLE'] for s in spectra]
    if len(set(names))!=len(names):raise ValueError('Duplicate literal MGF titles')
    return spectra

def spectrum_inputs(ids,out):
    spectra=read_mgf(ids['spectra']);header,identity=table(ids['spectrum_identity'],'spectrum_id')
    if not {'mgf_title','sample_id','unit_id','ionization'}<=set(header):raise ValueError('Actual spectrum/sample/unit/ionization mapping required')
    if {r['mgf_title'] for r in identity}!={s['TITLE'] for s in spectra} or len(identity)!=len(spectra):raise ValueError('Literal MGF titles and identity table differ')
    by={r['mgf_title']:r for r in identity}
    rows=[]
    for s in spectra:
        row=by[s['TITLE']];s['spectrum_id']=row['spectrum_id']
        if any(not row[k] for k in ['sample_id','unit_id','ionization']):raise ValueError('Incomplete source spectrum context')
        positive=sum(i>0 for mz,i in s['peaks'])
        if not positive:raise ValueError('All-zero MS/MS spectrum has no normalization denominator')
        rows.append({**row,'precursor_mz':s['precursor_mz'],'peaks':len(s['peaks']),'positive_peaks':positive,'mgf_charge':s.get('CHARGE','unreported')})
    import pandas as pd
    path=out/'spectrum_qc.tsv';pd.DataFrame(rows).to_csv(path,sep='\t',index=False)
    return spectra,rows,[(path,'spectrum_qc')]

def gnps(ids,p,out,repo):
    import pandas as pd
    spectra,identity,outputs=spectrum_inputs(ids,out)
    if len(spectra)>p['maximum_spectra'] or len(spectra)*(len(spectra)-1)//2>p['maximum_output_entries']:raise ValueError('All-pairs spectrum comparison exceeds explicit server budget')
    if any(s.get('CHARGE') not in {'1+','+1'} for s in spectra):raise ValueError('This reviewed legacy precursor-shift route is singly positively charged only; no unreviewed cross-charge comparison')
    file=repo/'metabolomics-snets/bin/scripts/spectrum_alignment.py'
    spec=importlib.util.spec_from_file_location('reviewed_gnps_alignment',file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    all_pairs=[];neighbors={s['spectrum_id']:[] for s in spectra}
    for i,s in enumerate(spectra):
        for j in range(i):
            t=spectra[j]
            # The original implementation uses abs(parent1-parent2) and shifts
            # only the first spectrum: put the higher precursor first.
            a,b=(s,t) if s['precursor_mz']>=t['precursor_mz'] else (t,s)
            score,matches=module.score_alignment(a['peaks'],b['peaks'],a['precursor_mz'],b['precursor_mz'],p['fragment_tolerance_da'])
            if not math.isfinite(score) or not -1e-8<=score<=1+1e-8:raise ValueError('Invalid actual native cosine score')
            row={'source':s['spectrum_id'],'target':t['spectrum_id'],'cosine':score,'matched_peaks':len(matches),'precursor_delta_da':abs(s['precursor_mz']-t['precursor_mz'])}
            all_pairs.append(row)
            if score>=p['cosine_cutoff'] and len(matches)>=p['minimum_matched_peaks']:
                neighbors[row['source']].append((score,row['target']));neighbors[row['target']].append((score,row['source']))
    top={name:{target for score,target in sorted(values,key=lambda v:(-v[0],v[1]))[:p['top_k']]} for name,values in neighbors.items()}
    for r in all_pairs:r['selected_mutual_top_k']=r['target'] in top[r['source']] and r['source'] in top[r['target']]
    edge=out/'spectral_pairs.tsv';pd.DataFrame(all_pairs,columns=['source','target','cosine','matched_peaks','precursor_delta_da','selected_mutual_top_k']).to_csv(edge,sep='\t',index=False);outputs.append((edge,'spectral_edges'))
    degrees={s['spectrum_id']:0 for s in spectra}
    for r in all_pairs:
        if r['selected_mutual_top_k']:degrees[r['source']]+=1;degrees[r['target']]+=1
    nodes=out/'spectral_nodes.tsv';pd.DataFrame([{**r,'degree':degrees[r['spectrum_id']],'structure_identification':'not_performed'} for r in identity]).to_csv(nodes,sep='\t',index=False);outputs.append((nodes,'spectral_nodes'))
    primary=out/'primary_results.tsv';pd.DataFrame([{'spectra':len(spectra),'pairs':len(all_pairs),'selected_edges':sum(r['selected_mutual_top_k'] for r in all_pairs),'algorithm':'author_legacy_modified_cosine_plus_explicit_mutual_top_k'}]).to_csv(primary,sep='\t',index=False);outputs.append((primary,'primary_results'))
    return outputs,{'spectra':len(spectra),'selected_edges':sum(r['selected_mutual_top_k'] for r in all_pairs),'isolated_spectra':sum(v==0 for v in degrees.values())}

def sirius(ids,p,out):
    import pandas as pd
    spectra,identity,outputs=spectrum_inputs(ids,out);exe=checked_executable(p)
    project=out/'native_project';summaries=out/'native_summaries'
    # Native write-summaries is standalone, never chain a fictitious subtool.
    log=native_command([exe,'--input',ids['spectra'],'--project',project,'formulas','-p',p['instrument'],'--ppm-max',p['ppm_ms1'],'--ppm-max-ms2',p['ppm_ms2'],'-c',p['formula_candidates']],out,'sirius_formulas')
    log2=native_command([exe,'--project',project,'write-summaries','--output',summaries,'--format','TSV'],out,'sirius_summaries')
    candidates=summaries/'formula_identifications.tsv'
    if not candidates.is_file():raise ValueError('Expected native formula summary absent; inspect actual version/output before any new dispatch')
    x=pd.read_csv(candidates,sep='\t')
    required={'molecularFormula','adduct','precursorIonType'}
    if 'molecularFormula' not in x or x.empty:raise ValueError('Native SIRIUS formula channel absent')
    # Join only an explicit native feature ID supplied in the original mapping.
    by=pd.DataFrame(identity)
    if 'native_feature_id' not in by or 'alignedFeatureId' not in x or by.native_feature_id.duplicated().any():raise ValueError('Native SIRIUS feature IDs require an exact supplied one-to-one mapping')
    x['alignedFeatureId']=x.alignedFeatureId.astype(str)
    if not set(x.alignedFeatureId)<=set(by.native_feature_id):raise ValueError('Unmapped native formula identities')
    x=x.merge(by,left_on='alignedFeatureId',right_on='native_feature_id',validate='many_to_one',how='left');path=out/'formula_candidates.tsv';x.to_csv(path,sep='\t',index=False);outputs.append((path,'formula_candidates'))
    primary=out/'primary_results.tsv';pd.DataFrame([{'spectra':len(spectra),'returned_features':x.spectrum_id.nunique(),'formula_rows':len(x),'interpretation':'computed_candidate_not_confirmed_identity'}]).to_csv(primary,sep='\t',index=False);outputs.extend([(primary,'primary_results'),(log,'native_engine_log'),(log2,'native_engine_log')])
    # Keep the complete native project/candidate tables as scientific artifacts.
    inventory=[]
    for q in project.rglob('*'):
        if q.is_file():
            inventory.append({'path':q.relative_to(out).as_posix(),'sha256':sha(q),'bytes':q.stat().st_size})
            if q.stat().st_size>0:outputs.append((q,'native_formula_project'))
    for q in summaries.rglob('*'):
        if q.is_file() and q.stat().st_size>0:outputs.append((q,'native_formula_summary'))
    write(out/'native_formula_inventory.private.json',{'files':inventory,'empty_auxiliary_files_not_counted_as_scientific_results':True});outputs.append((out/'native_formula_inventory.private.json','native_formula_inventory'))
    return outputs,{'input_spectra':len(spectra),'returned_feature_fraction':float(x.spectrum_id.nunique()/len(spectra)),'candidate_rows':len(x)}

def csi_import(ids,p,out):
    import pandas as pd
    spectra,identity,outputs=spectrum_inputs(ids,out);receipt=read(ids['native_result_receipt'])
    if receipt.get('tool')!='CSI:FingerID' or receipt.get('state')!='COMPLETED' or receipt.get('spectrum_sha256')!=sha(ids['spectra']) or receipt.get('structure_results_sha256')!=sha(ids['structure_results']) or not receipt.get('version') or not receipt.get('license_review'):
        raise ValueError('Actual CSI:FingerID results, source spectrum and native completion/license receipt required')
    x=pd.read_csv(ids['structure_results'],sep='\t',dtype=str,keep_default_na=False);mapping=p['result_columns']
    if set(mapping)!={'native_feature_id','rank','structure_id','score'} or len(set(mapping.values()))!=len(mapping) or not set(mapping.values())<=set(x):raise ValueError('Explicit actual native result columns required, no invented CSI prediction')
    x=x.rename(columns={v:k for k,v in mapping.items()});by=pd.DataFrame(identity)
    if 'native_feature_id' not in by or by.native_feature_id.duplicated().any() or not set(x.native_feature_id)<=set(by.native_feature_id):raise ValueError('CSI native feature identity differs from the selected source spectra')
    x['rank']=pd.to_numeric(x['rank'],errors='raise');x['score']=pd.to_numeric(x['score'],errors='raise')
    if x.empty or x[['native_feature_id','rank']].duplicated().any() or any(not math.isfinite(v) for v in x.score) or (x['rank']<1).any() or any(v%1 for v in x['rank']):raise ValueError('Invalid actual native candidate rank/score table')
    x=x.merge(by,on='native_feature_id',validate='many_to_one',how='left');x['score_meaning']='native_ranking_score_not_posterior_probability'
    path=out/'structure_candidates.tsv';x.to_csv(path,sep='\t',index=False);outputs.append((path,'structure_candidates'))
    primary=out/'primary_results.tsv';pd.DataFrame([{'source_spectra':len(spectra),'candidate_rows':len(x),'fresh_CSI_prediction':False,'private_spectra_uploaded':False}]).to_csv(primary,sep='\t',index=False);outputs.append((primary,'primary_results'))
    return outputs,{'input_spectra':len(spectra),'returned_feature_fraction':float(x.spectrum_id.nunique()/len(spectra)),'candidate_rows':len(x),'fresh_network_calls':0}
