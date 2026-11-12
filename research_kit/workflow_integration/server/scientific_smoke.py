"""Explicit server-only synthetic runtime acceptance; never runs on import or on the local PC."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import socket
import sys
from runtime import write,sha,run

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--host',required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--rscript',type=Path);args=parser.parse_args()
    if sys.platform!='linux' or 'microsoft' in platform.release().lower() or socket.gethostname()!=args.host:
        raise RuntimeError('Synthetic scientific acceptance stays on the explicitly verified existing compute server')
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    import numpy as np
    import pandas as pd
    rng=np.random.default_rng(20261025);n=120
    labels=np.array([i%2 for i in range(n)]);features=rng.normal(size=(n,8));features[:,:2]+=labels[:,None]*1.4
    data=pd.DataFrame(features,columns=['F'+str(i) for i in range(8)]);data['sample_id']=['S'+str(i) for i in range(n)];data['unit_id']=['U'+str(i) for i in range(n)];data['outcome']=labels
    data.to_csv(out/'ml.tsv',sep='\t',index=False)
    def request(name,backend,inputs,parameters,roles):
        source={q.name:sha(q) for q in Path(__file__).parent.glob('*') if q.is_file() and q.suffix in {'.py','.R'}}
        value={'schema':'private-scientific-request/2','run_id':name,'backend':backend,'expected_host':args.host,'node_role':'compute',
          'server_execution_authorized':False,'public_upload':False,'submission_state':'not_submitted','resource_budget':{'cpus':1,'gpus':0},
          'inputs':[{'id':key,'path':path.name,'sha256':sha(path)} for key,path in inputs.items()],
          'parameters':parameters,'required_roles':roles,'source_sha256':source,'synthetic_runtime_fixture':True}
        value['plan_sha256']=hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode('utf8')).hexdigest()
        value['server_execution_authorized']=True
        path=out/(name+'.request.json');write(path,value);return run(path,out/(name+'.result'))
    params={'features':['F'+str(i) for i in range(8)],'sample_key':'sample_id','unit_key':'unit_id','outcome':'outcome','task':'classification',
      'train_units':['U'+str(i) for i in range(80)],'calibration_units':['U'+str(i) for i in range(80,100)],'test_units':['U'+str(i) for i in range(100,120)],
      'models':{'baseline':{},'ridge':{'model__C':[.1,1.0]},'random_forest':{'model__max_depth':[3,6]}},
      'outer_folds':4,'inner_folds':3,'select_k':'all','seed':7,'threads':1,'max_candidates':4,
      'probability_calibration':'sigmoid','bootstrap_repeats':100,'calibration_bins':4}
    receipt=request('ml','ml',{'table':out/'ml.tsv'},params,['predictions','model_metrics','split_provenance'])
    if receipt['state']!='COMPLETED':raise RuntimeError('ML synthetic engine acceptance failed')
    # A real numeric design-QC negative: condition and batch are exactly confounded.
    counts=rng.poisson(100,size=(200,12));counts[:10,6:]=rng.poisson(220,size=(10,6))
    matrix=pd.DataFrame(counts,index=['G'+str(i) for i in range(200)],columns=['S'+str(i) for i in range(12)])
    matrix.to_csv(out/'counts.tsv',sep='\t')
    meta=pd.DataFrame({'sample_id':matrix.columns,'unit_id':['D'+str(i) for i in range(12)],'condition':['A']*6+['B']*6,'batch':['A']*6+['B']*6})
    meta.to_csv(out/'metadata.tsv',sep='\t',index=False)
    qc_params={'sample_key':'sample_id','unit_key':'unit_id','condition_key':'condition','scale':'raw_counts','case':'B','control':'A','paired':False,
      'covariates':['batch'],'covariate_types':{'batch':'categorical'},'minimum_units':3,
      'thresholds':{'minimum_observed_features':100,'maximum_missing_fraction':0.,'minimum_library_size':1000},
      'threshold_basis':'Synthetic fixture only, never a universal threshold','qc_variable_features':100,'qc_pcs':3}
    request('confounded_qc','matrix_qc',{'matrix':out/'counts.tsv','metadata':out/'metadata.tsv'},qc_params,['matrix_qc','sample_qc','design_matrix'])
    negative=json.loads((out/'confounded_qc.result/matrix_qc.json').read_text())
    if negative['numerical_qc_pass'] or 'rank_deficient_or_no_residual_df' not in negative['issues']:raise RuntimeError('True rank confounding was not blocked')
    qc_params['covariates']=[];qc_params['covariate_types']={}
    request('count_qc','matrix_qc',{'matrix':out/'counts.tsv','metadata':out/'metadata.tsv'},qc_params,['matrix_qc','sample_qc','design_matrix'])
    if args.rscript:
        qc=out/'count_qc.result/matrix_qc.json';qcr=out/'count_qc.result/server_receipt.private.json'
        # Copy selected bound QC artifacts beside the request; preserve original hashes.
        import shutil
        shutil.copy2(qc,out/'matrix_qc.json');shutil.copy2(qcr,out/'matrix_qc_receipt.json')
        write(out/'host_review.json',{'qc_sha256':sha(qc),'reviewed_by_host':True,'outlier_batch_decisions':'Synthetic generator and known unconfounded design; not real-study approval'})
        rp={'rscript':str(args.rscript),'method':'DESeq2','seed':7,'sample_key':'sample_id','unit_key':'unit_id','condition_key':'condition','case':'B','control':'A','minimum_units':3,
          'paired':False,'covariates':[],'covariate_types':{},'scale':'raw_counts','min_count':10,'min_samples':3,'size_factor_type':'ratio','fdr':.05}
        request('deseq2','r_omics',{'matrix':out/'counts.tsv','metadata':out/'metadata.tsv','matrix_qc':out/'matrix_qc.json','matrix_qc_receipt':out/'matrix_qc_receipt.json','qc_host_review':out/'host_review.json'},rp,['differential','diagnostics'])
        result=pd.read_csv(out/'deseq2.result/differential.tsv',sep='\t').set_index('feature_id')
        if result.loc[['G'+str(i) for i in range(10)],'log2FoldChange'].median()<=0:raise RuntimeError('Known synthetic contrast direction is wrong')
    write(out/'synthetic_acceptance.json',{'state':'SYNTHETIC_RUNTIME_CHECKS_PASS','ml_executed':True,'numeric_qc_negative_executed':True,
      'DESeq2_executed':bool(args.rscript),'AF3_executed':False,'molecular_engines_executed':False,
      'general_scientific_validity_established':False})
    print('Synthetic server checks completed; this is engine acceptance, not real-study validation.')

if __name__=='__main__':main()
