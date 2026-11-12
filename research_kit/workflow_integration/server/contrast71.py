"""Independent-unit numeric contrasts. Only imported by allocated-server scientific workers."""
def contrast_matrix(x,s,p):
    import numpy as np,pandas as pd
    from scipy import stats
    import statsmodels.api as sm
    from statsmodels.stats.multitest import multipletests
    if set(x.columns)!=set(s.index):raise ValueError('Contrast sample universe mismatch')
    x=x.loc[:,s.index];s=s.loc[x.columns];method=p['contrast_method'];minimum=p['min_units']
    if x.isna().any().any() or not np.isfinite(x.to_numpy(float)).all() or s[['unit_id','group']].isna().any().any():raise ValueError('No implicit missingness removal in formal contrast')
    if set(s.group)!={p['control'],p['treatment']}:raise ValueError('Exactly the reviewed groups are required')
    covariates=p['covariates']
    if method!='ols_hc3' and covariates:raise ValueError('Covariates cannot be silently ignored by Welch/paired contrast')
    a=s.group.eq(p['control']);b=s.group.eq(p['treatment']);result=[]
    if method=='paired_t':
        cross=pd.crosstab(s.unit_id,s.group)
        if not (cross.to_numpy()==1).all() or len(cross)<minimum:raise ValueError('Complete unique paired independent units required')
        left=s[a].sort_values('unit_id');right=s[b].sort_values('unit_id')
        if not left.unit_id.reset_index(drop=True).equals(right.unit_id.reset_index(drop=True)):raise ValueError('Paired donor axes differ')
        delta=x.loc[:,right.index].to_numpy()-x.loc[:,left.index].to_numpy();n=delta.shape[1]
        effect=delta.mean(axis=1);se=delta.std(axis=1,ddof=1)/np.sqrt(n);df=np.repeat(n-1,len(x));nn=(n,n)
        statistic=np.divide(effect,se,out=np.zeros_like(effect),where=se>0);prob=2*stats.t.sf(abs(statistic),df)
    elif method=='unpaired_welch':
        if s.unit_id.duplicated().any() or min(a.sum(),b.sum())<minimum:raise ValueError('Independent units and minimum group coverage required')
        aa=x.loc[:,a].to_numpy();bb=x.loc[:,b].to_numpy();va=aa.var(axis=1,ddof=1)/a.sum();vb=bb.var(axis=1,ddof=1)/b.sum();se=np.sqrt(va+vb);effect=bb.mean(axis=1)-aa.mean(axis=1)
        df=np.divide((va+vb)**2,va**2/(a.sum()-1)+vb**2/(b.sum()-1),out=np.full(len(x),np.nan),where=(va+vb)>0);statistic=np.divide(effect,se,out=np.zeros(len(x)),where=se>0);prob=2*stats.t.sf(abs(statistic),df);nn=(int(a.sum()),int(b.sum()))
    elif method=='ols_hc3':
        if s.unit_id.duplicated().any() or min(a.sum(),b.sum())<minimum or not set(covariates)<=set(s):raise ValueError('HC3 contrast independent-unit/covariate scope invalid')
        cv=pd.get_dummies(s[covariates],drop_first=True,dtype=float) if covariates else pd.DataFrame(index=s.index)
        if cv.isna().any().any():raise ValueError('Covariates have missing values')
        d=np.column_stack([np.ones(len(s)),b.to_numpy(float),cv.to_numpy(float)])
        if np.linalg.matrix_rank(d)!=d.shape[1] or len(s)<=d.shape[1]+2:raise ValueError('HC3 contrast rank/residual degrees of freedom insufficient')
        effect=[];se=[];prob=[]
        for _,row in x.iterrows():
            f=sm.OLS(row.to_numpy(float),d).fit(cov_type='HC3',use_t=True);effect.append(f.params[1]);se.append(f.bse[1]);prob.append(f.pvalues[1])
        effect=np.asarray(effect);se=np.asarray(se);prob=np.asarray(prob);df=np.repeat(len(s)-d.shape[1],len(x));nn=(int(a.sum()),int(b.sum()))
    else:raise ValueError('Choose unpaired_welch, paired_t or ols_hc3 explicitly')
    # A constant feature is untestable; never manufacture p=1 or p=0 by dividing by zero.
    testable=(se>0)&np.isfinite(se)&np.isfinite(df)&np.isfinite(prob);prob=np.where(testable,prob,np.nan);ci=stats.t.ppf(.975,df)*se
    q=np.full(len(x),np.nan)
    if testable.any():q[testable]=multipletests(prob[testable],method='fdr_bh')[1]
    return pd.DataFrame({'feature_id':x.index,'effect':effect,'se':se,'ci_lower':effect-ci,'ci_upper':effect+ci,'p':prob,'q':q,
      'n_control':nn[0],'n_treatment':nn[1],'residual_df':df,'testable':testable,
      'test_status':np.where(testable,'TESTED','UNTESTABLE_ZERO_VARIANCE_OR_NONFINITE'),'contrast_method':method})
