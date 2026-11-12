"""Specialist single-cell / contact-map code, executed exclusively after server guard."""
from pathlib import Path
from runtime import write

def analyze(job,out):
    import numpy as np,pandas as pd
    from scipy import sparse,spatial
    p=job['parameters'];I=job['inputs'];key=job['analysis_id'];metrics={}
    def df(role,cols=()):
        d=pd.read_csv(I[role],sep='\t',dtype={k:str for k in ('spot_id','cell_id','unit_id','sample_id','complex_id','feature_id')})
        if d.empty or not set(cols)<=set(d) or d.columns.duplicated().any():raise ValueError('Invalid selected '+role)
        from method_contract71 import strict_bool
        for name in set(d)&{'reviewed'}:d[name]=d[name].map(strict_bool)
        return d
    def dense(x):return x.toarray() if sparse.issparse(x) else np.asarray(x)
    if key in {'kinetic_velocity','fate_probabilities','lr_consensus','spatial_domains'}:
        import anndata as ad
        a=ad.read_h5ad(I['adata'])
        if not a.obs_names.is_unique or not a.var_names.is_unique or not {'unit_id','sample_id'}<=set(a.obs):raise ValueError('Exact cell/sample/independent unit mapping required')
        if a.obs[['unit_id','sample_id']].isna().any().any():raise ValueError('Missing unit map')
        if a.obs.groupby('sample_id',observed=True).unit_id.nunique().gt(1).any():raise ValueError('One literal sample cannot belong to multiple independent units')
        if a.n_obs<20 or a.n_vars<10:raise ValueError('Insufficient selected data geometry')
        metrics={'cells':a.n_obs,'features':a.n_vars,'independent_units':a.obs.unit_id.nunique()}
    if key=='kinetic_velocity':
        import scvelo as scv
        if not {'spliced','unspliced'}<=set(a.layers):raise ValueError('Assay must provide real spliced/unspliced count layers')
        for name in ('spliced','unspliced'):
            v=a.layers[name];d=v.data if sparse.issparse(v) else v
            if not np.isfinite(d).all() or (d<0).any() or (d!=np.round(d)).any():raise ValueError('Velocity requires raw nonnegative count layers')
        scv.pp.filter_and_normalize(a,min_shared_counts=p['min_shared_counts'],n_top_genes=p['n_top_genes'])
        import scanpy as sc
        sc.pp.pca(a,n_comps=min(p['n_pcs'],a.n_vars-1,a.n_obs-1),random_state=p['seed']);sc.pp.neighbors(a,n_neighbors=p['n_neighbors'],random_state=p['seed'])
        donor=a.obs.unit_id.to_numpy()
        for graph in ('connectivities','distances'):
            coo=a.obsp[graph].tocoo();keep=donor[coo.row]==donor[coo.col];a.obsp[graph]=sparse.csr_matrix((coo.data[keep],(coo.row[keep],coo.col[keep])),shape=coo.shape)
        neighbors=np.diff(a.obsp['connectivities'].indptr)
        if neighbors.min()<p['min_within_donor_neighbors']:raise ValueError('Velocity graph has insufficient within-donor neighbors; increase donor coverage or fit separate donors')
        weights=a.obsp['connectivities']+sparse.eye(a.n_obs);weights=sparse.diags(1/np.asarray(weights.sum(axis=1)).ravel())@weights
        a.layers['Ms']=dense(weights @ a.layers['spliced']);a.layers['Mu']=dense(weights @ a.layers['unspliced'])
        a.uns['velocity_neighbor_scope']='within_donor_conditional_joint_gene_kinetics'
        metrics['minimum_within_donor_neighbors']=int(neighbors.min())
        scv.tl.recover_dynamics(a,n_jobs=1)
        scv.tl.velocity(a,mode='dynamical');scv.tl.velocity_graph(a,n_jobs=1);scv.tl.velocity_confidence(a)
        A=pd.DataFrame(dense(a.layers['velocity']),index=a.obs_names,columns=a.var_names).reset_index(names='cell_id')
        B=a.var.filter(regex='^fit_').reset_index(names='feature_id');C=a.obs.filter(regex='velocity_|unit_id|sample_id').reset_index(names='cell_id')
        sp=a.layers['spliced'];un=a.layers['unspliced'];D=pd.DataFrame({'feature_id':a.var_names,'spliced_sum':np.asarray(sp.sum(axis=0)).ravel(),'unspliced_sum':np.asarray(un.sum(axis=0)).ravel()})
        if 'fit_likelihood' not in a.var or not np.isfinite(a.var.fit_likelihood).any():raise ValueError('No kinetic genes actually fitted')
        metrics['fitted_kinetic_genes']=int(np.isfinite(a.var.fit_likelihood).sum());a.write_h5ad(out/'velocity_result.h5ad')
    elif key=='fate_probabilities':
        import cellrank as cr
        if 'connectivities' not in a.obsp or a.uns.get('velocity_neighbor_scope')!='within_donor_conditional_joint_gene_kinetics':raise ValueError('Fate model requires the reviewed donor-restricted velocity graph')
        if 'velocity' not in a.layers or not p['root_evidence']:raise ValueError('Require actual velocity and reviewed origin evidence')
        weight=p['transition_weight']
        if not 0<weight<1 or not isinstance(p['terminal_states'],dict) or len(p['terminal_states'])<2:raise ValueError('Explicit mixed kernel weight and terminal cell sets required')
        all_terminal=[c for ids in p['terminal_states'].values() for c in ids]
        if len(all_terminal)!=len(set(all_terminal)) or not set(all_terminal)<=set(a.obs_names):raise ValueError('Terminal states overlap or leave selected cells')
        vk=cr.kernels.VelocityKernel(a).compute_transition_matrix();ck=cr.kernels.ConnectivityKernel(a).compute_transition_matrix();kernel=weight*vk+(1-weight)*ck
        coo=kernel.transition_matrix.tocoo();donor=a.obs.unit_id.to_numpy()
        if (coo.data[donor[coo.row]!=donor[coo.col]]>0).any():raise ValueError('Fate transitions incorrectly connect independent donors')
        for unit in set(donor):
            unit_cells=set(a.obs_names[donor==unit])
            if any(not unit_cells&set(cells) for cells in p['terminal_states'].values()):raise ValueError('Every compared terminal state needs an anchor in each disconnected donor graph; absent anchors are unassessed, not zero fate')
        g=cr.estimators.GPCCA(kernel);g.set_terminal_states(p['terminal_states'],cluster_key=p['cluster_key']);g.compute_fate_probabilities(use_petsc=False)
        probs=np.asarray(g.fate_probabilities)
        if not np.isfinite(probs).all() or (probs<0).any() or not np.allclose(probs.sum(axis=1),1,atol=.001):raise ValueError('Fate solution not normalized')
        A=pd.DataFrame(probs,index=a.obs_names,columns=g.fate_probabilities.names).reset_index(names='cell_id')
        B=pd.DataFrame([(name,c) for name,ids in p['terminal_states'].items() for c in ids],columns=['terminal_state','cell_id'])
        trans=kernel.transition_matrix;C=pd.DataFrame({'cell_id':a.obs_names,'transition_rowsum':np.asarray(trans.sum(axis=1)).ravel(),'fate_rowsum':probs.sum(axis=1)})
        D=a.obs[['unit_id','sample_id',p['cluster_key']]].reset_index(names='cell_id');metrics['terminal_states']=len(p['terminal_states']);metrics['maximum_rowsum_error']=float(np.max(abs(probs.sum(axis=1)-1)))
        a.write_h5ad(out/'fate_result.h5ad')
    elif key=='lr_consensus':
        import liana as li
        resource=df('lr_resource',['ligand','receptor']);subunits=df('lr_subunits',['complex_id','feature_id']);parts=[];coverage=[];abundance=[]
        if resource[['ligand','receptor']].duplicated().any() or subunits[['complex_id','feature_id']].duplicated().any():raise ValueError('Duplicate LR/complex definition')
        if not set(resource.ligand)|set(resource.receptor)<=set(subunits.complex_id):raise ValueError('Every LR complex needs an explicit subunit map')
        complexes={k:list(g.feature_id) for k,g in subunits.groupby('complex_id')}
        if not set(subunits.feature_id)<=set(a.var_names):raise ValueError('LR complex subunits absent from the observed gene universe')
        if job['context']['scale']!='log1p_normalized_expression':raise ValueError('LIANA requires explicitly normalized log1p expression; raw counts are not interchangeable')
        d=a.X.data if sparse.issparse(a.X) else a.X
        if not np.isfinite(d).all() or (d<0).any():raise ValueError('Invalid log1p matrix')
        for donor in sorted(a.obs.unit_id.unique()):
            v=a[a.obs.unit_id==donor].copy();counts=v.obs[p['groupby']].value_counts().reindex(p['celltype_universe'],fill_value=0)
            if set(v.obs[p['groupby']])!=set(p['celltype_universe']):raise ValueError('LR donor cell-type universe differs; missing populations cannot be replaced by zero scores')
            if (counts<p['min_cells']).any():raise ValueError('A donor cell population lacks declared expression coverage')
            li.mt.rank_aggregate(v,groupby=p['groupby'],resource=resource,expr_prop=p['expr_prop'],min_cells=p['min_cells'],n_perms=p['n_perms'],seed=p['seed'],use_raw=False,inplace=True,n_jobs=1,return_all_lrs=True)
            z=v.uns['liana_res'].copy();z['unit_id']=donor;parts.append(z);coverage.extend((donor,c,int(n)) for c,n in counts.items())
            linear=v.X.copy()
            if sparse.issparse(linear):linear.data=np.expm1(linear.data)
            else:linear=np.expm1(linear)
            if not np.isfinite(linear.data if sparse.issparse(linear) else linear).all():raise ValueError('LR log1p inversion overflow')
            means={}
            for celltype in p['celltype_universe']:
                values=np.asarray(linear[v.obs[p['groupby']].eq(celltype).to_numpy()].mean(axis=0)).ravel();means[celltype]={c:float(min(values[v.var_names.get_indexer(genes)])) for c,genes in complexes.items()}
            for source in p['celltype_universe']:
                for target in p['celltype_universe']:
                    for interaction in resource.itertuples():
                        lm=means[source][interaction.ligand];rm=means[target][interaction.receptor];abundance.append((str(donor),source,target,interaction.ligand,interaction.receptor,lm,rm,float(np.log1p(lm*rm)),int(counts[source]),int(counts[target])))
        A=pd.concat(parts,ignore_index=True);B=pd.DataFrame(abundance,columns=['unit_id','source','target','ligand','receptor','ligand_linear_mean','receptor_linear_mean','abundance_score','source_cells','target_cells']);C=pd.DataFrame(coverage,columns=['unit_id','celltype','cells']);D=resource.assign(ligand_present=[all(g in a.var_names for g in complexes[c]) for c in resource.ligand],receptor_present=[all(g in a.var_names for g in complexes[c]) for c in resource.receptor]);metrics['donor_lr_tests']=len(A)
    elif key=='spatial_domains':
        from sklearn.decomposition import PCA
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import adjusted_rand_score
        hist=df('histology',['spot_id','label','reviewed']);
        if hist.spot_id.duplicated().any() or hist.label.isna().any():raise ValueError('Histology IDs/labels must be unique and observed')
        if not hist.reviewed.all() or not set(a.obs_names)<=set(hist.spot_id) or not {'section_id','unit_id'}<=set(a.obs) or 'spatial' not in a.obsm:raise ValueError('Actual section coordinates and reviewed histology required')
        assignments=[];checks=[];parameters=[];stability=[]
        if not 0<=p['lambda']<=1:raise ValueError('Spatial weight must be in [0,1]')
        for section in a.obs.section_id.unique():
            v=a[a.obs.section_id==section].copy();x=dense(v.X);xy=np.asarray(v.obsm['spatial']);n=v.n_obs
            if not np.isfinite(x).all() or not np.isfinite(xy).all() or len(np.unique(xy,axis=0))!=n:raise ValueError('Nonfinite expression or duplicate/missing spatial coordinates')
            if n<=max(p['k_geom'],p['n_pcs']) or v.obs.unit_id.nunique()!=1:raise ValueError('Section geometry/independent unit invalid')
            nn=spatial.cKDTree(xy).query(xy,k=p['k_geom']+1)[1][:,1:];neighbor=x[nn].mean(axis=1);aug=np.hstack([np.sqrt(1-p['lambda'])*StandardScaler().fit_transform(x),np.sqrt(p['lambda'])*StandardScaler().fit_transform(neighbor)])
            emb=PCA(n_components=min(p['n_pcs'],n-1,aug.shape[1]),random_state=p['seed']).fit_transform(aug)
            if type(p['resolution']) is not int or p['resolution']<2:raise ValueError('Native spatial kmeans resolution is explicit integer number of domains')
            labels=KMeans(n_clusters=p['resolution'],n_init=30,random_state=p['seed']).fit_predict(emb);truth=hist.set_index('spot_id').loc[v.obs_names].label
            for iteration in range(p['bootstraps']):
                rng=np.random.default_rng(p['seed']+iteration);genes=rng.choice(x.shape[1],max(2,int(.8*x.shape[1])),replace=False);ix=np.concatenate([genes,genes+x.shape[1]]);part=PCA(n_components=min(p['n_pcs'],n-1,len(ix)),random_state=p['seed']).fit_transform(aug[:,ix]);other=KMeans(n_clusters=p['resolution'],n_init=20,random_state=p['seed']).fit_predict(part);stability.append((section,iteration,adjusted_rand_score(labels,other)))
            assignments.extend((spot,section,v.obs.unit_id.iloc[0],int(label)) for spot,label in zip(v.obs_names,labels));checks.append((section,adjusted_rand_score(truth,labels),n));parameters.append((section,p['lambda'],p['k_geom'],emb.shape[1],p['resolution']))
        A=pd.DataFrame(assignments,columns=['spot_id','section_id','unit_id','domain']);B=pd.DataFrame(parameters,columns=['section_id','neighbor_weight','neighbors','n_pcs','domains']);C=pd.DataFrame(checks,columns=['section_id','histology_ARI','spots']);D=pd.DataFrame(stability,columns=['section_id','iteration','conditional_feature_resample_ARI']);metrics['sections']=len(checks);metrics['domains_total']=A.groupby('section_id').domain.nunique().sum()
    elif key=='repertoire_clonotypes':
        import scirpy as ir
        md=df('cell_metadata',['cell_id','unit_id','sample_id']);a=ir.io.read_airr(I['airr']);
        if md.cell_id.duplicated().any() or set(md.cell_id)!=set(a.obs_names):raise ValueError('Exact AIRR/barcode crosswalk required')
        if md[['unit_id','sample_id']].isna().any().any():raise ValueError('Missing AIRR sample/donor identity')
        a.obs=a.obs.join(md.set_index('cell_id'),how='left');pieces=[]
        for unit in sorted(a.obs.unit_id.unique()):
            v=a[a.obs.unit_id==unit].copy();ir.pp.index_chains(v);ir.tl.chain_qc(v);ir.pp.ir_dist(v,sequence='nt',metric='identity');ir.tl.define_clonotypes(v,receptor_arms=p['receptor_arms'],dual_ir=p['dual_ir'],within_group='receptor_type');v.obs['donor_clone']=v.obs.clone_id.map(lambda c:None if __import__('pandas').isna(c) else __import__('json').dumps([str(unit),str(c)],ensure_ascii=False));pieces.append(v.obs)
        obs=pd.concat(pieces);A=obs[['unit_id','sample_id','clone_id','donor_clone']].reset_index(names='cell_id');B=obs.filter(items=['unit_id','receptor_type','receptor_subtype','chain_pairing']).reset_index(names='cell_id');C=md;D=pd.DataFrame({'parameter':['sequence','metric','receptor_arms','dual_ir','clone_scope'],'value':['nt','identity',p['receptor_arms'],p['dual_ir'],'within_independent_unit']});metrics={'cells':len(A),'donor_specific_clones':A.donor_clone.nunique(),'independent_units':A.unit_id.nunique()}
    elif key in {'hic_compartments','hic_loops_tads'}:
        import cooler,cooltools
        c=cooler.Cooler(I['cooler'])
        if c.binsize!=p['resolution']:raise ValueError('Cooler bin resolution differs from selected design')
        bins=c.bins()[:]
        if 'weight' not in bins or np.isfinite(bins.weight).sum()<10:raise ValueError('Require actually balanced contact map and mask')
        view=pd.DataFrame({'chrom':c.chromnames,'start':0,'end':list(c.chromsizes),'name':c.chromnames})
        expected=cooltools.expected_cis(c,view_df=view,nproc=1)
        if key=='hic_compartments':
            phase=df('phasing_track',['chrom','start','end','value']);vals,vectors=cooltools.eigs_cis(c,phasing_track=phase[['chrom','start','end','value']],view_df=view,n_eigs=p['n_eigs']);A=vectors;B=vectors[['chrom','start','end','E1']].copy();B['compartment']=np.where(B.E1.notna(),np.where(B.E1>=0,'A','B'),'MASKED');ref=df('reference_compartments',['chrom','start','end','compartment']);B=B.merge(ref,on=['chrom','start','end'],how='left',suffixes=('','_reference'),validate='one_to_one');B['switch']=pd.Series([None]*len(B),dtype='boolean');assessed=B.compartment.ne('MASKED')&B.compartment_reference.isin(['A','B']);B.loc[assessed,'switch']=B.loc[assessed,'compartment'].ne(B.loc[assessed,'compartment_reference']);B['switch_assessed']=assessed;C=phase;D=vals.reset_index();metrics={'valid_bins':int(np.isfinite(vectors.E1).sum()),'chromosomes':len(view),'eigenvectors':p['n_eigs']}
        else:
            insulation=cooltools.insulation(c,window_bp=p['windows'],verbose=False);dots=cooltools.dots(c,expected=expected,view_df=view,max_loci_separation=p['max_loci_separation'],lambda_bin_fdr=p['fdr'],nproc=1);A=dots;B=insulation;C=expected;D=bins[['chrom','start','end','weight']];metrics={'dots':len(dots),'bins':len(insulation),'expected_rows':len(expected)}
    else:raise ValueError('No specialist implementation '+key)
    mapping={}
    for role,obj in zip(job['required_roles'],[A,B,C,D]):
        if not isinstance(obj,pd.DataFrame) or not len(obj.columns):raise ValueError('Missing specialist output schema')
        name=role+'.tsv';obj.to_csv(out/name,sep='\t',index=False,na_rep='NA');mapping[role]=name
    write(out/'diagnostics.private.json',{'fit_completed':True,'metrics':{k:float(v) for k,v in metrics.items()},'method':p['implementation'],
      'scope':'conditional_observational_not_causal','scientific_acceptance':'NOT_ESTABLISHED'})
    return mapping
