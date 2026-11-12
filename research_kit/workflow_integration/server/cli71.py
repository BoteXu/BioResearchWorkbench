"""Fixed, offline server pipelines. No arbitrary shell strings, downloads or installations."""
from pathlib import Path
import subprocess,json,itertools,csv,bz2
from runtime import write,read,sha,selected

def analyze(job,out):
    import numpy as np,pandas as pd
    p=job['parameters'];I={k:Path(v) for k,v in job['inputs'].items()};key=job['analysis_id'];commands=[];versions={};metrics={};external_bindings=[]
    def run(argv):
        argv=list(map(str,argv));commands.append(argv)
        with (out/'engine.log').open('ab') as log:subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True,cwd=out)
    def table(role,cols=()):
        z=pd.read_csv(I[role],sep='\t',dtype={k:str for k in ('sample_id','unit_id','variant_id','mutation_id','feature_id','FID','IID')})
        from method_contract71 import strict_bool
        for name in set(z)&{'normal_reviewed','read_bias_assessed'}:z[name]=z[name].map(strict_bool)
        if z.empty or not set(cols)<=set(z):raise ValueError('Invalid selected '+role)
        return z
    def manifest(role):
        """Verify each dependency file from the selected private project manifest."""
        data=read(I[role]);root=I[role].parent;paths=[]
        for row in data['files']:
            f=selected(root,row['path'])
            if sha(f)!=row['sha256']:raise ValueError('Reference/database source changed')
            paths.append(f);external_bindings.append({'path':str(f),'sha256':row['sha256'],'bytes':f.stat().st_size})
        if not paths:raise ValueError('No bound existing reference files')
        return data,paths
    def version(exe,flag='--version'):
        r=subprocess.run([exe,flag],capture_output=True,text=True,check=True);versions[exe]=(r.stdout+r.stderr).strip()
        if not versions[exe]:raise ValueError('Could not recover actual software version')
    if key=='bulk_cnv':
        z=table('segments',['chromosome','start','end','log2','probes']);qc=table('reference_qc',['reference_sex','normal_reviewed','read_bias_assessed'])
        if not qc.normal_reviewed.all() or not qc.read_bias_assessed.all() or set(qc.reference_sex)!={p['reference_sex']} or (z.end<=z.start).any() or (z.probes<=0).any():raise ValueError('CNV normal reference/segmentation QC failed')
        if not 0<p['purity']<=1 or p['ploidy']<1:raise ValueError('Explicit purity/ploidy required')
        version('cnvkit.py');target=out/'called.cns';argv=['cnvkit.py','call',I['segments'],'--method','clonal','--purity',p['purity'],'--ploidy',p['ploidy'],'--sample-sex',p['sample_sex'],'--min-variant-depth',p['min_variant_depth'],'--vcf',I['variants'],'--output',target]
        if p['reference_sex']=='male':argv+=['--male-reference']
        run(argv);called=pd.read_csv(target,sep='\t')
        if not {'cn','cn1','cn2','baf'}<=set(called):raise ValueError('Allele-specific CNV output unavailable; do not invent allele states')
        A=called;B=called[['chromosome','start','end','cn','cn1','cn2','baf']];C=pd.DataFrame({'purity':[p['purity']],'ploidy':[p['ploidy']],'solution_scope':['prespecified_grid_point_not_estimated_posterior']});D=qc.assign(segments=len(called),covered_bases=(called.end-called.start).sum());metrics={'segments':len(called),'allele_assessed_segments':int(called.baf.notna().sum()),'purity':p['purity'],'ploidy':p['ploidy']}
    elif key=='clonal_phylogeny':
        z=table('mutations',['mutation_id','sample_id','ref_counts','alt_counts','normal_cn','major_cn','minor_cn','tumour_content'])
        if z[['mutation_id','sample_id']].duplicated().any() or (z[['ref_counts','alt_counts','major_cn','minor_cn']]<0).any().any() or not z.tumour_content.between(0,1,inclusive='right').all():raise ValueError('Mutation counts/copy state/purity invalid')
        if z.groupby('mutation_id').sample_id.apply(lambda v:tuple(sorted(v))).nunique()!=1:raise ValueError('Unequal mutation-by-sample denominator')
        if (z[['ref_counts','alt_counts','normal_cn','major_cn','minor_cn']]%1!=0).any().any() or (z.major_cn<z.minor_cn).any() or ((z.ref_counts+z.alt_counts)<=0).any():raise ValueError('Noninteger/invalid copy state or uncovered mutation')
        version('pyclone-vi');h=out/'pyclone.h5';raw=out/'clones.tsv';run(['pyclone-vi','fit','-i',I['mutations'],'-o',h,'-c',p['num_clusters'],'-r',p['num_restarts'],'--seed',p['seed']]);run(['pyclone-vi','write-results-file','-i',h,'-o',raw]);cc=pd.read_csv(raw,sep='\t')
        if not {'cellular_prevalence','cellular_prevalence_std','cluster_assignment_prob'}<=set(cc):raise ValueError('PyClone uncertainty columns missing')
        summary=cc.groupby(['cluster_id','sample_id'],as_index=False).agg(ccf=('cellular_prevalence','mean'),ccf_sd=('cellular_prevalence_std','mean'),mutations=('mutation_id','nunique'));pv=summary.pivot(index='cluster_id',columns='sample_id',values='ccf')
        if pv.isna().any().any() or len(pv)>min(p['max_clones'],8):raise ValueError('Bounded exact candidate-tree enumeration requires <=8 complete clones')
        order=pv.index.tolist();parents={c:[-1]+[v for v in order if v!=c and np.all(pv.loc[v]+p['tree_tolerance']>=pv.loc[c])] for c in order};trees=[];counts=[];tested=0
        possibilities=__import__('math').prod(len(parents[c]) for c in order)
        if possibilities>p['max_tree_assignments']:raise ValueError('Complete candidate-tree enumeration exceeds the declared budget; do not report a partial arbitrary tree set')
        for choice in itertools.product(*(parents[c] for c in order)):
            tested+=1;pa=dict(zip(order,choice));valid=True
            for start in order:
                visited=set();node=start
                while node!=-1:
                    if node in visited:valid=False;break
                    visited.add(node);node=pa[node]
                if not valid:break
            if not valid:continue
            for parent in [-1]+order:
                children=[c for c in order if pa[c]==parent];den=np.ones(pv.shape[1]) if parent==-1 else pv.loc[parent].to_numpy()
                if children and np.any(pv.loc[children].sum(axis=0).to_numpy()>den+p['tree_tolerance']):valid=False;break
            if valid:
                tid=len(counts);trees.extend((tid,int(c),int(pa[c])) for c in order);counts.append(tid)
        if not counts:raise ValueError('No sum-rule-compatible phylogeny; do not return an arbitrary tree')
        A=cc;B=pd.DataFrame(trees,columns=['candidate_tree','clone','parent']);C=summary;D=pd.DataFrame({'constraint':['sum_rule_tolerance','tested_assignments','compatible_candidates'],'observed':[p['tree_tolerance'],tested,len(counts)]});metrics={'clones':len(pv),'samples':pv.shape[1],'compatible_trees':len(counts),'tested_assignments':tested}
    elif key=='footprinting':
        import pyBigWig,pysam
        
        if p['organism']!=job['context']['species']:raise ValueError('Footprinting species differs from reference context')
        if p['footprint_max_width']<p['footprint_min_width']:raise ValueError('Maximum footprint width must cover minimum width')
        version('TOBIAS');peaks=pd.read_csv(I['peaks'],sep='\t',header=None,comment='#')
        if peaks.shape[1]<3 or (peaks[2]<=peaks[1]).any():raise ValueError('Invalid peak BED coordinates')
        with pysam.AlignmentFile(I['bam'],'rb',index_filename=str(I['bam_index'])) as bam:
            if not bam.has_index():raise ValueError('ATAC BAM index missing')
            if not set(peaks[0])<=set(bam.references):raise ValueError('Peak/BAM reference chromosomes disagree')
            with pysam.FastaFile(I['genome'],filepath_index=str(I['genome_index'])) as reference:
                if any(ch not in reference.references or reference.get_reference_length(ch)!=bam.get_reference_length(ch) for ch in set(peaks[0])):raise ValueError('BAM/genome coordinate lengths disagree')
        run(['TOBIAS','ATACorrect','--bam',I['bam'],'--genome',I['genome'],'--peaks',I['peaks'],'--outdir',out/'bias','--prefix','sample','--cores',p['cores']])
        corrected=out/'bias/sample_corrected.bw';bias=out/'bias/sample_bias.bw';scores=out/'footprints.bw'
        run(['TOBIAS','ScoreBigwig','--signal',corrected,'--regions',I['peaks'],'--output',scores,'--score','footprint','--fp-min',p['footprint_min_width'],'--fp-max',p['footprint_max_width'],'--cores',p['cores']])
        run(['TOBIAS','BINDetect','--motifs',I['motifs'],'--signals',scores,'--genome',I['genome'],'--peaks',I['peaks'],'--outdir',out/'binding','--cores',p['cores']])
        raw=out/'binding/bindetect_results.txt'
        if not raw.is_file():raise ValueError('Actual BINDetect result absent')
        binding=pd.read_csv(raw,sep='\t');profiles=[]
        with pyBigWig.open(str(scores)) as bw,pyBigWig.open(str(bias)) as bi:
            for row in peaks.itertuples(index=False,name=None):
                chrom,start,end=row[:3];bins=min(50,int(end-start));v=bw.stats(chrom,int(start),int(end),nBins=bins);b=bi.stats(chrom,int(start),int(end),nBins=bins)
                profiles.extend((chrom,start,end,j,sv,bv) for j,(sv,bv) in enumerate(zip(v,b)))
        A=pd.DataFrame(profiles,columns=['chromosome','start','end','relative_bin','footprint_score','sequence_bias']);B=binding;C=A[['chromosome','start','end','relative_bin','sequence_bias']];D=pd.DataFrame({'chromosome':peaks[0],'start':peaks[1],'end':peaks[2]});metrics={'peaks':len(peaks),'motifs_tested':len(binding),'profile_bins':len(A)}
    elif key=='microbe_gene_context':
        db,files=manifest('annotation_database');data_dir=files[0].parent
        if any(f.parent!=data_dir for f in files):raise ValueError('eggNOG selected database files must share one reviewed directory')
        version('emapper.py');run(['emapper.py','-i',I['fasta'],'--itype','proteins','--data_dir',data_dir,'--offline','--tax_scope',p['tax_scope'],'--cpu',p['cores'],'--output','annotation','--output_dir',out])
        fn=out/'annotation.emapper.annotations';lines=fn.read_text(encoding='utf8').splitlines();header=next((l for l in lines if l.startswith('#query\t')),None)
        if not header:raise ValueError('Unknown eggNOG annotation schema')
        columns=header.lstrip('#').split('\t');rows=[l.split('\t') for l in lines if l and not l.startswith('#')];ann=pd.DataFrame(rows,columns=columns)
        ids=[]
        with I['fasta'].open() as f:
            for line in f:
                if line.startswith('>'):ids.append(line[1:].split()[0])
        if not ids or len(ids)!=len(set(ids)) or not set(ann['query'])<=set(ids):raise ValueError('Protein query identity mismatch')
        def go_count(value):
            if pd.isna(value) or str(value) in {'','-','NA'}:return 0
            return len({term for term in str(value).split(',') if term.startswith('GO:')})
        A=ann;B=ann[[c for c in ('query','seed_ortholog','evalue','score','eggNOG_OGs','max_annot_lvl') if c in ann]];C=pd.DataFrame({'query':ids,'annotated':[q in set(ann['query']) for q in ids]});D=ann[['query']].assign(function_count=ann.get('GOs',pd.Series('',index=ann.index)).map(go_count));metrics={'queried_proteins':len(ids),'annotated_proteins':len(ann),'coverage':len(ann)/len(ids)}
    elif key=='microbe_strain':
        data,files=manifest('marker_manifest');database,dbfiles=manifest('database');units=data['units']
        if set(units)!=set(f.name for f in files) or any(not v for v in units.values()):raise ValueError('Marker/sample independent-unit mapping incomplete')
        if len(set(units.values()))!=len(units):raise ValueError('This strain comparison route requires one sample per independent unit')
        dbfile=next((f for f in dbfiles if f.name.endswith('.pkl')),None)
        if dbfile is None:raise ValueError('Existing exact MetaPhlAn database pickle required')
        version('strainphlan');run(['strainphlan','-s',*files,'-m',I['clade_markers'],'-c',p['clade'],'-d',dbfile,'-o',out,'-n',p['cores'],'--marker_in_n_samples',p['marker_in_n_samples'],'--sample_with_n_markers',p['sample_with_n_markers']])
        trees=list(out.glob('RAxML_bestTree.*'))+list(out.glob('*.tre'))
        if len(trees)!=1:raise ValueError('Ambiguous or missing actual strain phylogeny')
        from Bio import Phylo
        tree=Phylo.read(trees[0],'newick');leaves=tree.get_terminals();dist=[(a.name,b.name,tree.distance(a,b)) for i,a in enumerate(leaves) for b in leaves[i+1:]];coverage=[]
        for f in files:
            with bz2.open(f,'rt') as h:obj=json.load(h)
            markers=obj.get('markers')
            if not isinstance(markers,list):raise ValueError('Unsupported StrainPhlAn marker profile schema; review installed version before interpreting coverage')
            sequences=[m['sequence'] for m in markers]
            if not sequences or len({m['marker'] for m in markers})!=len(markers):raise ValueError('Missing or duplicated consensus markers')
            total=sum(map(len,sequences));amb=sum(s.upper().count('N')+s.count('-')+s.count('*') for s in sequences)
            if not total:raise ValueError('Empty consensus marker sequence denominator')
            coverage.append((f.name,units[f.name],len(markers),total,amb/total))
        A=pd.DataFrame(coverage,columns=['profile','unit_id','markers','marker_bases','gap_fraction']);
        leaf_map=data['leaf_to_profile']
        if len({n.name for n in leaves})!=len(leaves) or set(n.name for n in leaves)!=set(leaf_map) or not set(leaf_map.values())<=set(units):raise ValueError('Strain tree tips require a complete reviewed mapping to actual input profiles')
        B=pd.DataFrame(dist,columns=['source','target','patristic_distance']);C=A.copy();D=pd.DataFrame({'leaf':[n.name for n in leaves],'terminal_branch_length':[n.branch_length for n in leaves]});metrics={'independent_units':len(files),'tree_leaves':len(leaves),'marker_profiles':len(coverage)}
    elif key=='scenic_regulons':
        x=pd.read_csv(I['matrix'],sep='\t',index_col=0);s=table('samples',['sample_id','unit_id']);db,rankfiles=manifest('ranking_databases')
        if x.index.duplicated().any() or set(x.columns)!=set(s.sample_id) or not np.isfinite(x.to_numpy()).all() or (x<0).any().any():raise ValueError('SCENIC expression/independent-unit mapping invalid')
        if s.unit_id.nunique()<4:raise ValueError('SCENIC donor stability requires >=4 independent units')
        if not 0<p['donor_subsample_fraction']<=1:raise ValueError('Explicit donor subset fraction required')
        eligible=s[~s.unit_id.isin(p['heldout_units'])];
        if eligible.unit_id.nunique()<4:raise ValueError('Insufficient SCENIC training donors after excluding locked holdout')
        rng=np.random.default_rng(p['seed']);donors=rng.choice(sorted(eligible.unit_id.unique()),max(3,int(eligible.unit_id.nunique()*p['donor_subsample_fraction'])),replace=False);s=s[s.unit_id.isin(donors)];x=x.loc[:,s.sample_id]
        if set(s.unit_id)&set(p['heldout_units']):raise ValueError('SCENIC training subset includes declared held-out donors')
        expression=out/'cells_by_genes.tsv';x.T.to_csv(expression,sep='\t');edges=out/'adjacencies.tsv';motifs=out/'regulons.csv';aucs=out/'activity.csv';version('pyscenic')
        run(['pyscenic','grn',expression,I['tf_list'],'--num_workers',p['workers'],'--seed',p['seed'],'-o',edges])
        run(['pyscenic','ctx',edges,*rankfiles,'--annotations_fname',I['motif_annotations'],'--expression_mtx_fname',expression,'--num_workers',p['workers'],'--output',motifs,'--mode','dask_multiprocessing'])
        run(['pyscenic','aucell',expression,motifs,'--num_workers',p['workers'],'--auc_threshold',p['auc_threshold'],'--seed',p['seed'],'-o',aucs])
        from pyscenic.utils import load_motifs
        from pyscenic.prune import df2regulons
        motifdf=load_motifs(str(motifs));reg=df2regulons(motifdf);rows=[(r.name,g,w) for r in reg for g,w in r.gene2weight.items()];A=pd.DataFrame(rows,columns=['regulon','target','weight']);B=pd.read_csv(aucs,index_col=0).reset_index(names='cell_id');C=motifdf.reset_index();C.columns=['|'.join(map(str,c)) if isinstance(c,tuple) else str(c) for c in C.columns];D=pd.read_csv(edges,sep='\t');pd.DataFrame({'unit_id':donors}).to_csv(out/'actual_training_units.tsv',sep='\t',index=False);metrics={'regulons':len(reg),'regulon_edges':len(A),'donors':s.unit_id.nunique(),'cells':x.shape[1]}
    elif key=='polygenic_score':
        from sklearn.metrics import r2_score,mean_squared_error
        import statsmodels.api as sm
        if p['endpoint_type'] not in ('continuous','binary'):raise ValueError('Explicit continuous or binary endpoint required')
        geno,files=manifest('genotypes');variants=table('genotype_variants',['variant_id','ref','alt']);w=table('weights',['variant_id','effect_allele','beta']);s=table('samples',['sample_id','unit_id','FID','IID',p['phenotype']]);s[['sample_id','unit_id','FID','IID']]=s[['sample_id','unit_id','FID','IID']].astype(str);base=table('base_cohorts',['unit_id'])
        if s.unit_id.duplicated().any() or set(s.unit_id)&set(base.unit_id):raise ValueError('PRS discovery/target overlap or repeated target units')
        train=set(p['training_units']);test=set(p['test_units'])
        if train&test or train|test!=set(s.unit_id) or min(len(train),len(test))<10:raise ValueError('Explicit disjoint complete training/test units required')
        merged=w.merge(variants,on='variant_id',validate='one_to_one')
        if len(merged)!=len(w) or not ((merged.effect_allele==merged.ref)|(merged.effect_allele==merged.alt)).all() or merged.alt.str.contains(',').any():raise ValueError('Unresolved missing/strand/multiallelic PRS weights')
        pvar=next(f for f in files if f.suffix=='.pvar')
        with pvar.open() as handle:
            skip=0
            for line in handle:
                if line.startswith('##'):skip+=1
                else:break
        actual=pd.read_csv(pvar,sep='\t',skiprows=skip,dtype=str).rename(columns={'ID':'variant_id','REF':'ref','ALT':'alt','#CHROM':'chromosome'})
        locked=merged.merge(actual[['variant_id','ref','alt','chromosome']],on='variant_id',suffixes=('','_actual'),validate='one_to_one')
        if len(locked)!=len(w) or (locked.ref!=locked.ref_actual).any() or (locked.alt!=locked.alt_actual).any() or not set(locked.chromosome)<=set(p['autosomal_chromosomes']):raise ValueError('PRS provided alleles do not match actual diploid autosomal pvar records')
        prefixes={str(f.with_suffix('')) for f in files}
        if len(prefixes)!=1 or {f.suffix for f in files}!={'.pgen','.pvar','.psam'}:raise ValueError('Require exact bound PLINK2 pfile triplet')
        wf=out/'locked_weights.tsv';w.to_csv(wf,sep='\t',index=False);version('plink2');run(['plink2','--pfile',next(iter(prefixes)),'--score',wf,'1','2','3','header-read','list-variants','cols=+scoresums','--out',out/'prs'])
        used=pd.read_csv(out/'prs.sscore.vars',header=None,dtype=str).iloc[:,0]
        if set(used)!=set(w.variant_id.astype(str)) or len(used)!=len(w):raise ValueError('PLINK did not actually score the complete locked variant set')
        z=pd.read_csv(out/'prs.sscore',sep=r'\s+',dtype={'#FID':str,'FID':str,'IID':str}).rename(columns={'#FID':'FID'});score=s.merge(z,on=['FID','IID'],validate='one_to_one')
        if len(score)!=len(s) or 'SCORE1_SUM' not in score:raise ValueError('Actual PRS scoring denominator incomplete')
        if 'ALLELE_CT' not in score or (score.ALLELE_CT<2*len(w)*(1-p['max_missing_genotype_fraction'])).any():raise ValueError('Actual nonmissing scored allele count below the explicit missingness threshold')
        tr=score.unit_id.isin(train);te=score.unit_id.isin(test);covariates=p['calibration_covariates'];
        if not set(covariates)<=set(score):raise ValueError('Selected PRS calibration covariates missing')
        encoded=pd.get_dummies(score[covariates],drop_first=True,dtype=float) if covariates else pd.DataFrame(index=score.index)
        design=sm.add_constant(pd.concat([score[['SCORE1_SUM']],encoded],axis=1),has_constant='add')
        base_design=sm.add_constant(encoded,has_constant='add')
        if np.linalg.matrix_rank(design.loc[tr].to_numpy())!=design.shape[1] or design.loc[tr].isna().any().any():raise ValueError('PRS training design is singular or missing')
        y=pd.to_numeric(score[p['phenotype']],errors='raise')
        if p['endpoint_type']=='continuous':
            f=sm.OLS(y[tr],design.loc[tr]).fit();baseline=sm.OLS(y[tr],base_design.loc[tr]).fit();pred=f.predict(design.loc[te]);bp=baseline.predict(base_design.loc[te]);cal=sm.OLS(y[te],sm.add_constant(pred,has_constant='add')).fit()
            C=pd.DataFrame({'metric':['test_R2','test_RMSE','baseline_RMSE','calibration_intercept','calibration_slope'],'value':[r2_score(y[te],pred),np.sqrt(mean_squared_error(y[te],pred)),np.sqrt(mean_squared_error(y[te],bp)),cal.params.iloc[0],cal.params.iloc[1]]})
        else:
            from sklearn.metrics import roc_auc_score,average_precision_score,brier_score_loss,log_loss
            if set(y)!={0,1} or min(y[tr].value_counts().min(),y[te].value_counts().min())<2:raise ValueError('PRS binary endpoint requires both classes in the locked training and test sets')
            f=sm.GLM(y[tr],design.loc[tr],family=sm.families.Binomial()).fit();baseline=sm.GLM(y[tr],base_design.loc[tr],family=sm.families.Binomial()).fit()
            if not f.converged or not baseline.converged:raise ValueError('PRS binomial model failed to converge')
            pred=f.predict(design.loc[te]);bp=baseline.predict(base_design.loc[te]);C=pd.DataFrame({'metric':['ROC_AUC','average_precision','Brier','log_loss','baseline_Brier'],'value':[roc_auc_score(y[te],pred),average_precision_score(y[te],pred),brier_score_loss(y[te],pred),log_loss(y[te],pred),brier_score_loss(y[te],bp)]})
        A=w;B=score.loc[te,['unit_id','SCORE1_SUM',p['phenotype']]].assign(predicted=pred);D=locked.assign(overlap_audit_scope='selected_discovery_and_target_manifest_only')
        metrics={'locked_variants':len(w),'training_units':len(train),'test_units':len(test),'heldout_metric_count':len(C)}
    else:raise ValueError('No fixed offline CLI pipeline '+key)
    mapping={}
    for role,obj in zip(job['required_roles'],[A,B,C,D]):
        if not isinstance(obj,pd.DataFrame) or not len(obj.columns):raise ValueError('Actual typed CLI result absent')
        name=role+'.tsv';obj.to_csv(out/name,sep='\t',index=False,na_rep='NA');mapping[role]=name
    for binding in external_bindings:
        if sha(binding['path'])!=binding['sha256']:raise ValueError('External reference changed during scientific execution')
    write(out/'external_references.private.json',external_bindings)
    write(out/'commands.private.json',{'argv':commands,'versions':versions,'offline':True,'automatic_install':False})
    write(out/'diagnostics.private.json',{'fit_completed':True,'metrics':{k:float(v) for k,v in metrics.items()},'actual_software_versions':versions,
      'method':p['implementation'],'scientific_acceptance':'NOT_ESTABLISHED'})
    return mapping
