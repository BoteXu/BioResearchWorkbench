"""Real PASTE alignment and section-wise Squidpy statistics; no synthetic geometry."""
from runtime import write

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate
    validate(mode,p,verify_versions=True)
    import anndata as ad,numpy as np,pandas as pd
    from scipy import sparse
    np.random.seed(p['seed']);outputs=[];diag={'mode':mode,'software_versions':p['software_versions'],'scientific_acceptance':'NOT_ESTABLISHED'}
    def emit(df,name,role):
        fn=out/(name+'.tsv');df.to_csv(fn,sep='\t',index=True);outputs.append((fn,role))
    def checked(role):
        a=ad.read_h5ad(inputs[role]);keys=[p['unit_key'],p['section_key']]
        if not a.obs_names.is_unique or not a.var_names.is_unique or not set(keys)<=set(a.obs) or a.obs[keys].isna().any().any():raise ValueError('Unique actual spot/feature axes and full unit/section annotation required')
        c=a.obsm[p['spatial_key']]
        if c.shape!=(a.n_obs,2) or not np.isfinite(c).all() or not p['coordinate_unit']:raise ValueError('Actual two-dimensional physical coordinates and unit required; not UMAP or inferred positions')
        x=a.layers[p['expression_layer']];values=x.data if sparse.issparse(x) else np.asarray(x)
        if not np.isfinite(values).all() or (values<0).any():raise ValueError('Actual nonnegative observed expression required')
        a.X=x.copy();return a
    if mode=='paste_pairwise':
        import paste as pst,ot
        a=checked('slice_a');b=checked('slice_b')
        if a.obs[p['section_key']].nunique()!=1 or b.obs[p['section_key']].nunique()!=1 or a.obs[p['section_key']].iloc[0]==b.obs[p['section_key']].iloc[0]:raise ValueError('Each input must be one distinct actual section')
        if not a.var_names.equals(b.var_names) or set(a.obs_names)&set(b.obs_names):raise ValueError('Prespecified exact common feature order and globally unique spot identities required')
        if a.n_obs*b.n_obs>p['maximum_coupling_entries']:raise ValueError('Pairwise dense coupling exceeds the reviewed server task budget')
        wa=a.obs[p['weight_key']].to_numpy(float);wb=b.obs[p['weight_key']].to_numpy(float)
        for w in [wa,wb]:
            if not np.isfinite(w).all() or (w<=0).any() or not np.isclose(w.sum(),1,atol=1e-10):raise ValueError('Explicit positive normalized observed spot masses required; no hidden weighting change')
        # Store the author's required coordinate slot explicitly in analysis copies.
        a.obsm['spatial']=a.obsm[p['spatial_key']].copy();b.obsm['spatial']=b.obsm[p['spatial_key']].copy()
        pi,objective=pst.pairwise_align(a,b,alpha=p['alpha'],dissimilarity=p['dissimilarity'],a_distribution=wa,b_distribution=wb,norm=p['normalize_distances'],numItermax=p['max_iterations'],backend=ot.backend.NumpyBackend(),use_gpu=False,return_obj=True,verbose=True)
        pi=np.asarray(pi);err=max(float(abs(pi.sum(1)-wa).max()),float(abs(pi.sum(0)-wb).max()))
        if pi.shape!=(a.n_obs,b.n_obs) or not np.isfinite(pi).all() or (pi<0).any() or err>p['marginal_tolerance'] or not np.isfinite(objective):raise ValueError('Native coupling fails shape, mass, objective or numerical QC')
        np.save(out/'paste_coupling.npy',pi);outputs.append((out/'paste_coupling.npy','spatial_coupling'));emit(pd.DataFrame({'mass':wa},index=a.obs_names),'paste_source_spots','coupling_source_identity');emit(pd.DataFrame({'mass':wb},index=b.obs_names),'paste_target_spots','coupling_target_identity')
        if p['align_coordinates']:
            aligned=pst.stack_slices_pairwise([a,b],[pi])
            for i,z in enumerate(aligned):
                coords=z.obsm['spatial']
                if not z.obs_names.equals([a,b][i].obs_names) or not np.isfinite(coords).all():raise ValueError('Aligned output changed spot identity or has nonfinite coordinates')
                emit(pd.DataFrame(coords,index=z.obs_names,columns=['aligned_x','aligned_y']),'paste_aligned_'+str(i),'aligned_coordinates')
        diag.update(n_source_spots=a.n_obs,n_target_spots=b.n_obs,maximum_marginal_error=err,objective=float(objective),coordinate_unit=p['coordinate_unit'],kl_internal_pseudocount=.01 if p['dissimilarity']=='kl' else None,interpretation='Full-mass PASTE pairwise alignment; not PASTE2 partial overlap, observed cell lineage or measured cross-section pairing. Normalized distances, if enabled, are dimensionless')
    elif mode=='squidpy_section_statistics':
        import squidpy as sq
        a=checked('object');key=p['celltype_key'];sections=[]
        if key not in a.obs or a.obs[key].isna().any():raise ValueError('Actual reviewed celltype annotations required')
        genes=p['genes']
        if not isinstance(genes,list) or not genes or len(set(genes))!=len(genes) or not set(genes)<=set(a.var_names):raise ValueError('Prespecified unique observed feature universe required for spatial multiplicity control')
        for i,(section,positions) in enumerate(a.obs.groupby(p['section_key'],observed=True,sort=False).indices.items()):
            z=a[positions].copy()
            if z.obs[p['unit_key']].nunique()!=1 or not 3<=z.n_obs<=p['maximum_spots_per_section']:raise ValueError('Each actual section must have one unit and satisfy the reviewed server task budget')
            if not set(z.obs[key])<=set(p['celltype_order']):raise ValueError('Prespecified celltype universe does not cover observed identities')
            categories=[c for c in p['celltype_order'] if c in set(z.obs[key])];z.obs[key]=pd.Categorical(z.obs[key],categories=categories)
            # Native radius graph, computed within section only. No edge can cross
            # different tissue sections or independent subjects.
            sq.gr.spatial_neighbors_radius(z,radius=p['radius'],spatial_key=p['spatial_key'],set_diag=False)
            graph=z.obsp['spatial_connectivities'];degrees=np.asarray(graph.sum(1)).ravel();islands=int((degrees==0).sum())
            if graph.nnz==0 or islands/z.n_obs>p['maximum_island_fraction']:raise ValueError('Spatial neighborhood support fails the prespecified radius/island criterion')
            values=z[:,genes].layers[p['expression_layer']];dense=values.toarray() if sparse.issparse(values) else np.asarray(values)
            if (np.var(dense,axis=0)==0).any():raise ValueError('A selected gene is constant within section; review the tested feature universe explicitly')
            moran=sq.gr.spatial_autocorr(z,genes=genes,mode='moran',layer=p['expression_layer'],use_raw=False,n_perms=p['n_perms'],two_tailed=p['two_tailed'],corr_method='fdr_bh',rng=p['seed'],n_jobs=p['threads'],copy=True,show_progress_bar=False)
            if set(moran.index)!=set(genes):raise ValueError('Native spatial test changed the prespecified gene universe')
            emit(moran,'squidpy_section_'+str(i)+'_moran','spatial_autocorrelation')
            sq.gr.nhood_enrichment(z,cluster_key=key,n_perms=p['n_perms'],rng=p['seed'],n_jobs=p['threads'],normalization=p['nhood_normalization'],handle_nan='keep',copy=False,show_progress_bar=False)
            nhood=z.uns[key+'_nhood_enrichment'];enrich=np.asarray(nhood['zscore']);counts=np.asarray(nhood['count'])
            emit(pd.DataFrame(enrich,index=categories,columns=categories),'squidpy_section_'+str(i)+'_nhood_z','neighborhood_enrichment');emit(pd.DataFrame(counts,index=categories,columns=categories),'squidpy_section_'+str(i)+'_nhood_count','neighborhood_counts')
            occ,interval=sq.gr.co_occurrence(z,cluster_key=key,spatial_key=p['spatial_key'],interval=np.asarray(p['distance_intervals'],dtype=float),copy=True)
            np.savez_compressed(out/('squidpy_cooccurrence_'+str(i)+'.npz'),occ=occ,interval=interval,celltypes=np.asarray(categories,dtype=str));outputs.append((out/('squidpy_cooccurrence_'+str(i)+'.npz'),'cooccurrence'))
            sparse.save_npz(out/('squidpy_graph_'+str(i)+'.npz'),sparse.csr_matrix(graph));outputs.append((out/('squidpy_graph_'+str(i)+'.npz'),'spatial_graph'))
            sections.append({'section_index':i,'section_id':str(section),'unit_id':str(z.obs[p['unit_key']].iloc[0]),'n_spots':z.n_obs,'n_islands':islands,'undefined_neighborhood_zscores':int((~np.isfinite(enrich)).sum()),'undefined_cooccurrence_values':int((~np.isfinite(occ)).sum()),'celltype_order':categories})
        write(out/'squidpy_section_qc.json',sections);outputs.append((out/'squidpy_section_qc.json','section_diagnostics'));diag.update(n_sections=len(sections),coordinate_unit=p['coordinate_unit'],radius=p['radius'],permutation_method_version='Squidpy >=1.8.4 independent RNG streams; older seeds do not reproduce this stream',undefined_values='Preserved as undefined, never filled as absence or no enrichment',interpretation='Within-section spatial association with explicit distances and permutations; not independent-cell disease inference or proof of ligand-receptor binding')
    else:raise ValueError('Unsupported fixed native spatial statistics route')
    write(out/'native_diagnostics.json',diag);outputs.append((out/'native_diagnostics.json','diagnostics'));write(out/'native_versions.json',p['software_versions']);outputs.append((out/'native_versions.json','backend_versions'));return outputs
