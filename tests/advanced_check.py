"""Real bounded scientific backends on fixed synthetic fixtures; no private data or scientific claims."""
import json
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))


def main():
    os.environ['BIOMNI_COMPUTE_EDITION']='local'
    import numpy as np
    import pandas as pd
    import anndata as ad
    import scanpy as sc
    from scipy.io import mmwrite
    from scipy.sparse import csr_matrix
    from rdkit import Chem
    from rdkit.Chem import AllChem
    import statistics_ext as st
    import advanced_ext as adv
    from molecular_ext import prepare_ligand_meeko
    from reporting_ext import audit_analysis_result
    context=dict(species='synthetic',model='engineering fixture',assay='synthetic data',biological_unit='synthetic donor',contrast='prespecified synthetic contrast',limitations=['No biological or clinical inference'],input_source='fixed seed generated locally',input_processing='declared synthetic counts/log expression')
    checks=[];rng=np.random.default_rng(71)
    units=['u'+str(i) for i in range(100)]
    a=rng.normal(3,1,50);b=rng.normal(0,1,50)
    r=st.compare_groups(a.tolist(),b.tolist(),units[:50],units[50:]);assert r['effect']['mean_difference']>2 and r['mean_difference_ci'][0]>0;checks.append('welch_effect_interval')
    paired=a-b;r=st.compare_groups(a.tolist(),b.tolist(),units[:50],units[:50],True);assert abs(r['effect']['mean_difference']-paired.mean())<1e-12;checks.append('paired_alignment_and_interval')
    with_ids=['x'+str(i) for i in range(50)]
    try: st.compare_groups(a.tolist(),b.tolist(),with_ids,with_ids)
    except ValueError: pass
    else: raise AssertionError('Pseudoreplication accepted')
    checks.append('comparison_rejects_shared_units')
    power=st.plan_sample_size([.5,.8]);assert power['scenarios'][0]['analyzable_units_group1_or_pairs']==64;assert power['scenarios'][1]['analyzable_units_group1_or_pairs']<64;checks.append('prospective_noncentral_t_power_known_case')
    pp=st.plan_sample_size([.5],design='paired');assert pp['scenarios'][0]['analyzable_units_group1_or_pairs']==34;checks.append('paired_power_known_case')
    studies=[dict(study_id='s'+str(i),cohort_id='c'+str(i),effect=v,standard_error=1.,effect_scale='mean_difference',contrast='fixture') for i,v in enumerate([1.,3.])]
    meta=st.meta_analyze_effects(studies,'mean_difference','fixture','fixed');assert meta['pooled']['effect']==2.;assert abs(meta['pooled']['standard_error']-2**-.5)<1e-12;checks.append('meta_analysis_known_inverse_variance_case')
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);x=rng.normal(size=100);y=2*x+rng.normal(scale=.25,size=100)
        frame=pd.DataFrame({'unit':units,'x':x,'y':y});p=root/'regression.csv';frame.to_csv(p,index=False)
        fit=st.fit_statistical_model(str(p),'y',{'x':'numeric'},context,unit_key='unit')
        co=pd.read_csv(Path(fit['output_directory'])/'coefficients.csv',index_col=0);assert 1.8<co.loc['x','estimate']<2.2;checks.append('OLS_HC3_known_effect')
        probability=1/(1+np.exp(-x));frame['binary']=rng.binomial(1,probability);frame.to_csv(p,index=False)
        logistic=st.fit_statistical_model(str(p),'binary',{'x':'numeric'},context,model='logistic',unit_key='unit');assert logistic['model']=='logistic';checks.append('logistic_real_backend')
        separated=frame.copy();separated['binary']=(separated.x>0).astype(int);sp=root/'separated.csv';separated.to_csv(sp,index=False)
        try: st.fit_statistical_model(str(sp),'binary',{'x':'numeric'},context,model='logistic',unit_key='unit')
        except Exception as exc:
            assert type(exc).__name__ in {'PerfectSeparationWarning','PerfectSeparationError'}
        else: raise AssertionError('Separation must not be reported as completed inference')
        checks.append('logistic_separation_blocks_inference')
        frame['exposure']=rng.uniform(.5,2,size=100);frame['count']=rng.poisson(frame.exposure*np.exp(.2+.3*x));frame.to_csv(p,index=False)
        poisson=st.fit_statistical_model(str(p),'count',{'x':'numeric'},context,model='poisson',unit_key='unit',exposure_key='exposure');assert poisson['exposure_offset']=='exposure';checks.append('poisson_exposure_offset')
        group=np.repeat(np.arange(20),5);random_intercepts=rng.normal(scale=3,size=20);frame['cluster']=['g'+str(i) for i in group];frame['mixed_y']=2*x+random_intercepts[group]+rng.normal(scale=.2,size=100);frame.to_csv(p,index=False)
        mixed=st.fit_statistical_model(str(p),'mixed_y',{'x':'numeric'},context,model='mixed_linear',unit_key='unit',cluster_key='cluster');assert mixed['model']=='mixed_linear';checks.append('random_intercept_real_backend')
        samples=['s'+str(i) for i in range(16)];genes=['g'+str(i) for i in range(60)]
        metadata=pd.DataFrame({'condition':['control']*8+['case']*8,'unit':['donor'+str(i) for i in range(16)],'age':rng.uniform(20,70,16),'time':np.tile([0,1],8)},index=samples)
        means=rng.uniform(40,100,size=(60,16));means[:10,8:]*=4
        matrix=pd.DataFrame(rng.negative_binomial(30,30/(30+means)),index=genes,columns=samples);cp,mp=root/'counts.csv',root/'meta.csv';matrix.to_csv(cp);metadata.to_csv(mp)
        predictors={'condition':{'type':'categorical','reference':'control'},'age':{'type':'numeric'},'time':{'type':'numeric'}}
        for method,kind in [('edgeR_ql','raw_counts'),('limma_voom','raw_counts'),('limma_ebayes','log2_normalized')]:
            source=cp
            if kind=='log2_normalized': source=root/'log.csv';np.log2(matrix+1).to_csv(source)
            fitted=adv.run_designed_expression(str(source),str(mp),kind,'unit',predictors,{'condition[case]':1},context,interactions=[['condition','time']],method=method)
            table=pd.read_csv(Path(fitted['output_directory'])/'differential_expression.csv',index_col=0);assert table.loc[genes[:10],'log2FoldChange'].median()>1
            review=audit_analysis_result(str(Path(fitted['output_directory'])/'summary.json'),context['contrast']);assert review['review_gate_pass']
            checks.append('designed_expression_'+method)
        # Use altered metadata column names to verify donor pipeline normalization.
        cells=['c'+str(i) for i in range(96)];cm=pd.DataFrame({'donor_id':['d'+str(i//8) for i in range(96)],'group':['control']*48+['case']*48,'type':['curated']*96},index=cells)
        raw=rng.poisson(4,size=(60,96));raw[:10,48:]*=4;counts=pd.DataFrame(raw,index=genes,columns=cells);scp,smp=root/'cells.csv',root/'cell_meta.csv';counts.to_csv(scp);cm.to_csv(smp)
        differential=adv.run_donor_differential_state(str(scp),str(smp),'donor_id','group','type',['curated'],'case','control',context,min_cells=5)
        assert differential['all_requested_types_succeeded'];checks.append('donor_differential_state_actual_fit')
        comp=adv.analyze_cell_composition(str(smp),'donor_id','group','type',context,min_cells=5);assert comp['independent_units']==12;checks.append('independent_unit_cell_composition')
        annotated=ad.AnnData(counts.T.astype(float),obs=cm);annotated.layers['counts']=annotated.X.copy();hp=root/'raw.h5ad';annotated.write_h5ad(hp)
        imported=adv.import_expression_data(str(hp),'h5ad',context,layer='counts');assert imported['cells']==96;checks.append('explicit_H5AD_count_layer_import')
        tenx=root/'tenx';tenx.mkdir();mmwrite(tenx/'matrix.mtx',csr_matrix(counts.to_numpy()));(tenx/'features.tsv').write_text(''.join(g+'\t'+g+'\tGene Expression\n' for g in genes));(tenx/'barcodes.tsv').write_text('\n'.join(cells)+'\n')
        imported=adv.import_expression_data(str(tenx),'10x_mtx',context);assert imported['genes']==60;checks.append('10x_MTX_exact_import')
        # Explicit preprocessing for an exploratory, synthetic trajectory fixture.
        sc.pp.normalize_total(annotated);sc.pp.log1p(annotated);sc.pp.pca(annotated,n_comps=10);sc.pp.neighbors(annotated,n_neighbors=8,n_pcs=10);processed=root/'processed.h5ad';annotated.write_h5ad(processed)
        trajectory=adv.infer_diffusion_pseudotime(str(processed),[cells[0],cells[1]],'donor_id',context);assert trajectory['roots']==cells[:2];checks.append('diffusion_pseudotime_root_sensitivity')
        log=np.log2(matrix+1);lp=root/'expression.csv';log.to_csv(lp);network=root/'regulators.csv';pd.DataFrame({'regulator':['TF']*10,'target':genes[:10],'weight':[1.]*10},index=['e'+str(i) for i in range(10)]).to_csv(network)
        rc={**context,'network_source':'synthetic network','network_version':'fixture-v1','gene_namespace':'synthetic IDs'}
        regulatory=adv.score_regulatory_activity(str(lp),str(mp),str(network),rc);assert regulatory['regulators']==1;checks.append('weighted_regulatory_score_with_coverage')
        edge=root/'edges.csv';pd.DataFrame({'source':['A','B','C','D','A'],'target':['B','C','D','A','C'],'score':[.9,.8,.7,.9,.6]},index=['e'+str(i) for i in range(5)]).to_csv(edge)
        stable=adv.audit_network_stability(str(edge),rc,[.6,.85],[.5,1.],null_permutations=2);assert stable['fixed_node_universe']==4;checks.append('network_threshold_and_null_sensitivity')
        pred=[dict(unit='v'+str(i),y=i%2,p=.8 if i%2 else .2) for i in range(20)];split=st.audit_prediction_split(['training'],[r['unit'] for r in pred],['training'])
        evaluated=adv.evaluate_binary_prediction(pred,'y','p','unit',.5,split);assert evaluated['roc_auc']==1 and evaluated['confusion_counts']['FP']==0;checks.append('validation_discrimination_and_calibration')
        try: adv.evaluate_binary_prediction(pred,'y','p','unit',.5,st.audit_prediction_split(['training'],['other-validation'],['training']))
        except ValueError: pass
        else: raise AssertionError('An unrelated split receipt must not authorize performance evaluation')
        checks.append('prediction_requires_exact_validation_units')
        mol=Chem.AddHs(Chem.MolFromSmiles('CCO'));assert AllChem.EmbedMolecule(mol,randomSeed=42)==0;sdf=root/'ligand.sdf';writer=Chem.SDWriter(str(sdf));writer.write(mol);writer.close()
        prepared=prepare_ligand_meeko(str(sdf),{**context,'protonation_review':'synthetic neutral ethanol','stereochemistry_review':'no stereocenters','tautomer_review':'fixed synthetic state'});assert Path(prepared['output_directory'],'ligand.pdbqt').is_file();checks.append('Meeko_real_ligand_preparation')
        # Tampering must fail result review, including nested files.
        directory=Path(fitted['output_directory']);(directory/'design_matrix.csv').write_text('altered')
        assert not audit_analysis_result(str(directory/'summary.json'),context['contrast'])['review_gate_pass'];checks.append('result_integrity_rejects_tampering')
    print(json.dumps({'pass':True,'checks':checks,'limitations':['Fixed synthetic fixtures establish engineering behavior only.','No real clinical, biological, live Slurm, Cytoscape GUI or server-only R workflow validation is claimed.']},indent=2))


if __name__=='__main__': main()
