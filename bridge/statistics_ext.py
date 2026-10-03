"""Research statistics guidance and bounded, explicit computations; no automatic clinical decisions."""
import math
from pathlib import Path

REFERENCES = {
    'welch':'https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html',
    'power':'https://www.statsmodels.org/stable/stats.html#power-and-sample-size-calculations',
    'models':'https://www.statsmodels.org/stable/user-guide.html',
    'multiplicity':'https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.false_discovery_control.html',
    'repeated_expression':'https://bioconductor.org/packages/release/bioc/vignettes/variancePartition/inst/doc/dream.html',
}


def _finite(value):
    if isinstance(value,bool): raise ValueError('Boolean is not a numeric observation')
    x=float(value)
    if not math.isfinite(x): raise ValueError('Nonfinite numeric value')
    return x


def guide_study_statistics(study: dict) -> dict:
    """Produce a design-aware statistical consultation: estimand, units, candidate methods, assumptions and reporting; fit nothing."""
    required={'question','design','outcome_type','independent_unit','estimand','groups','repeated','clustered','primary_endpoints','missing_data','covariates'}
    if not isinstance(study,dict) or required-set(study): raise ValueError('Missing consultation fields: '+','.join(sorted(required-set(study) if isinstance(study,dict) else required)))
    if study['design'] not in {'randomized','observational','diagnostic','prediction','descriptive'}: raise ValueError('Unsupported study design')
    if study['outcome_type'] not in {'continuous','binary','count','ordinal','survival','expression','composition'}: raise ValueError('Unsupported outcome type')
    if type(study['groups']) is not int or study['groups']<1 or type(study['repeated']) is not bool or type(study['clustered']) is not bool: raise ValueError('Specify group count and explicit repeated/clustered flags')
    if not isinstance(study['primary_endpoints'],list) or not study['primary_endpoints'] or not isinstance(study['covariates'],list): raise ValueError('Declare endpoints and covariates explicitly')
    for k in ['question','independent_unit','estimand','missing_data']:
        if not isinstance(study[k],str) or not study[k].strip(): raise ValueError('Provide nonempty '+k)
    kind=study['outcome_type'];dependent=study['repeated'] or study['clustered']
    candidates={
        'continuous':['Welch mean difference with confidence interval for two independent groups','Prespecified linear regression with residual diagnostics','Robust or resampling sensitivity analysis at the independent-unit level'],
        'binary':['Risk difference and risk ratio with confidence intervals','Binomial/logistic regression with sparse-event and separation checks'],
        'count':['Poisson model only if dispersion is adequate','Negative-binomial model when scientifically appropriate; document exposure offset'],
        'ordinal':['Ordinal regression with proportional-odds assessment','Prespecified rank-based estimand; a rank test is not automatically a median test'],
        'survival':['Kaplan-Meier descriptive estimates','Cox regression with proportional-hazards checks','Restricted mean survival time for a prespecified horizon; handle competing risks explicitly'],
        'expression':['Count-aware DESeq2/edgeR or limma voom','Donor-level pseudobulk for cell-level measurements','dream mixed models for repeated-measures expression'],
        'composition':['Independent-unit-level composition model','Account for the sum constraint and sampling depth; analyze denominator changes'],
    }[kind]
    if dependent: candidates=['Use paired, cluster-robust, GEE or mixed models matching the estimand; do not treat rows as independent']+candidates
    if study['design']=='prediction': candidates=['Split by independent unit before preprocessing; use nested validation for selection','Assess discrimination, calibration and external validation']+candidates
    if study['design']=='diagnostic': candidates=['Define reference standard, blinded assessment, spectrum and verification bias','Prespecify thresholds; report sensitivity/specificity with independent-unit confidence intervals']+candidates
    return {'success':True,'state':'guidance_only','study':study,'candidate_methods':candidates,
        'required_checks':['Verify the actual independent unit and group allocation from source records','Define the population, exposure/treatment, outcome, time horizon and target contrast','Inspect distribution, variance, residuals, outliers and model fit; do not choose a test solely from a normality p-value','Check missingness by group and reasons; MCAR/MAR/MNAR cannot be proven from the observed table','Check collinearity, sparse groups and overlap; covariate adjustment does not prove causality','Define the family of tests and multiplicity strategy before examining significance'],
        'missing_data_guidance':['Report amount, pattern and reasons by endpoint and group','Complete-case estimates may be biased; document its assumptions','Multiple imputation must respect clusters, time, outcome/exposure and analysis model','Plan sensitivity to departures from MAR; do not silently fill values with group means'],
        'reporting':['Independent units and observations separately','Effect estimate and uncertainty, not only p-values','Prespecified primary endpoint and contrast, exclusions and missing-data decisions','Diagnostics, multiplicity family, sensitivity analyses and negative results'],
        'power_guidance':['Choose a scientifically meaningful effect and plausible variability/event rate before observing results','Use a range of assumptions; inflate for attrition only with an explicit rationale','Use simulation for complex repeated, clustered, survival or high-dimensional designs','Do not report observed post-hoc power as evidence for a null finding'],
        'causal_boundary':'Randomization, confounding, selection and measurement assumptions require scientific review; method choice alone does not identify a causal effect.',
        'references':REFERENCES,'limitations':['Consultation is a structured aid; recommendations require source/design review.','Candidate methods are not automatically executable backends or final approval of an analysis.']}


def audit_statistical_dataset(path: str, unit_key: str, outcome_keys: list, group_key: str = '', required_keys: list = None, repeated: bool = False) -> dict:
    """Audit a local table for missingness, independent units, duplicate records and group overlap without imputing or excluding."""
    from workflow_ext import _table,_hash
    h,rows=_table(path,20000000)
    required=list(dict.fromkeys([unit_key,*outcome_keys,*(required_keys or []),*([group_key] if group_key else [])]))
    if not outcome_keys or not set(required)<=set(h) or len(rows)>100000: raise ValueError('Provide valid columns and a bounded table')
    missing={'','na','nan','null','none','.'}
    absent=lambda v: str(v).strip().lower() in missing
    issues=[]
    if any(absent(r[unit_key]) for r in rows): issues.append('missing_independent_unit')
    units={r[unit_key] for r in rows if not absent(r[unit_key])}
    duplicates=len(rows)-len({tuple(r[k] for k in h) for r in rows})
    if duplicates: issues.append('duplicate_full_records')
    if len(rows)>len(units) and not repeated: issues.append('repeated_units_in_declared_independent_data')
    by_group={}
    if group_key:
        for g in sorted({r[group_key] for r in rows}):
            rr=[r for r in rows if r[group_key]==g];uu={r[unit_key] for r in rr if not absent(r[unit_key])}
            by_group[g]={'observations':len(rr),'independent_units':len(uu),'missing':{k:sum(absent(r[k]) for r in rr) for k in required}}
        overlap={u for u in units if len({r[group_key] for r in rows if r[unit_key]==u})>1}
        if overlap and not repeated: issues.append('units_shared_across_independent_groups')
    return {'success':True,'qc_gate_pass':not issues,'issues':issues,'observations':len(rows),'independent_units':len(units),'duplicate_records':duplicates,'missing':{k:sum(absent(r[k]) for r in rows) for k in required},'groups':by_group,'input_sha256':_hash(path),'limitations':['No rows are removed or imputed.','Missingness mechanisms and the validity of unit labels are not inferred from the table.','Duplicate records may reflect an export error or a real design; review their origin.']}


def compare_groups(case_values: list, control_values: list, case_units: list, control_units: list, paired: bool = False, confidence: float = 0.95) -> dict:
    """Estimate a prespecified mean difference with a Welch or paired t interval and test; reject pseudoreplicated or missing inputs."""
    from compute_policy import require_local
    require_local()
    import numpy as np
    from scipy import stats
    a=np.array([_finite(x) for x in case_values]);b=np.array([_finite(x) for x in control_values])
    if not 0.8<=confidence<1 or not 3<=len(a)<=10000 or not 3<=len(b)<=10000: raise ValueError('Use 3..10000 units per group and a valid confidence level')
    if len(a)!=len(case_units) or len(b)!=len(control_units) or any(not isinstance(u,str) or not u for u in [*case_units,*control_units]) or len(set(case_units))!=len(a) or len(set(control_units))!=len(b): raise ValueError('Each value must have a distinct nonempty biological unit within its group')
    if paired:
        if set(case_units)!=set(control_units): raise ValueError('Pairs must be complete and align by unit ID')
        lookup=dict(zip(control_units,b));b=np.array([lookup[u] for u in case_units]);d=a-b
        if d.std(ddof=1)==0: raise ValueError('Constant paired differences; t inference is undefined')
        test=stats.ttest_rel(a,b);method='paired_t';effect={'mean_difference':float(d.mean()),'paired_standardized_difference_dz':float(d.mean()/d.std(ddof=1))}
    else:
        if set(case_units)&set(control_units): raise ValueError('Shared units require an explicitly dependent design')
        if a.var(ddof=1)+b.var(ddof=1)==0: raise ValueError('Both groups have zero variance')
        test=stats.ttest_ind(a,b,equal_var=False);method='welch_t'
        pooled=math.sqrt(((len(a)-1)*a.var(ddof=1)+(len(b)-1)*b.var(ddof=1))/(len(a)+len(b)-2))
        correction=1-3/(4*(len(a)+len(b)-2)-1)
        effect={'mean_difference':float(a.mean()-b.mean()),'hedges_g_descriptive':float(correction*(a.mean()-b.mean())/pooled)}
    ci=test.confidence_interval(confidence_level=confidence)
    return {'success':True,'method':method,'contrast':'case minus control','effect':effect,'confidence_level':confidence,'mean_difference_ci':[float(ci.low),float(ci.high)],'statistic':float(test.statistic),'degrees_of_freedom':float(test.df),'pvalue':float(test.pvalue),'independent_units':{'case':len(a),'control':len(b)},'limitations':['No automatic outlier removal or missing-value omission.','The t model and sampling assumptions need review; no normality-test-driven method switching.','No multiplicity adjustment is applied to this single comparison.','An association or mean difference does not by itself establish causality.']}


def adjust_pvalues(pvalues: list, family: str, method: str = 'bh') -> dict:
    """Adjust a declared complete family using BH, BY, Holm or Bonferroni; never invent a missing test family."""
    if not isinstance(family,str) or not family.strip() or not 1<=len(pvalues)<=100000 or method not in {'bh','by','holm','bonferroni'}: raise ValueError('Declare the complete test family and a supported method')
    p=[_finite(x) for x in pvalues]
    if any(x<0 or x>1 for x in p): raise ValueError('p-values must be in [0,1]')
    n=len(p);order=sorted(range(n),key=p.__getitem__);adjusted=[0.]*n
    if method=='bonferroni': adjusted=[min(1.,x*n) for x in p]
    elif method=='holm':
        running=0.
        for rank,i in enumerate(order): running=max(running,min(1.,(n-rank)*p[i]));adjusted[i]=running
    else:
        factor=sum(1/j for j in range(1,n+1)) if method=='by' else 1.
        running=1.
        for rank in range(n-1,-1,-1):
            i=order[rank];running=min(running,n*factor*p[i]/(rank+1));adjusted[i]=min(1.,running)
    return {'success':True,'family':family,'method':method,'tests':n,'adjusted_pvalues':adjusted,'limitations':['The caller must supply all tests in the intended family, not only selected significant tests.','BH requires independence or suitable positive dependence; BY is more conservative under general dependence.','Holm and Bonferroni control family-wise error; BH/BY target false discovery rate.']}


def plan_sample_size(effect_sizes: list, target_power: float = 0.8, alpha: float = 0.05, design: str = 'independent', ratio: float = 1., attrition: float = 0.) -> dict:
    """Prospective two-sided t-test sample-size sensitivity scenarios using noncentral t; paired effects use SD of differences."""
    from compute_policy import require_local
    require_local()
    from scipy.stats import nct,t
    if design not in {'independent','paired'} or not 0.5<target_power<1 or not 0<alpha<0.2 or not 0.1<=ratio<=10 or not 0<=attrition<0.8 or not 1<=len(effect_sizes)<=20: raise ValueError('Invalid prospective power assumptions')
    if design=='paired' and ratio!=1: raise ValueError('Paired design requires ratio=1')
    effects=[_finite(x) for x in effect_sizes]
    if any(not 0<x<=10 for x in effects): raise ValueError('Provide plausible positive standardized effects')
    scenarios=[]
    for effect in effects:
        def power(n):
            n2=math.ceil(n*ratio);df=n-1 if design=='paired' else n+n2-2
            delta=effect*math.sqrt(n if design=='paired' else n*n2/(n+n2));critical=t.ppf(1-alpha/2,df)
            # Symmetry avoids a noncentral-t lower-tail NaN in some SciPy builds.
            value=float(nct.sf(critical,df,delta)+nct.sf(critical,df,-delta))
            if not math.isfinite(value): raise ValueError('Power backend returned a nonfinite probability')
            return min(1.,max(0.,value))
        low,high=2,100000
        if power(high)<target_power: raise ValueError('Required sample size exceeds bounded planning range')
        while low<high:
            mid=(low+high)//2
            if power(mid)>=target_power: high=mid
            else: low=mid+1
        n=low;n2=math.ceil(n*ratio)
        scenarios.append({'standardized_effect':effect,'analyzable_units_group1_or_pairs':n,'analyzable_units_group2':n2 if design=='independent' else None,'recruit_group1_or_pairs':math.ceil(n/(1-attrition)),'recruit_group2':math.ceil(n2/(1-attrition)) if design=='independent' else None,'achieved_model_power':power(n)})
    return {'success':True,'state':'prospective_planning','design':design,'alpha':alpha,'target_power':target_power,'ratio':ratio,'attrition':attrition,'scenarios':scenarios,'references':{'power':REFERENCES['power']},'limitations':['Independent design assumes a common population SD; this is not an exact Welch power calculation.','Paired effect is mean difference divided by SD of differences, not marginal SD.','No clustered, survival, multiple-endpoint or RNA-seq power model is implied.','Effects must come from scientific targets or external evidence; observed post-hoc power is not supported.']}


def meta_analyze_effects(studies: list, effect_scale: str, contrast: str, method: str = 'random_dl') -> dict:
    """Pool compatible independent study estimates with fixed or DerSimonian-Laird weights, heterogeneity and leave-one-out sensitivity."""
    from compute_policy import require_local
    require_local()
    from scipy.stats import norm,chi2
    if method not in {'fixed','random_dl'} or effect_scale not in {'mean_difference','standardized_mean_difference','log_odds_ratio','log_risk_ratio','log_hazard_ratio'} or not contrast or not 2<=len(studies)<=100: raise ValueError('Declare a compatible scale, contrast and 2..100 independent studies')
    ids=[s.get('study_id') for s in studies];cohorts=[s.get('cohort_id') for s in studies]
    if any(not isinstance(x,str) or not x for x in ids+cohorts) or len(set(ids))!=len(ids) or len(set(cohorts))!=len(cohorts): raise ValueError('Studies and cohort IDs must be distinct; overlapping cohorts need another model')
    values=[_finite(s['effect']) for s in studies];se=[_finite(s['standard_error']) for s in studies]
    if any(x<=0 for x in se) or any(s.get('effect_scale')!=effect_scale or s.get('contrast')!=contrast for s in studies): raise ValueError('Positive standard errors and matching scale/direction are required')
    def pool(y,s):
        w=[1/x**2 for x in s];sw=sum(w);fixed=sum(a*b for a,b in zip(w,y))/sw
        q=sum(a*(b-fixed)**2 for a,b in zip(w,y));df=len(y)-1;c=sw-sum(x*x for x in w)/sw
        tau=max(0.,(q-df)/c) if df and c>0 and method=='random_dl' else 0.
        ww=[1/(x*x+tau) for x in s];estimate=sum(a*b for a,b in zip(ww,y))/sum(ww);error=math.sqrt(1/sum(ww))
        return {'effect':estimate,'standard_error':error,'ci95':[estimate-1.95996398454*error,estimate+1.95996398454*error],'pvalue':float(2*norm.sf(abs(estimate/error))),'Q':q,'Q_df':df,'Q_pvalue':float(chi2.sf(q,df)) if df else None,'I2_percent':max(0.,(q-df)/q)*100 if q>0 and df else 0.,'tau2':tau}
    result=pool(values,se)
    return {'success':True,'method':method,'effect_scale':effect_scale,'contrast':contrast,'pooled':result,'leave_one_out':[{'excluded':ids[i],**pool(values[:i]+values[i+1:],se[:i]+se[i+1:])} for i in range(len(ids))],'limitations':['Caller declares compatibility and absence of cohort overlap; IDs alone cannot prove it.','DL tau-squared and normal intervals may be unreliable with few studies or high heterogeneity; consider REML/Hartung-Knapp sensitivity.','No publication-bias absence, mechanism or causal effect is established.','Do not pool odds ratios, risk ratios or hazard ratios on the original ratio scale.']}


def audit_prediction_split(training_units: list, validation_units: list, preprocessing_fit_units: list, tuning_units: list = None) -> dict:
    """Check independent-unit overlap and preprocessing/tuning leakage before interpreting prediction performance."""
    groups={'training':training_units,'validation':validation_units,'preprocessing_fit':preprocessing_fit_units,'tuning':tuning_units or []}
    if any(not isinstance(v,list) or any(not isinstance(x,str) or not x for x in v) for v in groups.values()) or not training_units or not validation_units: raise ValueError('Provide explicit nonempty training and validation unit lists')
    train,val,prep,tune=(set(groups[k]) for k in ['training','validation','preprocessing_fit','tuning'])
    issues=[]
    if train&val: issues.append('training_validation_unit_overlap')
    if prep-train: issues.append('preprocessing_fit_outside_training')
    if tune&val: issues.append('validation_used_for_tuning')
    if tune-train: issues.append('tuning_outside_training')
    import hashlib,json
    fingerprints={k:hashlib.sha256(json.dumps(sorted(set(v)),ensure_ascii=False,separators=(',',':')).encode()).hexdigest() for k,v in groups.items()}
    return {'success':True,'leakage_gate_pass':not issues,'issues':issues,'unit_set_hashes':fingerprints,'unique_units':{k:len(set(v)) for k,v in groups.items()},'limitations':['Provided IDs do not detect mislabeled donors, related individuals, batch/site leakage or feature leakage.','Hyperparameter selection needs inner folds; external validation must remain untouched.','This is a split audit, not performance evaluation or model validation.']}


def fit_statistical_model(path: str, outcome: str, predictors: dict, context: dict, model: str = 'linear', cluster_key: str = '', unit_key: str = '', exposure_key: str = '', interactions: list = None) -> dict:
    """Fit bounded OLS HC3, binary logistic, Poisson or random-intercept linear models using explicit numeric/categorical predictors and QC."""
    from compute_policy import require_local
    from transcriptomics_ext import _context,_folder,_finish
    from workflow_ext import _table
    require_local();_context(context)
    import numpy as np
    import pandas as pd
    import statsmodels.api as sm
    h,rows=_table(path,20000000)
    if model not in {'linear','logistic','poisson','mixed_linear'} or not isinstance(predictors,dict) or not 1<=len(predictors)<=20 or not 10<=len(rows)<=10000: raise ValueError('Use a supported model and bounded explicit predictors/data')
    if not unit_key or unit_key not in h or outcome not in h or outcome in predictors or not set(predictors)<=set(h) or any(v not in {'numeric','categorical'} for v in predictors.values()): raise ValueError('Declare outcome, independent unit and predictor types')
    frame=pd.DataFrame(rows);audit=audit_statistical_dataset(path,unit_key,[outcome],required_keys=list(predictors)+([cluster_key] if cluster_key else []),repeated=model=='mixed_linear' or bool(cluster_key))
    if not audit['qc_gate_pass'] or any(audit['missing'].values()): raise ValueError('Dataset QC failed or missing values require a separately specified strategy')
    import re
    if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,40}',key) for key in predictors): raise ValueError('Use simple predictor column names')
    columns={};encodings={};groups={}
    for key,kind in predictors.items():
        if kind=='numeric': columns[key]=[_finite(x) for x in frame[key]];groups[key]=[key]
        else:
            levels=sorted(frame[key].unique())
            if not 2<=len(levels)<=30: raise ValueError('Categorical predictors require 2..30 levels')
            encodings[key]={'reference':levels[0],'levels':levels}
            groups[key]=[]
            for level in levels[1:]:
                name=key+'['+level+']';columns[name]=(frame[key]==level).astype(float);groups[key].append(name)
    for pair in interactions or []:
        if not isinstance(pair,list) or len(pair)!=2 or pair[0]==pair[1] or not set(pair)<=set(predictors): raise ValueError('Declare interactions between distinct predictors')
        for a in groups[pair[0]]:
            for b in groups[pair[1]]:
                name=a+':'+b
                if name in columns: raise ValueError('Duplicate interaction coefficient')
                columns[name]=np.asarray(columns[a])*np.asarray(columns[b])
    x=pd.DataFrame(columns,dtype=float);x.insert(0,'Intercept',1.);y=np.array([_finite(v) for v in frame[outcome]])
    if np.linalg.matrix_rank(x)!=x.shape[1] or len(y)-x.shape[1]<5 or np.var(y)==0: raise ValueError('Confounded, saturated or constant-outcome model')
    offset=None
    if exposure_key:
        if model!='poisson' or exposure_key not in h: raise ValueError('Exposure offset is supported only for a declared Poisson model')
        exposure=np.array([_finite(v) for v in frame[exposure_key]])
        if (exposure<=0).any(): raise ValueError('Exposure must be positive')
        offset=np.log(exposure)
    folder=_folder('statistical_model')
    if cluster_key and cluster_key not in h: raise ValueError('Missing cluster column')
    if cluster_key:
        nclusters=frame[cluster_key].nunique()
        if nclusters<10: raise ValueError('This adapter requires at least ten clusters; small-cluster inference needs a separate method')
        if frame.groupby(unit_key)[cluster_key].nunique().max()>1: raise ValueError('Independent units cross declared clusters')
    elif model=='mixed_linear': raise ValueError('Random-intercept model requires a cluster key')
    covariance={'cov_type':'cluster','cov_kwds':{'groups':frame[cluster_key]}} if cluster_key else {'cov_type':'HC3'}
    if model=='linear': fitted=sm.OLS(y,x).fit(**covariance)
    elif model=='logistic':
        if set(y)!={0.,1.} or min(sum(y==0),sum(y==1))<10: raise ValueError('Binary model needs both classes and at least ten observations in each; sparse-event inference is unsupported')
        import warnings
        from statsmodels.tools.sm_exceptions import PerfectSeparationWarning
        with warnings.catch_warnings():
            warnings.filterwarnings('error',category=PerfectSeparationWarning)
            fitted=sm.GLM(y,x,family=sm.families.Binomial()).fit(**covariance)
    elif model=='poisson':
        if (y<0).any() or (y!=np.floor(y)).any() or y.sum()==0: raise ValueError('Poisson requires nonnegative integer counts and events')
        fitted=sm.GLM(y,x,family=sm.families.Poisson(),offset=offset).fit(**covariance)
    else: fitted=sm.MixedLM(y,x,groups=frame[cluster_key]).fit(reml=True,method='lbfgs',maxiter=200)
    if hasattr(fitted,'converged') and not fitted.converged: raise ValueError('Model did not converge; no successful inference receipt')
    if not np.isfinite(fitted.params).all() or not np.isfinite(fitted.bse).all() or np.max(np.abs(fitted.params))>1e6: raise ValueError('Unstable parameter estimate; inspect separation or model fit')
    if not np.isfinite(fitted.pvalues).all(): raise ValueError('Nonfinite coefficient tests; review boundary or model degeneracy')
    ci=fitted.conf_int()
    pd.DataFrame({'estimate':fitted.params,'standard_error':fitted.bse,'ci95_low':ci.iloc[:,0],'ci95_high':ci.iloc[:,1],'pvalue':fitted.pvalues}).to_csv(folder/'coefficients.csv')
    x.to_csv(folder/'design_matrix.csv',index=False)
    pd.DataFrame({'observed':y,'fitted':fitted.fittedvalues,'residual':y-np.asarray(fitted.fittedvalues)}).to_csv(folder/'diagnostics.csv',index=False)
    diagnostics={'design_condition_number':float(np.linalg.cond(x)),'outcome_variance':float(np.var(y))}
    if model=='poisson': diagnostics['pearson_dispersion']=float(np.sum(fitted.resid_pearson**2)/fitted.df_resid)
    return _finish(folder,{'workflow':'statistical_model','model':model,'covariance':'random_intercept_REML' if model=='mixed_linear' else 'cluster' if cluster_key else 'HC3','encodings':encodings,'interactions':interactions or [],'exposure_offset':exposure_key or None,'qc':audit,'diagnostics':diagnostics,'context':context,'limitations':['No formula strings are evaluated; only declared main effects and interactions are fitted.','No missing values are automatically dropped or imputed.','Logistic coefficients are log odds and Poisson coefficients log rates; interpretation needs the declared exposure design.','Poisson overdispersion needs review; this adapter does not silently switch models.','Random-intercept variance parameters are not ordinary exposure effects; asymptotic intervals require review.','Model fit and robust covariance do not prove causality or correct functional form.']})


from transcriptomics_ext import _workflow
fit_statistical_model=_workflow(fit_statistical_model)
