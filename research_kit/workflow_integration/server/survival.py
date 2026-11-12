"""Existing scikit-survival backends; independent-unit split and censoring-aware evaluation."""
from runtime import write

def analyze(inputs,p,out,mode):
    import numpy as np
    import pandas as pd
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import GroupKFold,GridSearchCV,ParameterGrid
    from sksurv.util import Surv
    from sksurv.linear_model import CoxPHSurvivalAnalysis,CoxnetSurvivalAnalysis
    from sksurv.ensemble import RandomSurvivalForest,GradientBoostingSurvivalAnalysis
    from sksurv.svm import FastSurvivalSVM
    from sksurv.metrics import concordance_index_censored,concordance_index_ipcw,cumulative_dynamic_auc
    data=pd.read_csv(inputs['table'],sep='\t');unit=p['unit_key'];group=p.get('split_group_key',unit)
    if p['competing_risks']!='none' or p.get('left_truncation') is not False:raise ValueError('Dedicated competing-risk/left-truncation model required before fitting')
    if data[unit].duplicated().any() or data[[unit,group,p['event_key'],p['time_key']]].isna().any().any():raise ValueError('One complete first-event record per independent unit')
    if not set(data[p['event_key']])<={0,1} or (data[p['time_key']]<=0).any() or not np.isfinite(data[p['time_key']]).all():raise ValueError('Invalid event/censoring/time data')
    features=p['features']
    if set(features)&{unit,group,p['event_key'],p['time_key']}:raise ValueError('Outcome/identity leakage into predictors')
    X=data[features].apply(pd.to_numeric,errors='raise');y=Surv.from_arrays(data[p['event_key']].astype(bool),data[p['time_key']])
    uid=data[unit].astype(str);groups=data[group].astype(str);train=np.flatnonzero(uid.isin(p['train_units']));test=np.flatnonzero(uid.isin(p['test_units']))
    if len(set(train)&set(test)) or len(train)+len(test)!=len(data) or set(groups.iloc[train])&set(groups.iloc[test]):raise ValueError('Incomplete/overlapping survival split')
    if not len(train) or not len(test) or len(set(features))!=len(features):raise ValueError('Nonempty split and unique features required')
    models={'coxph':lambda:CoxPHSurvivalAnalysis(),'cox_elasticnet':lambda:CoxnetSurvivalAnalysis(l1_ratio=.5,fit_baseline_model=True),
       'random_survival_forest':lambda:RandomSurvivalForest(n_estimators=300,n_jobs=p['threads'],random_state=p['seed']),
       'gradient_survival':lambda:GradientBoostingSurvivalAnalysis(random_state=p['seed']),
       'survival_svm':lambda:FastSurvivalSVM(random_state=p['seed'])}
    results={};predictions=[];fold_records=[]
    def splits(indices,n):
        s=list(GroupKFold(n_splits=n).split(X.iloc[indices],groups=groups.iloc[indices]))
        for a,b in s:
            if data.iloc[indices[a]][p['event_key']].sum()==0 or data.iloc[indices[b]][p['event_key']].sum()==0:raise ValueError('Survival fold has no events')
        return s
    for name,grid in p['models'].items():
        if name not in models or len(ParameterGrid(grid))>p['max_candidates']:raise ValueError('Unknown model or excessive search')
        def search(indices):
            pipe=Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True)),('scale',StandardScaler()),('model',models[name]())])
            fit=GridSearchCV(pipe,grid,cv=splits(indices,p['inner_folds']),n_jobs=1,error_score='raise').fit(X.iloc[indices],y[indices]);return fit
        outer=[]
        for fold,(a,b) in enumerate(splits(train,p['outer_folds'])):
            tr=train[a];va=train[b];fit=search(tr);risk=fit.predict(X.iloc[va]);c=concordance_index_censored(data.iloc[va][p['event_key']].astype(bool),data.iloc[va][p['time_key']],risk)[0]
            outer.append(float(c));fold_records.append({'model':name,'fold':fold,'train_units':uid.iloc[tr].tolist(),'validation_units':uid.iloc[va].tolist()})
        fit=search(train);risk=fit.predict(X.iloc[test]);event=data.iloc[test][p['event_key']].astype(bool);time=data.iloc[test][p['time_key']]
        met={'harrell_c':float(concordance_index_censored(event,time,risk)[0]),'outer_cv_c':outer,'best_parameters':fit.best_params_}
        try:
            met['uno_c']=float(concordance_index_ipcw(y[train],y[test],risk,tau=p['evaluation_horizon'])[0])
            auc,mean_auc=cumulative_dynamic_auc(y[train],y[test],risk,np.asarray(p['evaluation_times']))
            met['dynamic_auc']=auc.tolist();met['mean_dynamic_auc']=float(mean_auc)
        except ValueError as exc:met['ipcw_state']='not_estimable: '+str(exc)
        results[name]=met
        predictions.extend({'unit_id':uid.iloc[i],'model':name,'event':int(data.iloc[i][p['event_key']]),'time':float(data.iloc[i][p['time_key']]),'risk':float(risk[j])} for j,i in enumerate(test))
    pd.DataFrame(predictions).to_csv(out/'survival_predictions.tsv',sep='\t',index=False)
    write(out/'survival_metrics.json',results);write(out/'fold_membership.json',fold_records)
    write(out/'survival_contract.json',{'time_unit':p['time_unit'],'event_definition':p['event_definition'],'competing_risks':p['competing_risks'],
        'time_origin':p['time_origin'],'left_truncation':'unsupported','missing_outcomes_imputed':False,
        'ph_assumption':'Cox scientific adoption requires separate PH/sensitivity diagnostics',
        'calibration':'survival probability calibration/Brier score requires a prespecified supported survival-function model; risk scores are not probabilities'})
    return [(out/'survival_predictions.tsv','predictions'),(out/'survival_metrics.json','model_metrics'),(out/'fold_membership.json','split_provenance'),(out/'survival_contract.json','feature_contract')]
