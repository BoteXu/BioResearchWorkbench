"""Server-only scientific branch runner. No imports of numerical packages before guard."""
from pathlib import Path
import csv,json,copy,subprocess,sys,importlib.metadata
try:
    from .runtime import read,write,sha
except ImportError:
    from runtime import read,write,sha

REGISTRY=Path(__file__).with_name('branches71.json')
FORBIDDEN={'analysis_id','implementation','seed','sensitivity_variants','control','treatment','contrast','design','formula','null_formula','holdout_units','training_units','test_units'}

def parameter_types(parameters,spec):
    import math
    for name,rule in spec['parameter_schema'].items():
        if name not in parameters and rule.get('optional'):continue
        value=parameters[name];kind=rule['type']
        valid={'integer':lambda:type(value) is int,'number':lambda:type(value) in (int,float) and math.isfinite(value),
          'array':lambda:isinstance(value,list),'boolean':lambda:type(value) is bool,'object':lambda:isinstance(value,dict),
          'string':lambda:isinstance(value,str) and bool(value.strip()),
          'contrast':lambda:isinstance(value,dict) and bool(value) and all(type(v) in (int,float) and math.isfinite(v) for v in value.values()),
          'bins':lambda:(type(value) is int and value>=2) or (isinstance(value,list) and len(value)>=3 and all(type(v) in (int,float) for v in value) and all(a<b for a,b in zip(value,value[1:])))}[kind]()
        if not valid or ('minimum' in rule and value<rule['minimum']) or ('minimum_exclusive' in rule and value<=rule['minimum_exclusive']) or ('maximum' in rule and value>rule['maximum']) or ('enum' in rule and value not in rule['enum']):raise ValueError('Invalid explicit method parameter: '+name)

def contract(parameters,inputs):
    registry=read(REGISTRY);key=parameters['analysis_id'];spec=registry[key]
    if set(parameters)-set(spec['parameter_schema'])-{'analysis_id','implementation','seed','sensitivity_variants'}:raise ValueError('Unknown scientific parameters cannot be silently ignored')
    if parameters.get('implementation')!=spec['implementation']:raise ValueError('Select the actual implemented method explicitly; candidate packages are not aliases')
    if not set(spec['required_inputs'])<=set(inputs):raise ValueError('Missing selected scientific inputs: '+str(set(spec['required_inputs'])-set(inputs)))
    for parameter,choices in spec.get('conditional_inputs_by_parameter',{}).items():
        if not set(choices.get(parameters.get(parameter),[]))<=set(inputs):raise ValueError('The selected scientific method branch needs its actual conditional inputs')
    if any(k not in parameters for k in spec['required_parameters']):raise ValueError('Missing branch-specific method decisions')
    parameter_types(parameters,spec)
    try:from .method_contract71 import validate_parameters as validate_method_parameters
    except ImportError:from method_contract71 import validate_parameters as validate_method_parameters
    validate_method_parameters(parameters,spec)
    if type(parameters.get('seed')) is not int:raise ValueError('Explicit integer seed required')
    variants=parameters.get('sensitivity_variants')
    if not isinstance(variants,list) or len(variants)<2:raise ValueError('At least two actual nonbaseline sensitivity reruns required')
    labels=[];settings=[]
    for v in variants:
        if not isinstance(v,dict) or set(v)!={'label','parameters'}:raise ValueError('Variant requires label and explicit parameters')
        label=v['label'];delta=v['parameters']
        if not isinstance(label,str) or not label.replace('_','').isalnum() or label=='primary' or label in labels:raise ValueError('Unique safe variant label required')
        if not isinstance(delta,dict) or not delta or set(delta)&FORBIDDEN or not set(delta)<=set(spec['sensitivity_parameters']):raise ValueError('Sensitivity must use the method-specific whitelist, never identity, test units or estimand')
        if not any(parameters[k]!=val for k,val in delta.items()):raise ValueError('Sensitivity must actually differ from primary')
        parameter_types({**parameters,**delta},spec)
        validate_method_parameters({**parameters,**delta},spec)
        canonical=json.dumps(delta,sort_keys=True)
        if canonical in settings:raise ValueError('Duplicate sensitivity configuration')
        labels.append(label);settings.append(canonical)
    # The immutable historical registry is not a live server observation.
    spec=copy.deepcopy(spec)
    spec['scientific_runtime']='NOT_RUN_THIS_UPGRADE'
    spec['server_live_status']='NOT_PROBED_THIS_UPGRADE'
    return spec

def validate_context(context):
    import math
    for key in ('species','assembly','annotation_version','assay','scale','feature_unit','independent_unit','estimand','reference_versions','qc_evidence','limitations'):
        if not context.get(key):raise ValueError('Missing exact scientific context: '+key)
    if context.get('public_upload') is not False:raise ValueError('Private offline analysis only')
    for row in context['qc_evidence']:
        if set(('input_id','sha256','criterion','observed','decision','operator','bound','unit','source_receipt_sha256','source_receipt_input','measurement_input','measurement_field'))-set(row):raise ValueError('Substantive bound upstream QC required')
        if row['decision']!='ACCEPT' or type(row['observed']) not in (int,float):raise ValueError('Upstream QC is blocked or is only a status string')
        if type(row['bound']) not in (int,float) or not math.isfinite(row['bound']) or not math.isfinite(row['observed']):raise ValueError('Finite measured upstream QC and threshold required')
        op=row['operator'];a=row['observed'];b=row['bound']
        if op not in {'ge','le','eq'} or not {'ge':a>=b,'le':a<=b,'eq':a==b}[op]:raise ValueError('Upstream scientific QC did not meet its prespecified threshold')

def summarize(path):
    """Run on the server only. Full result denominator, no local matrix import."""
    import math
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f,delimiter='\t');cols=reader.fieldnames
        if not cols or len(cols)!=len(set(cols)):raise ValueError('Malformed method output')
        n=0;numeric={};keys=set()
        for r in reader:
            if None in r or any(v is None for v in r.values()):raise ValueError('Ragged method result')
            n+=1
            for k,v in r.items():
                if v in ('','NA','NaN'):continue
                try:x=float(v)
                except ValueError:continue
                if not math.isfinite(x):raise ValueError('Nonfinite method output in '+k)
                a=numeric.setdefault(k,[0,0.0,0.0]);a[0]+=1;a[1]+=x;a[2]+=x*x
        return {'rows':n,'columns':cols,'numeric':{k:{'n':a[0],'mean':a[1]/a[0],'sum_squares':a[2]} for k,a in numeric.items()}}

def analyze(ids,params,out,mode):
    import platform,os
    if sys.platform!='linux' or 'microsoft' in platform.release().lower() or not (os.environ.get('SLURM_JOB_ID') or os.environ.get('SSH_CONNECTION')):
        raise RuntimeError('No local scientific execution; use the existing allocated server')
    spec=contract(params,ids);context=read(ids['context']);validate_context(context)
    for q in context['qc_evidence']:
        if q['input_id'] not in ids or sha(ids[q['input_id']])!=q['sha256']:raise ValueError('Upstream scientific QC is bound to a different input')
        upstream=read(ids[q['source_receipt_input']]);measurement=ids[q['measurement_input']]
        if sha(ids[q['source_receipt_input']])!=q['source_receipt_sha256'] or upstream.get('state')!='COMPLETED' or upstream.get('exit_code')!=0:raise ValueError('Actual upstream QC run did not complete or changed')
        if not any(row.get('sha256')==sha(measurement) for row in upstream.get('outputs',[])):raise ValueError('QC observation file is not registered in the actual upstream completion receipt')
        if not any(row.get('sha256')==q['sha256'] for row in upstream.get('inputs',[])):raise ValueError('QC was computed on different scientific inputs')
        observed=read(measurement)
        for component in q['measurement_field'].split('.'):
            observed=observed[int(component)] if isinstance(observed,list) else observed[component]
        if type(observed) not in (int,float) or observed!=q['observed']:raise ValueError('Caller QC value differs from actual returned measurement')
    from qc71 import preflight
    executable_qc=preflight(ids,params,context,spec)
    import numpy as np
    np.random.seed(params['seed'])
    runs=[('primary',params)]+[(r['label'],{**params,**r['parameters']}) for r in params['sensitivity_variants']]
    all_outputs=[];comparisons=[];reports=[];full_audits=[]
    for label,p in runs:
        folder=out/label;folder.mkdir()
        variant_qc=preflight(ids,p,context,spec)
        invocation={'analysis_id':params['analysis_id'],'implementation':params['implementation'],
          'parameters':p,'inputs':{k:str(v) for k,v in ids.items()},'context':context,'required_roles':spec['required_roles']}
        write(folder/'invocation.private.json',invocation)
        if spec['worker'] in {'r','rna'}:
            command=['Rscript','--vanilla',str(Path(__file__).with_name('analysis71.R')),str(folder/'invocation.private.json'),str(folder)]
            with (folder/'engine.log').open('xb') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
            mapping=read(folder/'outputs.private.json')
        else:
            module=__import__({'native':'native71','cell':'cell71','cli':'cli71'}[spec['worker']])
            mapping=module.analyze(invocation,folder)
        if set(mapping)!=set(spec['required_roles']):raise ValueError('A required branch result was not actually generated')
        for role,name in mapping.items():
            path=folder/name
            if not path.is_file() or not path.stat().st_size:raise ValueError('Empty/missing scientific output')
            summary=summarize(path);comparisons.append({'variant':label,'role':role,**summary})
            from result_audit71 import audit as audit_full
            rule=spec['primary_result_rule'] if role==spec['required_roles'][0] else {'required':[],'keys':[],'allow_empty':True}
            preview=folder/(role+'.preview.tsv');proof=audit_full(path,rule,preview);proof.update(variant=label,role=role,path=path.relative_to(out).as_posix(),preview_path=preview.relative_to(out).as_posix());full_audits.append(proof)
            all_outputs.append((preview,'preview_'+label+'_'+role))
            all_outputs.append((path,role if label=='primary' else 'sensitivity_'+role))
        report=read(folder/'diagnostics.private.json')
        if report.get('fit_completed') is not True or not isinstance(report.get('metrics'),dict) or not report['metrics']:raise ValueError('Actual numerical diagnostics required')
        if any(type(x) not in (int,float) for x in report['metrics'].values()):raise ValueError('A diagnostic status string is not a measured diagnostic')
        if any(not __import__('math').isfinite(x) for x in report['metrics'].values()):raise ValueError('Nonfinite measured diagnostics cannot pass')
        reports.append({'variant':label,'parameters':p,'preflight':variant_qc,**report})
        all_outputs.extend([(folder/'engine.log','engine_log')] if (folder/'engine.log').is_file() and (folder/'engine.log').stat().st_size else [])
        all_outputs.append((folder/'diagnostics.private.json','variant_diagnostics'))
        already={Path(f).resolve() for f,r in all_outputs}
        for artifact in folder.rglob('*'):
            if artifact.is_file() and artifact.stat().st_size and artifact.resolve() not in already:
                all_outputs.append((artifact,'supporting_artifact'))
    # Actual independent rerun results are retained, never replaced with copied baseline or flags.
    write(out/'analysis_sensitivity.json',comparisons)
    from result_audit71 import compare as compare_actual
    actual_comparison,metric_file=compare_actual(out,spec,params['sensitivity_variants'])
    write(out/'full_result_audit.json',full_audits);write(out/'actual_sensitivity_comparison.json',actual_comparison)
    write(out/'analysis_diagnostics.json',reports)
    write(out/'analysis_qc.json',{'context':context,'input_roles':list(ids),'upstream_evidence':context['qc_evidence'],
      'variant_count':len(runs),'executed_preflight':executable_qc,'method_runtime_completed':True,'scientific_acceptance':'requires_independent_review'})
    distributions={}
    for package in ('numpy','scipy','pandas','statsmodels','networkx','scanpy','scvelo','cellrank','liana','cooltools','pyscenic','scirpy'):
        try:distributions[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:pass
    write(out/'implementation_record.json',{'analysis_id':params['analysis_id'],'implementation':params['implementation'],
      'original_candidates':spec['original_candidates'],'candidate_execution_not_implied':True,
      'versions':distributions,'source_sha256':{p.name:sha(p) for p in Path(__file__).parent.glob('*') if p.is_file() and p.suffix in {'.py','.R','.json'}},
      'interpretation_limit':spec['interpretation_limit'],'public_upload':False})
    # Exact input metadata supports downstream condition annotations without
    # guessing sample suffixes or treating technical replicates as new subjects.
    import shutil
    for role in ('samples','cell_metadata','coordinates'):
        if role in ids:
            snapshot=out/('source_'+role+'.tsv');shutil.copyfile(ids[role],snapshot)
            if sha(snapshot)!=sha(ids[role]):raise ValueError('Frozen metadata copy changed')
            all_outputs.append((snapshot,'source_metadata_snapshot'))
    write(out/'scientific_context.private.json',context);all_outputs.append((out/'scientific_context.private.json','scientific_context'))
    return all_outputs+[(out/'full_result_audit.json','full_result_audit'),(out/'actual_sensitivity_comparison.json','actual_sensitivity_comparison'),(metric_file,'full_sensitivity_column_metrics'),(out/'analysis_sensitivity.json','analysis_sensitivity'),(out/'analysis_diagnostics.json','analysis_diagnostics'),
      (out/'analysis_qc.json','analysis_qc'),(out/'implementation_record.json','implementation_record')]
