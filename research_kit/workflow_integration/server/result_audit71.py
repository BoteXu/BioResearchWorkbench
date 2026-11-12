"""Full server-file semantic audit and actual rerun comparisons; no fitting and no local matrix import."""
from pathlib import Path
import csv,json,math,sqlite3,re
from runtime import sha,write
from method_contract71 import validate_rows

def audit(path,rule,preview):
    n=0;seen=set();numeric={};missing={};saved=[]
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f,delimiter='\t');cols=reader.fieldnames
        if not cols or len(cols)!=len(set(cols)) or not set(rule.get('required',[]))<=set(cols):raise ValueError('Full result schema is incompatible with its declared scientific role')
        for r in reader:
            if None in r or any(v is None for v in r.values()):raise ValueError('Ragged scientific result')
            n+=1;k=tuple(r[c] for c in rule.get('keys',[]))
            if k and (k in seen or any(v in ('','NA','NaN','None') for v in k)):raise ValueError('Missing/duplicate scientific result identity')
            if k:seen.add(k)
            issues=validate_rows(cols,[r],{**rule,'keys':[]})
            if issues:raise ValueError('Full result semantic checks failed: '+str(issues))
            for c,v in r.items():
                if v in ('','NA','NaN','None','nan'):missing[c]=missing.get(c,0)+1;continue
                try:x=float(v)
                except ValueError:continue
                if not math.isfinite(x):raise ValueError('Infinite/nonfinite value in actual result')
                numeric[c]=numeric.get(c,0)+1
            if len(saved)<40:saved.append(r)
    if not n and not rule.get('allow_empty',False):raise ValueError('Empty mandatory test/result denominator')
    with Path(preview).open('x',encoding='utf8',newline='') as f:w=csv.DictWriter(f,fieldnames=cols,delimiter='\t');w.writeheader();w.writerows(saved)
    return {'path':Path(path).name,'rows':n,'columns':cols,'sha256':sha(path),'bytes':Path(path).stat().st_size,'keys':rule.get('keys',[]),'numeric_denominators':numeric,'missing_values':missing,'preview_rows':len(saved),'preview_sha256':sha(preview),'scope':'FULL_SERVER_FILE_SCAN_NOT_INDEPENDENT_SCIENTIFIC_VALIDATION'}

def compare(out,spec,variants):
    role=spec['required_roles'][0];keys=spec['primary_result_rule']['keys'];db=Path(out)/'comparison_scratch.sqlite';connection=sqlite3.connect(db)
    connection.execute('create table base (identity text primary key, data text)')
    def rows(path):
        with Path(path).open(encoding='utf-8-sig',newline='') as f:yield from csv.DictReader(f,delimiter='\t')
    def identity(r):return json.dumps([r[c] for c in keys],ensure_ascii=False) if keys else '__single_model_result__'
    n=0
    for r in rows(Path(out)/'primary'/(role+'.tsv')):
        connection.execute('insert into base values (?,?)',(identity(r),json.dumps(r)));n+=1
    connection.commit();summaries=[];metrics_path=Path(out)/'sensitivity_column_metrics.tsv'
    with metrics_path.open('x',encoding='utf8',newline='') as f:
        writer=csv.writer(f,delimiter='\t');writer.writerow(['variant','column','matched_numeric_cells','mean_abs_change','max_abs_change'])
        for v in variants:
            matched=0;extra=0;changed=0;metrics={};seen=set()
            for r in rows(Path(out)/v['label']/(role+'.tsv')):
                ident=identity(r)
                if ident in seen:raise ValueError('Duplicate sensitivity result identity')
                seen.add(ident);old=connection.execute('select data from base where identity=?',(ident,)).fetchone()
                if old is None:extra+=1;continue
                matched+=1;old=json.loads(old[0]);changed+=old!=r
                for col in set(old)&set(r)-set(keys):
                    if re.search('(^|_)(id|index)$',col):continue
                    try:a=float(old[col]);b=float(r[col])
                    except (ValueError,TypeError):continue
                    if not math.isfinite(a) or not math.isfinite(b):continue
                    x=metrics.setdefault(col,[0,0.,0.]);d=abs(a-b);x[0]+=1;x[1]+=d;x[2]=max(x[2],d)
            for col,x in metrics.items():writer.writerow([v['label'],col,x[0],x[1]/x[0],x[2]])
            precision={'bootstraps','permutations','n_perms','simulations','stars_reps','null_permutations','donor_resamples','reference_bootstraps'}
            scope='MONTE_CARLO_PRECISION_ONLY' if set(v['parameters'])<=precision else 'EXPLICIT_PARAMETER_OR_REFERENCE_SENSITIVITY'
            summaries.append({'variant':v['label'],'primary_rows':n,'matched_rows':matched,'missing_primary_rows':n-matched,'alternate_new_rows':extra,'changed_matched_rows':int(changed),'compared_numeric_columns':len(metrics),'column_metrics_path':metrics_path.name,'scope':scope,'scientific_robustness_established':False})
    connection.close();db.unlink()
    return summaries,metrics_path
