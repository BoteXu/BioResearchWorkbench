"""Explicit native alternatives. Scientific libraries load only inside the server dispatcher."""
from pathlib import Path
from runtime import write
from method_contract71 import strict_bool

def analyze(job,out):
    import numpy as np,pandas as pd
    from scipy import stats,spatial,optimize
    from scipy.special import betaln,gammaln,expit
    from statsmodels.stats.multitest import multipletests
    import statsmodels.api as sm
    import networkx as nx
    p=job['parameters'];I=job['inputs'];key=job['analysis_id'];rng=np.random.default_rng(p['seed']);metrics={}
    def table(role,cols=()):
        x=pd.read_csv(I[role],sep='\t',dtype={k:str for k in ('sample_id','unit_id','cell_id','spot_id','feature_id','variant_id','source','target','node_id','clone_id')})
        if x.empty or x.columns.duplicated().any() or not set(cols)<=set(x):raise ValueError('Missing/empty columns in '+role)
        for name in set(x)&{'foreground','ambiguous','unique_to_variant','is_decoy','variant_space','reviewed_normal','motif_supported','offset_validated','positive'}:x[name]=x[name].map(strict_bool)
        return x
    def matrix(role='matrix'):
        x=pd.read_csv(I[role],sep='\t',index_col=0,dtype=str);x=x.apply(pd.to_numeric,errors='raise')
        if x.empty or x.index.duplicated().any() or x.columns.duplicated().any() or not np.isfinite(x.to_numpy(float)).all():raise ValueError('Invalid finite unique matrix '+role)
        return x
    def samples(repeated=False):
        s=table('samples',['sample_id','unit_id']).set_index('sample_id',drop=False);repeated=repeated or p.get('contrast_method')=='paired_t'
        for name in p.get('covariates',[]):
            kind=job['context'].get('variable_types',{}).get(name)
            if kind=='categorical':s[name]=s[name].astype('category')
            elif kind=='continuous':s[name]=pd.to_numeric(s[name],errors='raise')
            else:raise ValueError('Covariate type must be explicitly reviewed: '+name)
        if s.index.duplicated().any() or s.unit_id.isna().any() or (not repeated and s.unit_id.duplicated().any()):raise ValueError('Independent unit mapping invalid; aggregate upstream or select repeated-unit model')
        return s
    def align(x,s):
        if set(x.columns)!=set(s.index):raise ValueError('Exact sample denominator mismatch')
        return x.loc[:,s.index]
    def groups(s):
        if set(s.group)!={p['control'],p['treatment']}:raise ValueError('Explicit two-group population required')
        a=s.group.eq(p['control']).to_numpy();b=s.group.eq(p['treatment']).to_numpy()
        if min(a.sum(),b.sum())<p.get('min_units',3):raise ValueError('Too few independent units per group')
        return a,b
    def bh(df,column='p'):
        good=df[column].notna();df['q']=np.nan
        if good.any():df.loc[good,'q']=multipletests(df.loc[good,column],method='fdr_bh')[1]
        return df
    def welch(x,s):
        from contrast71 import contrast_matrix
        return contrast_matrix(x,s,p)
    def frame(rows,cols):return pd.DataFrame(rows,columns=cols)
    def graph():
        e=table('edges',['source','target','weight']);nodes=table('nodes',['node_id']);g=nx.Graph();g.add_nodes_from(nodes.node_id)
        if not set(e.source)|set(e.target)<=set(nodes.node_id):raise ValueError('Network universe omits nodes')
        if nodes.node_id.duplicated().any() or e.apply(lambda r:tuple(sorted((r.source,r.target))),axis=1).duplicated().any() or (e.source==e.target).any() or (~np.isfinite(e.weight)).any() or (e.weight<=0).any():raise ValueError('Resolve duplicate/self/invalid weighted edges upstream')
        g.add_weighted_edges_from(e[['source','target','weight']].itertuples(index=False,name=None));return e,nodes,g
    def network_null(g,n):
        rows=[]
        for i in range(n):
            h=g.copy()
            try:nx.double_edge_swap(h,nswap=max(1,len(h.edges)*2),max_tries=max(100,len(h.edges)*30),seed=p['seed']+i)
            except (nx.NetworkXAlgorithmError,nx.NetworkXError):raise ValueError('Degree-preserving null failed; lower graph scope or use an explicit different null')
            rows.append({'iteration':i,'transitivity':nx.transitivity(h),'components':nx.number_connected_components(h),'edges':h.number_of_edges()})
        return pd.DataFrame(rows)
    if key=='differential_coexpression':
        x=matrix();s=samples();x=align(x,s);a,b=groups(s);edges=table('edge_universe',['source','target']);rows=[];boots=[]
        canonical=edges.apply(lambda z:tuple(sorted((z.source,z.target))),axis=1)
        if canonical.duplicated().any() or (edges.source==edges.target).any():raise ValueError('Duplicate/self differential-correlation hypothesis')
        if not 0<p['bootstrap_fraction']<=1:raise ValueError('Correlation resampling fraction outside (0,1]')
        for e in edges.itertuples():
            if e.source not in x.index or e.target not in x.index:raise ValueError('Edge universe outside selected genes')
            u=x.loc[e.source].to_numpy();v=x.loc[e.target].to_numpy()
            if min(np.std(u[a]),np.std(v[a]),np.std(u[b]),np.std(v[b]))==0:raise ValueError('Constant group-specific gene requires an explicit excluded-edge record upstream')
            corr=stats.pearsonr if p['correlation_method']=='pearson' else stats.spearmanr
            r1=corr(u[a],v[a]).statistic;r2=corr(u[b],v[b]).statistic;delta=r2-r1;ds=[]
            na=max(4,int(a.sum()*p['bootstrap_fraction']));nb=max(4,int(b.sum()*p['bootstrap_fraction']))
            if min(a.sum(),b.sum())<=3:raise ValueError('At least four independent units per group required')
            for it in range(p['bootstraps']):
                ai=rng.choice(np.flatnonzero(a),na);bi=rng.choice(np.flatnonzero(b),nb);rr=corr(u[bi],v[bi]).statistic-corr(u[ai],v[ai]).statistic
                if np.isfinite(rr):ds.append(rr)
            if len(ds)<.9*p['bootstraps']:raise ValueError('Excessive degenerate correlation resamples')
            if p['correlation_method']=='pearson':
                if abs(r1)>=1 or abs(r2)>=1:raise ValueError('Perfect correlation makes the Fisher-Z approximation singular')
                z=(np.arctanh(r2)-np.arctanh(r1))/np.sqrt(1/(a.sum()-3)+1/(b.sum()-3));pv=2*stats.norm.sf(abs(z));scope='Fisher_Z_independent_bivariate_normal_approximation'
            else:pv=(1+sum(abs(val-delta)>=abs(delta) for val in ds))/(1+len(ds));scope='centered_donor_bootstrap_approximation'
            lo,hi=np.quantile(ds,[.025,.975]);rows.append((e.source,e.target,r1,r2,delta,pv,lo,hi,scope));boots.append((e.source,e.target,len(ds),p['bootstraps']-len(ds),np.mean(np.sign(ds)==np.sign(delta))))
        A=bh(frame(rows,['source','target','r_control','r_treatment','delta_r','p','ci_lower','ci_upper','p_value_scope']));B=A[['source','target','r_control','r_treatment']];C=A[['source','target','ci_lower','ci_upper']];D=frame(boots,['source','target','valid_bootstraps','failed_bootstraps','sign_stability']);metrics={'tested_edges':len(A),'independent_units':len(s)}
    elif key in {'peak_gene_links','enhancer_grn'}:
        rna=matrix('rna_matrix');atac=matrix('atac_matrix');s=samples();rna=align(rna,s);atac=align(atac,s);links=table('candidate_links',['peak','gene','distance_bp']);rows=[];predictions=[];stability=[]
        if key=='peak_gene_links':
            all_links=links.copy();all_links['included']=all_links.distance_bp.abs().le(p['max_distance_bp']);links=all_links[all_links.included].copy()
            if links.empty:raise ValueError('No cis candidate satisfies the declared distance window')
            cov=pd.get_dummies(s[p['covariates']],drop_first=True,dtype=float) if p['covariates'] else pd.DataFrame(index=s.index)
            d=sm.add_constant(cov,has_constant='add').to_numpy(float)
            if len(s)<p['min_units'] or np.linalg.matrix_rank(d)!=d.shape[1] or len(s)-d.shape[1]<=3:raise ValueError('Partial-correlation design rank/df invalid')
            for e in links.itertuples():
                u=sm.OLS(atac.loc[e.peak].to_numpy(),d).fit().resid;v=sm.OLS(rna.loc[e.gene].to_numpy(),d).fit().resid;rr=stats.pearsonr(u,v).statistic;df=len(s)-d.shape[1]-1
                if not np.isfinite(rr) or abs(rr)>=1:raise ValueError('Peak/gene partial correlation is constant or perfectly singular')
                ts=rr*np.sqrt(df/(1-rr*rr));bs=[]
                for _ in range(p['bootstraps']):
                    ix=rng.choice(len(s),len(s));du=d[ix];uu=sm.OLS(atac.loc[e.peak].to_numpy()[ix],du).fit().resid;vv=sm.OLS(rna.loc[e.gene].to_numpy()[ix],du).fit().resid;z=np.corrcoef(uu,vv)[0,1]
                    if np.isfinite(z):bs.append(z)
                if len(bs)<.9*p['bootstraps']:raise ValueError('Degenerate donor resampling')
                lo,hi=np.quantile(bs,[.025,.975]);rows.append((e.peak,e.gene,e.distance_bp,rr,2*stats.t.sf(abs(ts),df),lo,hi));stability.append((e.peak,e.gene,len(bs),np.mean(np.sign(bs)==np.sign(rr))))
            A=bh(frame(rows,['peak','gene','distance_bp','partial_r','p','ci_lower','ci_upper']));B=all_links;C=pd.DataFrame(d,index=s.index).reset_index();D=frame(stability,['peak','gene','valid_resamples','sign_stability'])
        else:
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
            from sklearn.linear_model import Ridge
            links=table('candidate_links',['peak','gene','tf','motif_supported','distance_bp'])
            if not links.motif_supported.all():raise ValueError('Enhancer GRN candidates require selected motif support')
            test=s.unit_id.isin(p['holdout_units']).to_numpy();train=~test
            if min(test.sum(),train.sum())<3 or not p['holdout_units']:raise ValueError('Explicit independent training and holdout units required')
            if (links.tf==links.gene).any():raise ValueError('Target gene cannot predict itself through a TF feature')
            for gene,z in links.groupby('gene',sort=False):
                features=sorted(set(z.peak));tfs=sorted(set(z.tf));xx=np.vstack([atac.loc[features].to_numpy(),rna.loc[tfs].to_numpy()]).T;yy=rna.loc[gene].to_numpy();model=make_pipeline(StandardScaler(),Ridge(alpha=p['alpha']));model.fit(xx[train],yy[train]);pred=model.predict(xx[test]);co=model[-1].coef_/model[0].scale_;labels=features+tfs
                for typ,name,c in zip(['peak']*len(features)+['tf']*len(tfs),labels,co):rows.append((gene,typ,name,c))
                for unit,truth,estimate in zip(s.unit_id[test],yy[test],pred):predictions.append((gene,unit,truth,estimate))
                boot=[]
                for _ in range(p['bootstraps']):
                    ix=rng.choice(np.flatnonzero(train),train.sum());m=make_pipeline(StandardScaler(),Ridge(alpha=p['alpha']));m.fit(xx[ix],yy[ix]);boot.append(m[-1].coef_/m[0].scale_)
                boot=np.asarray(boot)
                for j,name in enumerate(labels):lo,hi=np.quantile(boot[:,j],[.025,.975]);stability.append((gene,name,lo,hi,np.mean(np.sign(boot[:,j])==np.sign(co[j]))))
            A=frame(rows,['gene','predictor_type','predictor','coefficient_original_predictor_scale']);B=frame(predictions,['gene','unit_id','observed','predicted']);C=links;D=frame(stability,['gene','predictor','bootstrap_lower','bootstrap_upper','sign_stability']);B.to_csv(out/'heldout_predictions.tsv',sep='\t',index=False);D.to_csv(out/'coefficient_stability.tsv',sep='\t',index=False);metrics['holdout_rmse']=float(((B.observed-B.predicted)**2).mean()**.5);metrics['train_units']=int(train.sum());metrics['holdout_units']=int(test.sum())
        metrics.update(candidate_links=len(links),independent_units=len(s),fitted_rows=len(A))
    elif key=='junction_events':
        c=table('junction_counts',['event_id','sample_id','included','total']);s=samples();a,b=groups(s);definitions=table('event_definitions',['event_id','cluster_id','coordinate','event_type']);rows=[];diag=[]
        if definitions.event_id.duplicated().any() or set(definitions.event_id)!=set(c.event_id):raise ValueError('Complete unique event definitions must match every junction test')
        if c[['event_id','sample_id']].duplicated().any() or (c.included<0).any() or (c.total<c.included).any() or (c[['included','total']]%1!=0).any().any():raise ValueError('Invalid integer junction count numerator/denominator')
        for event,z in c.groupby('event_id',sort=False):
            z=z.set_index('sample_id').reindex(s.index)
            if z.isna().any().any() or (z.total<p['min_reads']).any():raise ValueError('Missing or below-threshold junction coverage; retain full failed event set upstream')
            n=z.total.to_numpy();k=z.included.to_numpy();group=b.astype(float);d=np.column_stack([np.ones(len(s)),group])
            def nll(theta):
                mu=expit(d@theta[:2]);rho=p['dispersion_floor']+(1-p['dispersion_floor'])*expit(theta[2]);phi=1/rho-1;aa=mu*phi;bb=(1-mu)*phi
                return -np.sum(gammaln(n+1)-gammaln(k+1)-gammaln(n-k+1)+betaln(k+aa,n-k+bb)-betaln(aa,bb))
            fit=optimize.minimize(nll,[0,0,-3],method='BFGS');null=optimize.minimize(lambda t:nll([t[0],0,t[1]]),[0,-3],method='BFGS')
            if not fit.success or not null.success:raise ValueError('Beta-binomial event optimization did not converge')
            from statsmodels.tools.numdiff import approx_hess
            hessian=approx_hess(fit.x,nll)
            if not np.isfinite(hessian).all() or np.linalg.eigvalsh(hessian).min()<=1e-8 or np.linalg.norm(fit.jac)>p['max_gradient_norm']:raise ValueError('Junction model Hessian/gradient diagnostics fail')
            fit.hess_inv=np.linalg.inv(hessian)
            lr=max(0,2*(null.fun-fit.fun));m0=expit(fit.x[0]);m1=expit(fit.x[0]+fit.x[1]);gradient=np.array([m1*(1-m1)-m0*(1-m0),m1*(1-m1),0]);se=np.sqrt(max(0,float(gradient @ fit.hess_inv @ gradient)));delta=m1-m0
            rows.append((event,delta,stats.chi2.sf(lr,1),fit.x[1],se,max(-1,delta-1.96*se),min(1,delta+1.96*se)));diag.append((event,n.sum(),n.min(),fit.fun,np.linalg.norm(fit.jac)))
        A=bh(frame(rows,['event_id','delta_usage','p','log_odds','se','ci_lower','ci_upper']));B=frame(diag,['event_id','total_reads','minimum_unit_reads','negative_loglikelihood','gradient_norm']);C=definitions;D=c.assign(usage=c.included/c.total);metrics={'events':len(A),'units':len(s)}
    elif key=='leading_edge':
        e=table('enrichment',['term','q','NES']);m=table('leading_members',['term','feature_id'])
        if e.term.duplicated().any() or m[['term','feature_id']].duplicated().any() or not set(m.term)<=set(e.term):raise ValueError('Leading-edge terms/members must map uniquely to the complete enrichment denominator')
        e=e[e.q<p['fdr']];sets={term:set(z.feature_id) for term,z in m.groupby('term') if term in set(e.term)};g=nx.Graph();g.add_nodes_from(sets);rows=[]
        for i,a in enumerate(sets):
            for b in list(sets)[i+1:]:
                j=len(sets[a]&sets[b])/len(sets[a]|sets[b]) if sets[a]|sets[b] else 0;rows.append((a,b,j,len(sets[a]&sets[b])))
                if j>=p['jaccard_threshold']:g.add_edge(a,b)
        reps=[]
        for i,component in enumerate(nx.connected_components(g)):
            best=e[e.term.isin(component)].sort_values(['q','term']).iloc[0].term
            for term in sorted(component):reps.append((i,term,best,term==best))
        A=m[m.term.isin(sets)];B=frame(rows,['source','target','Jaccard','overlap_n']);C=frame(reps,['component','term','representative','is_representative']);D=table('enrichment');metrics={'selected_terms':len(sets),'leading_members':len(A),'components':len(set(C.component))}
    elif key in {'network_diffusion','physical_ppi','ppi_modules'}:
        e,nodes,g=graph()
        if key=='physical_ppi':
            if not {'evidence_type','source_database','source_record'}<=set(e):raise ValueError('Physical interactions require traceable evidence, not a generic association score')
            keep=e.evidence_type.isin(p['allowed_evidence'])&e.weight.ge(p['min_score']);accepted=e[keep];h=nx.Graph();h.add_nodes_from(g.nodes);h.add_weighted_edges_from(accepted[['source','target','weight']].itertuples(index=False,name=None));A=accepted;B=e.assign(included=keep);C=nodes.assign(degree=nodes.node_id.map(dict(h.degree())));D=network_null(h,p['permutations']);g=h
        elif key=='network_diffusion':
            seeds=table('seeds',['node_id','weight']);hold=table('holdout',['node_id','positive']);
            if seeds.node_id.duplicated().any() or hold.node_id.duplicated().any() or (seeds.weight<0).any() or seeds.weight.sum()<=0:raise ValueError('Invalid/duplicate diffusion seed weights or holdout identities')
            if set(seeds.node_id)&set(hold.node_id) or not set(seeds.node_id)|set(hold.node_id)<=set(g):raise ValueError('Holdout leakage/network universe mismatch')
            pers={n:0. for n in g};pers.update(dict(zip(seeds.node_id,seeds.weight)));score=nx.pagerank(g,alpha=p['alpha'],personalization=pers,weight='weight');null=[]
            for it in range(p['permutations']):
                perm=rng.permutation(list(g));sp=dict(zip(perm,list(pers.values())));rr=nx.pagerank(g,alpha=p['alpha'],personalization=sp,weight='weight')
                for n in hold.node_id:null.append((it,n,rr[n]))
            A=pd.DataFrame({'node_id':list(score),'score':list(score.values())}).sort_values('score',ascending=False);B=seeds;C=frame(null,['iteration','node_id','null_score']);D=hold.assign(predicted=hold.node_id.map(score))
        else:
            com=nx.community.louvain_communities(g,weight='weight',resolution=p['resolution'],seed=p['seed']);membership={n:i for i,c in enumerate(com) for n in c};bet=nx.betweenness_centrality(g,weight=None);A=nodes.assign(module=nodes.node_id.map(membership));B=nodes.assign(degree=nodes.node_id.map(dict(g.degree())),betweenness=nodes.node_id.map(bet));C=network_null(g,p['permutations']);boot=[]
            for it in range(p['bootstraps']):
                h=nx.Graph();h.add_nodes_from(g);chosen=rng.choice(len(e),len(e));sampled=e.iloc[chosen].groupby(['source','target'],as_index=False).weight.sum();h.add_weighted_edges_from(sampled[['source','target','weight']].itertuples(index=False,name=None));cc=nx.community.louvain_communities(h,resolution=p['resolution'],seed=p['seed']+it);mm={n:i for i,c in enumerate(cc) for n in c}
                for u,v in g.edges:boot.append((it,u,v,int(mm[u]==mm[v])))
            D=frame(boot,['iteration','source','target','coassigned'])
        metrics={'nodes':g.number_of_nodes(),'edges':g.number_of_edges(),'isolates':len(list(nx.isolates(g)))}
    elif key in {'lr_differential','microbe_pathways','lipid_chain_patterns'}:
        s=samples()
        if key=='lr_differential':
            z=table('donor_lr',['sample_id','source','target','ligand','receptor','score','score_kind'])
            if set(z.score_kind)!={'log1p_ligand_receptor_mean_product'}:raise ValueError('Donor LR contrasts require comparable abundance scores, not per-donor ranks')
            z['feature_id']=z[['source','target','ligand','receptor']].astype(str).apply(lambda r:__import__('json').dumps(r.tolist(),ensure_ascii=False,separators=(',',':')),axis=1)
            if z[['sample_id','feature_id']].duplicated().any():raise ValueError('Duplicate donor LR measurement')
            x=z.pivot(index='feature_id',columns='sample_id',values='score')
            if x.isna().any().any():raise ValueError('Missing LR combinations are not biological zeros')
            if set(z.sample_id)!=set(s.index):raise ValueError('Donor LR sample universe mismatch')
            A=welch(x,s);B=z.groupby('feature_id').sample_id.nunique().rename('donor_support').reset_index();C=z.assign(observed=True);D=x.reset_index()
        elif key=='microbe_pathways':
            x=align(matrix('function_abundance'),s)
            if (x<0).any().any() or p['pseudocount']<=0:raise ValueError('Nonnegative HUMAnN abundance and explicit pseudocount required')
            stratified=x.index.to_series().str.contains('|',regex=False);B=x.loc[stratified].reset_index();x=x.loc[~stratified]
            if B.empty:raise ValueError('HUMAnN stratified output is required for this branch; a collapsed table alone is incomplete')
            if (x.sum(axis=0)<=0).any():raise ValueError('Empty unstratified pathway denominator')
            unclassified=x.index.to_series().str.contains('UNMAPPED|UNINTEGRATED');C=pd.DataFrame({'sample_id':x.columns,'unclassified_fraction':x.loc[unclassified].sum()/x.sum()});functional=x.loc[~unclassified];
            if functional.empty:raise ValueError('No annotated pathways remain in CLR reference')
            log=np.log(functional+p['pseudocount']);clr=log-log.mean(axis=0);A=welch(clr,s);D=clr.reset_index()
        else:
            x=align(matrix(),s);an=table('lipid_annotations',['feature_id','class','carbons','double_bonds','ambiguous']);
            if an.ambiguous.any() or an.feature_id.duplicated().any() or not set(x.index)<=set(an.feature_id):raise ValueError('Lipid identities/chain annotation unresolved')
            base=welch(x,s).merge(an,on='feature_id');rows=[];unit_slopes=[]
            for cls,z in base.groupby('class'):
                if len(z)<p['min_class_size']:continue
                d=sm.add_constant(z[['carbons','double_bonds']]).to_numpy();
                if np.linalg.matrix_rank(d)<d.shape[1]:raise ValueError('Chain length/unsaturation are confounded within a lipid class')
                coefficients=np.linalg.lstsq(d,x.loc[z.feature_id].to_numpy(),rcond=None)[0]
                for j,term in enumerate(['carbons','double_bonds'],start=1):
                    for sample,val in zip(s.index,coefficients[j]):unit_slopes.append((str(cls)+'|'+term,sample,float(val)))
            slope=frame(unit_slopes,['feature_id','sample_id','slope']);A=welch(slope.pivot(index='feature_id',columns='sample_id',values='slope'),s);B=an;C=base;D=slope
        metrics={'tested_features':len(A),'independent_units':s.unit_id.nunique(),'selected_samples':len(s)}
    elif key=='motif_enrichment':
        universe=table('peak_universe',['peak_id','foreground','gc','length']);hits=table('motif_hits',['peak_id','motif']);
        all_motifs=table('motif_universe',['motif']);
        if all_motifs.motif.duplicated().any() or not set(hits.motif)<=set(all_motifs.motif):raise ValueError('Motif hit set differs from searched motif universe')
        if universe.peak_id.duplicated().any() or not set(hits.peak_id)<=set(universe.peak_id):raise ValueError('Motif background universe invalid')
        universe['gc_bin']=pd.cut(universe.gc,p['gc_bins'],labels=False,include_lowest=True);universe['length_bin']=pd.cut(universe.length,p['length_bins'],labels=False,include_lowest=True)
        if universe[['gc_bin','length_bin']].isna().any().any():raise ValueError('GC/length strata omit peaks')
        chosen=[]
        for _,z in universe.groupby(['gc_bin','length_bin'],observed=True):
            fg=z[z.foreground];bg=z[~z.foreground]
            if len(bg)<len(fg):raise ValueError('Insufficient GC/length matched background')
            chosen.extend(bg.sample(n=len(fg),random_state=p['seed']).peak_id)
        fg=set(universe.peak_id[universe.foreground]);bg=set(chosen);rows=[]
        for motif in all_motifs.motif:
            hh=set(hits.peak_id[hits.motif==motif]);aa=len(fg&hh);bb=len(bg&hh);od,pv=stats.fisher_exact([[aa,len(fg)-aa],[bb,len(bg)-bb]],alternative='greater');rows.append((motif,aa,bb,len(fg),len(bg),pv,(aa+.5)*(len(bg)-bb+.5)/((bb+.5)*(len(fg)-aa+.5))))
        A=bh(frame(rows,['motif','foreground_hits','background_hits','foreground_n','background_n','p','haldane_odds_ratio']));B=universe.assign(selected=universe.peak_id.isin(bg|fg));C=hits;D=B.groupby(['gc_bin','length_bin','foreground'],observed=True).size().rename('n').reset_index();metrics={'foreground':len(fg),'matched_background':len(bg),'motifs':len(A)}
    elif key=='methylation_gene_links':
        m=matrix('methylated');n=matrix('total');s=samples();m=align(m,s);n=align(n,s);rna=align(matrix('rna_matrix'),s);rg=table('regions',['region_id','chromosome','start','end','gene_id']);mp=table('probe_map',['probe_id','chromosome','position']);
        if not m.index.equals(n.index) or ((m<0)|(m>n)).any().any() or (n<p['min_coverage']).any().any():raise ValueError('Methylation read denominator/coverage invalid')
        beta=(m+.5)/(n+1);mval=np.log2(beta/(1-beta));vals=[];mapping=[];assoc=[]
        for r in rg.itertuples():
            probes=mp.probe_id[(mp.chromosome==r.chromosome)&(mp.position.ge(r.start)&mp.position.lt(r.end))];probes=[v for v in probes if v in m.index]
            if len(probes)<p['min_probes']:raise ValueError('Predefined region lacks probe coverage')
            vals.append(pd.Series(mval.loc[probes].mean(),name=r.region_id));mapping.extend((r.region_id,pr,r.gene_id) for pr in probes)
            mv=beta.loc[probes].mean();rv=rna.loc[r.gene_id]
            if p['contrast_method']=='paired_t':
                if set(s.group)!={p['control'],p['treatment']} or s.groupby(['unit_id','group']).size().ne(1).any() or s.groupby('unit_id').group.nunique().ne(2).any():raise ValueError('Methylation/RNA change association needs complete unique unit pairs')
                pair=s.pivot(index='unit_id',columns='group',values='sample_id');control=pair[p['control']];treated=pair[p['treatment']]
                mv=pd.Series(mv.loc[treated].to_numpy()-mv.loc[control].to_numpy(),index=pair.index);rv=pd.Series(rv.loc[treated].to_numpy()-rv.loc[control].to_numpy(),index=pair.index);cov=pd.get_dummies(s.groupby('unit_id')[p['covariates']].first().reindex(pair.index),drop_first=True,dtype=float) if p['covariates'] else pd.DataFrame(index=pair.index)
            else:cov=pd.get_dummies(s[['group']+p['covariates']],drop_first=True,dtype=float)
            d=sm.add_constant(cov,has_constant='add').to_numpy();ur=sm.OLS(stats.rankdata(mv),d).fit().resid;vr=sm.OLS(stats.rankdata(rv),d).fit().resid;rr=stats.pearsonr(ur,vr).statistic;df=len(mv)-d.shape[1]-1;
            if np.linalg.matrix_rank(d)!=d.shape[1] or df<=1 or not np.isfinite(rr) or abs(rr)>=1:raise ValueError('Methylation/RNA partial association is not estimable')
            pv=2*stats.t.sf(abs(rr)*np.sqrt(df/(1-rr*rr)),df);assoc.append((r.region_id,r.gene_id,rr,pv))
        region=pd.DataFrame(vals);A=welch(region,s);B=frame(mapping,['region_id','probe_id','gene_id']);C=bh(frame(assoc,['region_id','gene_id','rho','p']));D=pd.DataFrame({'sample_id':s.sample_id,'minimum_coverage':n.min(axis=0),'median_coverage':n.median(axis=0)});metrics={'predefined_regions':len(rg),'independent_units':s.unit_id.nunique(),'selected_samples':len(s),'probes':len(m)}
    elif key=='proteogenomic_links':
        z=table('psms',['spectrum_id','peptide','score','is_decoy','search_space','variant_space','sample_id']);v=table('peptide_variants',['peptide','variant_id','unique_to_variant','reference_peptide']);
        if z[['sample_id','spectrum_id']].duplicated().any() or not z.is_decoy.isin([True,False]).all():raise ValueError('Require target-decoy competed one-PSM-per-spectrum results')
        if v[['peptide','variant_id']].duplicated().any() or v[['peptide','reference_peptide','variant_id']].isna().any().any() or (v.peptide==v.reference_peptide).any():raise ValueError('Variant-peptide mapping is duplicate, incomplete or identical to its claimed reference peptide')
        parts=[]
        for space,g in z.groupby(['sample_id','search_space','variant_space'],sort=False):
            if not g.is_decoy.any() or g.is_decoy.all():raise ValueError('Each canonical/variant search class needs actual competed target and decoy evidence')
            g=g.sort_values('score',ascending=False).copy();bins=g.groupby('score',sort=True).is_decoy.agg(decoys='sum',total='size').sort_index(ascending=False);bins['targets']=bins.total-bins.decoys;bins['fdr']=np.minimum(1.,(bins.decoys.cumsum()+1)/bins.targets.cumsum().clip(lower=1));bins['q']=np.minimum.accumulate(bins.fdr.to_numpy()[::-1])[::-1];g['q']=g.score.map(bins.q);g['fdr']=g.score.map(bins.fdr);parts.append(g)
        scored=pd.concat(parts);peptide_rows=[]
        if z.groupby(['sample_id','search_space','variant_space','peptide']).is_decoy.nunique().gt(1).any():raise ValueError('A peptide cannot be both target and decoy in the same search class')
        for space,g in z.groupby(['sample_id','search_space','variant_space'],sort=False):
            pep=g.sort_values('score',ascending=False).drop_duplicates('peptide').copy();bins=pep.groupby('score').is_decoy.agg(decoys='sum',total='size').sort_index(ascending=False);fdr=(bins.decoys.cumsum()+1)/(bins.total-bins.decoys).cumsum().clip(lower=1);bins['peptide_q']=np.minimum.accumulate(np.minimum(1.,fdr.to_numpy())[::-1])[::-1];pep['peptide_q']=pep.score.map(bins.peptide_q);peptide_rows.append(pep)
        peptide_table=pd.concat(peptide_rows);peptide_table.to_csv(out/'peptide_level_FDR.tsv',sep='\t',index=False)
        scored=scored.merge(peptide_table[['sample_id','search_space','variant_space','peptide','peptide_q']],on=['sample_id','search_space','variant_space','peptide'],validate='many_to_one')
        accepted=scored[(~scored.is_decoy)&scored.variant_space&(scored.q<=p['fdr'])&(scored.peptide_q<=p['fdr'])];links=accepted.merge(v,on='peptide',validate='many_to_many');unique=v.groupby('peptide').variant_id.nunique();links=links[links.unique_to_variant&links.peptide.isin(unique[unique==1].index)];counts=links.groupby('variant_id').peptide.nunique();qualified=set(counts[counts>=p['min_unique_peptides']].index);A=links[links.variant_id.isin(qualified)];B=scored;C=scored.groupby(['search_space','variant_space']).agg(targets=('is_decoy',lambda x:sum(~x)),decoys=('is_decoy','sum')).reset_index();D=v.assign(accepted_variant=v.variant_id.isin(qualified));metrics={'searched_spectra':len(z),'accepted_variant_spectra':len(A),'variants':len(qualified)}
    elif key in {'repertoire_diversity','clonotype_phenotype'}:
        z=table('clone_cells',['cell_id','sample_id','clone_id']);s=samples()
        if z[['sample_id','cell_id']].duplicated().any() or not set(z.sample_id)<=set(s.index):raise ValueError('Clone cell/sample scope invalid')
        if 'unit_id' in z:
            expected=z.sample_id.map(s.unit_id);
            if not z.unit_id.astype(str).equals(expected.astype(str)):raise ValueError('Existing clonotype unit labels disagree with metadata')
            z=z.drop(columns='unit_id')
        unassigned=z.clone_id.isna()|z.clone_id.astype(str).str.lower().isin(['nan','none','na',''])
        z.assign(unassigned=unassigned).to_csv(out/'clonotype_assignment_denominator.tsv',sep='\t',index=False);z=z[~unassigned].copy()
        if z.empty:raise ValueError('No assigned clonotypes remain; missing clone IDs cannot form a giant artificial clone')
        z=z.merge(s[['sample_id','unit_id']].reset_index(drop=True),on='sample_id',validate='many_to_one');z['donor_clone']=[__import__('json').dumps([str(u),str(c)],ensure_ascii=False) for u,c in zip(z.unit_id,z.clone_id)]
        if key=='repertoire_diversity':
            rows=[];boots=[];exp=[]
            for unit,g in z.groupby('unit_id'):
                clones=g.donor_clone.to_numpy();counts=g.donor_clone.value_counts();prob=counts/counts.sum();rows.append((unit,len(clones),len(counts),stats.entropy(prob),1-(prob**2).sum(),counts.max()/counts.sum()));exp.extend((unit,c,int(n)) for c,n in counts.items())
                if len(clones)<p['rarefaction_depth']:raise ValueError('Selected rarefaction depth exceeds a donor denominator')
                for it in range(p['bootstraps']):
                    sub=pd.Series(rng.choice(clones,p['rarefaction_depth'],replace=False)).value_counts();pr=sub/sub.sum();boots.append((unit,it,len(sub),stats.entropy(pr)))
            A=frame(rows,['unit_id','cells','clones','shannon','simpson','max_clone_fraction']);B=frame(exp,['unit_id','clone_id','cells']);C=frame(boots,['unit_id','iteration','rarefied_richness','rarefied_shannon']);D=C.groupby('unit_id').agg(rarefaction_sampling_p025=('rarefied_shannon',lambda x:x.quantile(.025)),rarefaction_sampling_p975=('rarefied_shannon',lambda x:x.quantile(.975))).reset_index()
        else:
            state=p['state_column'];
            if state not in z:raise ValueError('Selected phenotype state missing')
            rows=[];nulls=[]
            for unit,g in z.groupby('unit_id'):
                if len(g)<p['min_cells']:raise ValueError('Insufficient clone-state donor coverage')
                ct=pd.crosstab(g.donor_clone,g[state])
                if min(ct.shape)<2:raise ValueError('Clone/state association is untestable with only one clone or one state')
                obs=stats.chi2_contingency(ct,correction=False).statistic;ns=[]
                for it in range(p['permutations']):
                    c=pd.crosstab(g.donor_clone,rng.permutation(g[state].to_numpy()));val=stats.chi2_contingency(c,correction=False).statistic;ns.append(val);nulls.append((unit,it,val))
                rows.append((unit,obs,(1+sum(v>=obs for v in ns))/(1+len(ns)),len(g),len(ct)))
            A=bh(frame(rows,['unit_id','association_chi2','p','cells','clones']));B=z.groupby(['unit_id','donor_clone',state]).size().rename('cells').reset_index();C=frame(nulls,['unit_id','iteration','null_statistic']);D=A[['unit_id','cells','clones']]
        metrics={'independent_units':z.unit_id.nunique(),'cells':len(z),'donor_specific_clones':z.donor_clone.nunique()}
    elif key=='signature_matching':
        q=table('query_signature',['feature_id','statistic']);r=matrix('reference_signatures');ct=table('signature_context',['signature_id','cell_model','dose','duration','source_record']);
        if q.feature_id.duplicated().any() or not set(r.columns)<=set(ct.signature_id):raise ValueError('Signature identity/context invalid')
        genes=[g for g in q.feature_id if g in r.index];
        if len(genes)<p['min_overlap']:raise ValueError('Insufficient ranked gene overlap')
        u=q.set_index('feature_id').loc[genes].statistic.to_numpy();rows=[];nulls=[]
        for col in r:
            v=r.loc[genes,col].to_numpy();obs=stats.spearmanr(u,v).statistic;ns=[]
            for it in range(p['permutations']):ns.append(stats.spearmanr(rng.permutation(u),v).statistic)
            rows.append((col,obs,(1+sum(abs(z)>=abs(obs) for z in ns))/(len(ns)+1),len(genes)));nulls.extend((col,it,val) for it,val in enumerate(ns))
        A=bh(frame(rows,['signature_id','rank_connectivity','p','shared_genes']));B=ct;C=frame(nulls,['signature_id','iteration','gene_permutation_score']);D=q.assign(in_reference=q.feature_id.isin(genes));metrics={'shared_genes':len(genes),'reference_signatures':len(r.columns),'gene_permutations':p['permutations']}
    elif key=='singlecell_cnv':
        x=matrix();s=samples(True);x=align(x,s);pos=table('gene_positions',['feature_id','chromosome','position']);ref=table('normal_reference',['sample_id','reviewed_normal']);
        if pos.feature_id.duplicated().any() or ref.sample_id.duplicated().any():raise ValueError('Duplicate RNA-CNV genomic/reference identities')
        if not ref.reviewed_normal.all() or not set(ref.sample_id)<=set(x.columns) or len(ref)<p['min_reference']:raise ValueError('Normal RNA reference incomplete')
        if job['context']['scale']!='log2_normalized_expression':raise ValueError('RNA-CNV smoothing requires explicit log2 normalized expression')
        shared=pos[pos.feature_id.isin(x.index)].sort_values(['chromosome','position']);baseline=x.loc[shared.feature_id,ref.sample_id].median(axis=1);centered=x.loc[shared.feature_id].sub(baseline,axis=0);smooth=[]
        for chrom,z in shared.groupby('chromosome',sort=False):
            if len(z)<p['min_chr_genes']:raise ValueError('Chromosome gene coverage insufficient')
            h=centered.loc[z.feature_id].rolling(p['window'],min_periods=max(1,p['window']//2),center=True).mean();smooth.append(h)
        smoothed=pd.concat(smooth);A=smoothed.reset_index();B=ref;C=pd.DataFrame({'sample_id':x.columns,'mean_abs_RNA_CNV':smoothed.abs().mean(axis=0)});dna=table('dna_segments',['unit_id','chromosome','start','end','log2']);concord=[]
        for unit,g in dna.groupby('unit_id'):
            cells=s.index[s.unit_id==unit];observed=[];reference=[]
            for seg in g.itertuples():
                genes=shared.feature_id[(shared.chromosome==seg.chromosome)&(shared.position.ge(seg.start)&shared.position.lt(seg.end))]
                if len(genes) and len(cells):observed.append(float(smoothed.loc[genes,cells].mean().mean()));reference.append(seg.log2)
            if len(observed)<3:raise ValueError('Independent DNA segment concordance has insufficient matching coverage')
            rr,pv=stats.spearmanr(observed,reference);concord.append((unit,len(observed),rr,pv))
        D=frame(concord,['unit_id','matched_segments','DNA_RNA_spearman_r','conditional_p']);metrics={'genes':len(shared),'reference_cells':len(ref),'cells_or_units':len(x.columns)}
    elif key in {'spatial_niches','spatial_lr','spatial_gradients'}:
        co=table('coordinates',['spot_id','x','y','section_id','unit_id']);blocks=table('permutation_blocks',['spot_id','block_id'])
        if co.spot_id.duplicated().any() or co[['x','y']].isna().any().any() or co.groupby('section_id').unit_id.nunique().max()!=1:raise ValueError('Section/unit/coordinate mapping invalid')
        if blocks.spot_id.duplicated().any() or set(co.spot_id)!=set(blocks.spot_id) or blocks.block_id.isna().any():raise ValueError('Complete independently reviewed spatial exchangeability blocks required')
        blockmap=blocks.set_index('spot_id').block_id
        def permuted(values,block):
            answer=values.copy()
            for label in sorted(set(block)):
                ix=np.flatnonzero(block==label);answer[ix]=rng.permutation(values[ix])
            return answer
        if key=='spatial_gradients':
            from patsy import dmatrix
            v=table('spatial_values',['spot_id','feature_id','value']);bounds=table('boundaries',['section_id','x','y']);rows=[];resids=[];distances=[];spatial_diagnostics=[]
            if v[['spot_id','feature_id']].duplicated().any() or not set(v.spot_id)<=set(co.spot_id):raise ValueError('Duplicate/mismatched spatial feature observations')
            for section,g in co.groupby('section_id'):
                boundary=bounds[bounds.section_id==section]
                if len(boundary)<2:raise ValueError('Explicit tissue boundary coordinates required')
                dd=spatial.cKDTree(boundary[['x','y']]).query(g[['x','y']])[0]*p['distance_scale'];distance=dict(zip(g.spot_id,dd));distances.extend((section,k,val) for k,val in distance.items())
                for feature,z in v[v.spot_id.isin(g.spot_id)].groupby('feature_id'):
                    if len(z)<p['min_spots']:raise ValueError('Insufficient gradient observations')
                    dx=z.spot_id.map(distance).to_numpy();d=np.asarray(dmatrix('bs(x, df=df, degree=3, include_intercept=False)',{'x':dx,'df':p['time_df']}));yy=z.value.to_numpy(float);fit=sm.OLS(yy,d).fit()
                    block=z.spot_id.map(blockmap).to_numpy();ids=np.array(sorted(set(block)))
                    if len(ids)<5:raise ValueError('Spatial gradient uncertainty requires at least five declared spatial blocks')
                    samples=[];failed=0
                    for _ in range(p['bootstraps']):
                        chosen=rng.choice(ids,len(ids));ix=np.concatenate([np.flatnonzero(block==k) for k in chosen]);xx=d[ix]
                        if np.linalg.matrix_rank(xx)<d.shape[1]:failed+=1;continue
                        samples.append(np.linalg.lstsq(xx,yy[ix],rcond=None)[0])
                    if len(samples)<.9*p['bootstraps']:raise ValueError('Excessive rank-deficient spatial block resamples')
                    samples=np.asarray(samples);lo,hi=np.quantile(samples,[.025,.975],axis=0);se=samples.std(axis=0,ddof=1)
                    for j,effect in enumerate(fit.params):rows.append((section,g.unit_id.iloc[0],feature,j,effect,se[j],lo[j],hi[j],fit.rsquared,len(ids),failed))
                    positions=g.set_index('spot_id').loc[z.spot_id,['x','y']].to_numpy();pairs=spatial.cKDTree(positions).query_pairs(p['residual_radius'],output_type='ndarray');rr=fit.resid
                    moran=float(len(z)*np.sum(rr[pairs[:,0]]*rr[pairs[:,1]])/(len(pairs)*np.sum(rr**2))) if len(pairs) and np.sum(rr**2)>0 else np.nan
                    spatial_diagnostics.append((section,feature,moran,len(pairs),len(ids)))
                    resids.extend((section,feature,spot,float(residual)) for spot,residual in zip(z.spot_id,rr))
            A=frame(rows,['section_id','unit_id','feature_id','basis','effect','conditional_se','ci_lower','ci_upper','r_squared','spatial_blocks','failed_resamples']);B=bounds;C=frame(resids,['section_id','feature_id','spot_id','residual']).merge(frame(spatial_diagnostics,['section_id','feature_id','residual_Moran_I','residual_neighbor_pairs','spatial_blocks']),on=['section_id','feature_id'],validate='many_to_one');D=frame(distances,['section_id','spot_id','distance']);metrics={'sections':co.section_id.nunique(),'units':co.unit_id.nunique(),'conditional_models':A[['section_id','feature_id']].drop_duplicates().shape[0]}
        else:
            types=table('cell_types',['spot_id','cell_type']).set_index('spot_id')
            if set(co.spot_id)!=set(types.index) or types.index.duplicated().any():raise ValueError('Incomplete/duplicate spatial cell-type assignment')
            x=matrix() if key=='spatial_lr' else None;lr=table('lr_resource',['ligand','receptor']) if key=='spatial_lr' else None;rows=[];nulls=[];edges=[]
            for section,g in co.groupby('section_id'):
                coords=g[['x','y']].to_numpy();pairs=spatial.cKDTree(coords).query_pairs(p['radius'],output_type='ndarray')
                if not len(pairs):raise ValueError('No spatial neighbors at selected physical radius')
                directed=np.vstack([pairs,pairs[:,::-1]]);spots=g.spot_id.to_numpy();labels=types.loc[spots].cell_type.to_numpy();block=g.spot_id.map(blockmap).to_numpy();categories=sorted(set(labels))
                if any(sum(block==k)<2 for k in set(block)):raise ValueError('Spatial null has singleton nonexchangeable blocks')
                edges.extend((section,spots[i],spots[j],labels[i],labels[j],np.linalg.norm(coords[i]-coords[j])) for i,j in pairs)
                if key=='spatial_niches':
                    obs={(a,b):sum((labels[directed[:,0]]==a)&(labels[directed[:,1]]==b)) for a in categories for b in categories};nv={k:[] for k in obs}
                    for it in range(p['permutations']):
                        lab=permuted(labels,block)
                        for (a,b) in nv:nv[(a,b)].append(int(sum((lab[directed[:,0]]==a)&(lab[directed[:,1]]==b))))
                    for (a,b),observed in obs.items():
                        ns=np.asarray(nv[(a,b)]);rows.append((section,g.unit_id.iloc[0],a,b,'NA','NA',observed,ns.mean(),(1+sum(ns>=observed))/(len(ns)+1),len(directed),'TESTED'));nulls.extend((section,a,b,'NA','NA',it,int(val)) for it,val in enumerate(ns))
                else:
                    if not set(spots)<=set(x.columns) or (x<0).any().any():raise ValueError('Spatial LR requires complete nonnegative normalized expression')
                    if lr[['ligand','receptor']].duplicated().any():raise ValueError('Duplicate spatial LR hypotheses')
                    for interaction in lr.itertuples():
                        if interaction.ligand not in x.index or interaction.receptor not in x.index:raise ValueError('Spatial LR gene universe is incomplete; complex IDs require an explicit upstream monomer representation')
                        u=x.loc[interaction.ligand,spots].to_numpy();v=x.loc[interaction.receptor,spots].to_numpy()
                        for source in categories:
                            for target in categories:
                                chosen=(labels[directed[:,0]]==source)&(labels[directed[:,1]]==target);d=directed[chosen];n=len(d)
                                if n<p['min_neighbors']:rows.append((section,g.unit_id.iloc[0],source,target,interaction.ligand,interaction.receptor,np.nan,np.nan,np.nan,n,'UNASSESSED_LOW_NEIGHBOR_COVERAGE'));continue
                                observed=np.mean(u[d[:,0]]*v[d[:,1]]);ns=[];within=np.array([str(a)+'|'+str(b) for a,b in zip(block,labels)])
                                for it in range(p['permutations']):ns.append(np.mean(u[d[:,0]]*permuted(v,within)[d[:,1]]))
                                rows.append((section,g.unit_id.iloc[0],source,target,interaction.ligand,interaction.receptor,observed,np.mean(ns),(1+sum(val>=observed for val in ns))/(len(ns)+1),n,'TESTED'));nulls.extend((section,source,target,interaction.ligand,interaction.receptor,it,val) for it,val in enumerate(ns))
            A=bh(frame(rows,['section_id','unit_id','source','target','ligand','receptor','observed','null_mean','p','neighbor_pairs','test_status']));B=frame(edges,['section_id','source_spot','target_spot','source_type','target_type','distance']);C=frame(nulls,['section_id','source','target','ligand','receptor','iteration','null_score']);D=co.assign(radius=p['radius'],permutation_block=co.spot_id.map(blockmap));metrics={'sections':co.section_id.nunique(),'units':co.unit_id.nunique(),'neighbor_pairs':len(B),'tested_hypotheses':int(A.p.notna().sum()),'unassessed_hypotheses':int(A.p.isna().sum())}
    elif key=='temporal_modules':
        from patsy import dmatrix
        from sklearn.cluster import KMeans
        from sklearn.metrics import adjusted_rand_score
        x=matrix();s=samples(True);x=align(x,s);t=pd.to_numeric(s[p['time_column']],errors='raise').to_numpy()
        if not np.isfinite(t).all() or len(np.unique(t))<=p['time_df'] or len(set(s.unit_id))<4:raise ValueError('Insufficient temporal/donor coverage')
        time_basis=np.asarray(dmatrix('bs(t, df=df, degree=3, include_intercept=False)-1',{'t':t,'df':p['time_df']}));nuisance=pd.get_dummies(s[p['covariates']],drop_first=True,dtype=float) if p['covariates'] else pd.DataFrame(index=s.index);parts=[np.ones((len(s),1)),nuisance.to_numpy(),time_basis]
        if p['time_group']!='none':
            group=pd.get_dummies(s[p['time_group']],drop_first=True,dtype=float).to_numpy()
            if not group.shape[1]:raise ValueError('Selected temporal group has only one level')
            parts.extend([group,np.hstack([time_basis*group[:,j,None] for j in range(group.shape[1])])])
        basis=np.hstack(parts)
        if np.linalg.matrix_rank(basis)!=basis.shape[1] or len(s)<=basis.shape[1]:raise ValueError('Temporal covariate/group spline design is rank deficient or saturated')
        coef=np.linalg.lstsq(basis,x.T,rcond=None)[0].T
        # Keep nuisance effects out of temporal clustering; retain the full fit
        # for residual diagnostics rather than treating adjusted curves as fits.
        display_basis=basis.copy();display_basis[:,1:1+nuisance.shape[1]]=0
        fitted_full=coef@basis.T;curves=coef@display_basis.T;sd=curves.std(axis=1)
        if (sd<=0).any() or p['n_modules']>=len(x):raise ValueError('Flat curves or invalid module number')
        z=(curves-curves.mean(axis=1,keepdims=True))/sd[:,None];labels=KMeans(n_clusters=p['n_modules'],n_init=20,random_state=p['seed']).fit_predict(z);boots=[];failed=0
        units=np.array(sorted(set(s.unit_id)))
        for it in range(p['bootstraps']):
            chosen=rng.choice(units,len(units));idx=np.concatenate([np.flatnonzero(s.unit_id.to_numpy()==u) for u in chosen])
            if np.linalg.matrix_rank(basis[idx])!=basis.shape[1]:failed+=1;boots.append((it,np.nan,'RANK_DEFICIENT_RESAMPLE'));continue
            cf=np.linalg.lstsq(basis[idx],x.to_numpy()[:,idx].T,rcond=None)[0].T;cc=cf@display_basis.T;cc=(cc-cc.mean(axis=1,keepdims=True))/np.maximum(cc.std(axis=1,keepdims=True),1e-8);ll=KMeans(n_clusters=p['n_modules'],n_init=10,random_state=p['seed']+it).fit_predict(cc);boots.append((it,adjusted_rand_score(labels,ll),'ASSESSED'))
        if 1-failed/p['bootstraps']<p['min_valid_resample_fraction']:raise ValueError('Too few estimable donor-bootstrap temporal designs')
        A=pd.DataFrame({'feature_id':x.index,'module':labels});B=pd.DataFrame(z,index=x.index,columns=x.columns).groupby(labels).mean().reset_index();C=pd.DataFrame({'feature_id':x.index,'full_model_residual_rmse':np.sqrt(((x.to_numpy()-fitted_full)**2).mean(axis=1)),'curve_scope':'time_and_group_terms_at_zero_nuisance_design'});D=frame(boots,['iteration','adjusted_rand_index','resample_status']);metrics={'genes':len(x),'units':len(units),'modules':len(set(labels)),'failed_resamples':failed,'valid_resample_fraction':1-failed/p['bootstraps']}
    elif key=='uorf_translation':
        sites=table('p_sites',['chromosome','position','strand','sample_id','count']);orfs=table('orfs',['orf_id','chromosome','start','end','strand','transcript_id','orf_type','orf_start_tx','orf_end_tx','main_cds_start_tx']);blocks=table('orf_blocks',['orf_id','chromosome','start','end','strand','transcript_offset']);qc=table('offset_qc',['sample_id','offset_validated','cds_frame0_fraction']);
        if qc.sample_id.duplicated().any() or orfs.orf_id.duplicated().any() or qc.sample_id.isna().any() or orfs.orf_id.isna().any() or not qc.offset_validated.all() or not np.isfinite(qc.cds_frame0_fraction).all() or not qc.cds_frame0_fraction.between(1/3,1,inclusive='right').all() or not set(sites.sample_id)<=set(qc.sample_id):raise ValueError('P-site offset/known-CDS periodicity/unique source axes QC failed')
        if not np.isfinite(sites.position).all() or (sites.position<0).any() or (sites.position%1!=0).any() or not sites.strand.isin(['+','-']).all() or sites.sample_id.isna().any():raise ValueError('P-sites need exact nonnegative integer coordinates, strand and sample identity')
        if (sites['count']<0).any() or (sites['count']%1!=0).any():raise ValueError('P-site observations must be real nonnegative integer counts')
        rows=[];frames=[];per_sample=[]
        for o in orfs.itertuples():
            selected_blocks=blocks[blocks.orf_id==o.orf_id].sort_values('transcript_offset');fragments=[]
            if selected_blocks.empty or int(selected_blocks.transcript_offset.min())!=0:raise ValueError('Exon-aware ORF coordinate map missing or not anchored at ORF start')
            cursor=0
            for block in selected_blocks.itertuples():
                if block.transcript_offset!=cursor or block.end<=block.start or block.strand!=o.strand or block.chromosome!=o.chromosome:raise ValueError('ORF exon blocks are noncontiguous in transcript coordinates or use incompatible reference/strand')
                cursor+=block.end-block.start
                z=sites[(sites.chromosome==block.chromosome)&(sites.strand==block.strand)&sites.position.between(block.start,block.end-1)].copy();offset=(z.position-block.start if block.strand=='+' else block.end-1-z.position)+block.transcript_offset;z['frame']=offset%3;fragments.append(z)
            if cursor!=o.orf_end_tx-o.orf_start_tx or cursor%3:raise ValueError('ORF exon length/frame disagrees with transcript definition')
            z=pd.concat(fragments)
            if z[['chromosome','position','strand','sample_id']].duplicated().any():raise ValueError('Overlapping exon blocks or duplicate P-sites double-count reads')
            for sample in qc.sample_id:
                sample_counts=z[z.sample_id==sample].groupby('frame')['count'].sum().reindex([0,1,2],fill_value=0);den=sample_counts.sum();per_sample.append((o.orf_id,sample,int(den),float(sample_counts[0]/den) if den else np.nan))
            counts=z.groupby('frame')['count'].sum().reindex([0,1,2],fill_value=0);total=counts.sum();codons=(o.orf_end_tx-o.orf_start_tx)//3
            if o.orf_type=='uORF' and o.orf_end_tx>o.main_cds_start_tx:raise ValueError('Overlapping ORF cannot be labeled a non-overlapping upstream ORF')
            testable=total>=p['min_reads'] and codons>=p['min_codons'];pv=stats.binomtest(int(counts[0]),int(total),1/3,alternative='greater').pvalue if testable else np.nan;rows.append((o.orf_id,total,codons,counts[0]/total if total else np.nan,pv,testable));frames.extend((o.orf_id,int(f),int(c)) for f,c in counts.items())
        A=bh(frame(rows,['orf_id','p_sites','codons','frame0_fraction','p','testable']));A['candidate_periodic']=A.testable&A.q.lt(p['fdr']);A['p_scope']='pooled_read_conditional_binomial_not_independent_donor_translation_evidence';frame(per_sample,['orf_id','sample_id','p_sites','frame0_fraction']).to_csv(out/'per_sample_ORF_periodicity.tsv',sep='\t',index=False);B=frame(frames,['orf_id','frame','p_sites']);C=orfs;D=qc;metrics={'candidate_orfs':len(orfs),'testable_orfs':int(A.testable.sum()),'offset_validated_samples':len(qc)}
        if p['periodicity_inference']=='donor_controlled':
            metadata=samples(True)
            if 'group' in metadata and metadata.group.nunique()!=1:raise ValueError('ORF presence inference must select one declared biological condition')
            controls=table('orf_negative_controls',['orf_id','unit_id','frame0_fraction','matched_length','reviewed'])
            controls['reviewed']=controls.reviewed.map(strict_bool)
            if controls[['orf_id','unit_id']].duplicated().any() or not controls.reviewed.all() or not controls.frame0_fraction.between(0,1).all() or not controls.matched_length.map(strict_bool).all():raise ValueError('Complete, unique, reviewed and length-matched negative ORF periodicity controls required')
            ps=frame(per_sample,['orf_id','sample_id','p_sites','frame0_fraction']);ps['frame0_sites']=ps.p_sites*ps.frame0_fraction.fillna(0)
            if not set(ps.sample_id)<=set(metadata.index):raise ValueError('P-site samples lack actual independent units')
            ps['unit_id']=ps.sample_id.map(metadata.unit_id);units=ps.groupby(['orf_id','unit_id'],as_index=False).agg(p_sites=('p_sites','sum'),frame0_sites=('frame0_sites','sum'));units['frame0_fraction']=units.frame0_sites/units.p_sites.replace(0,np.nan)
            units=units.merge(controls,on=['orf_id','unit_id'],how='left',suffixes=('','_negative_control'),validate='one_to_one')
            if units.frame0_fraction_negative_control.isna().any():raise ValueError('Negative-control denominator does not cover every ORF/unit')
            units['difference']=units.frame0_fraction-units.frame0_fraction_negative_control;units['orf_codons']=units.orf_id.map(A.set_index('orf_id').codons);units['eligible']=units.p_sites.ge(p['min_reads'])&units.orf_codons.ge(p['min_codons'])&units.difference.notna();pop=[]
            for identity,z in units.groupby('orf_id'):
                d=z.loc[z.eligible,'difference'].to_numpy();d[np.isclose(d,0,atol=1e-12)]=0;nonzero=d[d!=0];valid=len(nonzero)>=p['min_independent_units'];pv=stats.binomtest(int((nonzero>0).sum()),len(nonzero),.5,alternative='greater').pvalue if valid else np.nan;pop.append((identity,len(d),len(nonzero),float(np.median(d)) if len(d) else np.nan,pv,valid))
            A=A.rename(columns={'p':'read_level_p','q':'read_level_q','testable':'read_level_testable'}).drop(columns=['candidate_periodic']);A=A.merge(frame(pop,['orf_id','eligible_units','non_tied_units','median_controlled_frame0_difference','p','testable']),on='orf_id',validate='one_to_one');A=bh(A);A['candidate_periodic']=A.testable&A.q.lt(p['fdr']);A['p_scope']='independent_unit_sign_test_vs_length_matched_negative_ORF_controls_not_confirmed_translation';units.to_csv(out/'donor_controlled_ORF_periodicity.tsv',sep='\t',index=False);metrics['formal_testable_orfs']=int(A.testable.sum());metrics['independent_units']=metadata.unit_id.nunique()
        elif p['periodicity_inference']!='conditional_reads':raise ValueError('Select conditional_reads or donor_controlled periodicity explicitly')
    else:raise ValueError('No native implementation: '+key)
    mapping={}
    for role,obj in zip(job['required_roles'],[A,B,C,D]):
        if not isinstance(obj,pd.DataFrame) or not len(obj.columns):raise ValueError('Real typed branch result required')
        numeric=obj.select_dtypes(include='number')
        if np.isinf(numeric.to_numpy()).any():raise ValueError('Numerical infinity must be investigated, never silently converted to missing')
        name=role+'.tsv';obj.to_csv(out/name,sep='\t',index=False,na_rep='NA');mapping[role]=name
    if not metrics:raise ValueError('Measured diagnostics missing')
    if 'p' in A:metrics['finite_primary_pvalues']=int(np.isfinite(pd.to_numeric(A.p,errors='coerce')).sum())
    if 'testable' in A:metrics['actually_testable_primary_rows']=int(A.testable.sum());metrics['untestable_primary_rows']=int((~A.testable).sum())
    write(out/'diagnostics.private.json',{'fit_completed':True,'metrics':metrics,'method':p['implementation'],
      'causality':'not_established','native_alternative_not_original_candidate':True})
    return mapping
