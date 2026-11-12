"""Actual server-only nested/group-aware training. All learned preprocessing stays in folds."""
from runtime import write

def estimator(name,task,seed,threads):
    from sklearn import linear_model,ensemble,svm,neighbors,naive_bayes,dummy,neural_network
    classify=task=='classification'
    constructors={
      'elastic_net':lambda:linear_model.LogisticRegression(penalty='elasticnet',solver='saga',l1_ratio=.5,max_iter=10000,random_state=seed) if classify else linear_model.ElasticNet(max_iter=10000,random_state=seed),
      'ridge':lambda:linear_model.LogisticRegression(max_iter=10000,random_state=seed) if classify else linear_model.Ridge(),
      'lasso':lambda:linear_model.LogisticRegression(penalty='l1',solver='saga',max_iter=10000,random_state=seed) if classify else linear_model.Lasso(max_iter=10000,random_state=seed),
      'svm':lambda:svm.SVC(probability=False,random_state=seed) if classify else svm.SVR(),
      'random_forest':lambda:ensemble.RandomForestClassifier(n_estimators=300,n_jobs=threads,random_state=seed) if classify else ensemble.RandomForestRegressor(n_estimators=300,n_jobs=threads,random_state=seed),
      'extra_trees':lambda:ensemble.ExtraTreesClassifier(n_estimators=300,n_jobs=threads,random_state=seed) if classify else ensemble.ExtraTreesRegressor(n_estimators=300,n_jobs=threads,random_state=seed),
      'hist_gradient_boosting':lambda:ensemble.HistGradientBoostingClassifier(random_state=seed,early_stopping=False) if classify else ensemble.HistGradientBoostingRegressor(random_state=seed,early_stopping=False),
      'gradient_boosting':lambda:ensemble.GradientBoostingClassifier(random_state=seed) if classify else ensemble.GradientBoostingRegressor(random_state=seed),
      'adaboost':lambda:ensemble.AdaBoostClassifier(random_state=seed) if classify else ensemble.AdaBoostRegressor(random_state=seed),
      'knn':lambda:neighbors.KNeighborsClassifier() if classify else neighbors.KNeighborsRegressor(),
      'mlp':lambda:neural_network.MLPClassifier(hidden_layer_sizes=(128,64),max_iter=500,early_stopping=False,random_state=seed) if classify else neural_network.MLPRegressor(hidden_layer_sizes=(128,64),max_iter=500,early_stopping=False,random_state=seed),
      'baseline':lambda:dummy.DummyClassifier(strategy='prior') if classify else dummy.DummyRegressor(strategy='mean')}
    if name=='naive_bayes':
        if not classify:raise ValueError('Naive Bayes is classification-only')
        return naive_bayes.GaussianNB()
    if name=='xgboost':
        import xgboost
        return xgboost.XGBClassifier(n_jobs=threads,random_state=seed) if classify else xgboost.XGBRegressor(n_jobs=threads,random_state=seed)
    if name=='lightgbm':
        import lightgbm
        return lightgbm.LGBMClassifier(n_jobs=threads,random_state=seed,verbosity=-1) if classify else lightgbm.LGBMRegressor(n_jobs=threads,random_state=seed,verbosity=-1)
    if name=='catboost':
        import catboost
        return catboost.CatBoostClassifier(thread_count=threads,random_seed=seed,verbose=False,allow_writing_files=False) if classify else catboost.CatBoostRegressor(thread_count=threads,random_seed=seed,verbose=False,allow_writing_files=False)
    if name not in constructors:raise ValueError('Unsupported fixed model ID')
    return constructors[name]()

def analyze(inputs,p,out,mode):
    import numpy as np
    import pandas as pd
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler,LabelEncoder
    from sklearn.feature_selection import SelectKBest,f_classif,f_regression
    from sklearn.model_selection import StratifiedGroupKFold,GroupKFold,GridSearchCV,ParameterGrid
    from sklearn import metrics
    from sklearn.linear_model import LogisticRegression
    data=pd.read_csv(inputs['table'],sep='\t')
    features=p['features'];unit=p['unit_key'];outcome=p['outcome'];group=p.get('split_group_key',unit)
    if not features or len(features)!=len(set(features)) or set(features)&{unit,outcome,group,p['sample_key']}:
        raise ValueError('Explicit distinct feature columns; no identity/outcome columns in features')
    if data[p['sample_key']].duplicated().any() or data[unit].duplicated().any():
        raise ValueError('Cohort backend requires one prespecified record per independent unit; use longitudinal model for repeats')
    if data[[unit,outcome,group,p['sample_key']]].isna().any().any():raise ValueError('Missing identity, group or outcome')
    X=data[features].apply(pd.to_numeric,errors='raise')
    if np.isinf(X.to_numpy()).any():raise ValueError('Infinite features; missing values remain missing until training-fold imputation')
    uid=data[unit].astype(str);groups=data[group].astype(str)
    partitions={k:set(map(str,p[k+'_units'])) for k in ('train','calibration','test')}
    if any(partitions[a]&partitions[b] for a,b in (('train','test'),('train','calibration'),('calibration','test'))):raise ValueError('Independent-unit leakage')
    if set.union(*partitions.values())!=set(uid) or not partitions['train'] or not partitions['test']:raise ValueError('Account for every unit and lock a nonempty test set')
    masks={k:uid.isin(v).to_numpy() for k,v in partitions.items()}
    if any(set(groups[masks[a]])&set(groups[masks[b]]) for a,b in (('train','test'),('train','calibration'),('calibration','test'))):raise ValueError('Family/cohort grouping leaks across partitions')
    train=np.flatnonzero(masks['train']);test=np.flatnonzero(masks['test']);cal=np.flatnonzero(masks['calibration'])
    if p.get('shap') is not None:
        from shap_native import contract as shap_contract
        shap_contract(p['shap'],uid.iloc[train].tolist(),uid.iloc[test].tolist(),features)
        if not set(p['shap']['models'])<=set(p['models']):raise ValueError('Requested SHAP model is not in this actual fitted comparison')
    classification=p['task']=='classification'
    if p['task'] not in {'classification','regression'}:raise ValueError('Select classification or regression; survival is a separate backend')
    if classification:
        encoder=LabelEncoder().fit(data.iloc[train][outcome].astype(str));y=encoder.transform(data[outcome].astype(str))
        if len(encoder.classes_)<2:raise ValueError('Training set has fewer than two classes')
    else:
        y=pd.to_numeric(data[outcome],errors='raise').to_numpy()
        if not np.isfinite(y).all():raise ValueError('Nonfinite outcome')
    seed=p['seed'];outer_n=p['outer_folds'];inner_n=p['inner_folds'];threads=p['threads']
    if type(threads) is not int or threads<1 or any(type(n) is not int or n<2 for n in (outer_n,inner_n)):raise ValueError('Explicit positive thread/fold budgets')
    if X.iloc[train].isna().all().any():raise ValueError('Training-all-missing feature must be explicitly resolved, never filled from test data')
    splitter=lambda n:StratifiedGroupKFold(n_splits=n,shuffle=True,random_state=seed) if classification else GroupKFold(n_splits=n)
    def checked_splits(indices,n):
        splits=list(splitter(n).split(X.iloc[indices],y[indices],groups.iloc[indices]))
        for a,b in splits:
            if set(groups.iloc[indices[a]])&set(groups.iloc[indices[b]]):raise ValueError('CV group leakage')
            if classification and (len(set(y[indices[a]]))!=len(encoder.classes_) or len(set(y[indices[b]]))!=len(encoder.classes_)):
                raise ValueError('CV fold lacks a class; change the prespecified design, do not silently reduce folds')
        return splits
    def pipeline(name):
        k=p['select_k']
        if k!='all' and (type(k) is not int or not 1<=k<=len(features)):raise ValueError('Invalid fold-contained selection size')
        return Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True)),('scale',StandardScaler()),
          ('select',SelectKBest(f_classif if classification else f_regression,k=k)),('model',estimator(name,p['task'],seed,threads))])
    scoring='balanced_accuracy' if classification else 'neg_root_mean_squared_error'
    def fit_search(name,idx):
        grid=p['models'][name]
        if any(not k.startswith('model__') for k in grid):raise ValueError('Only explicitly selected estimator hyperparameters may be searched')
        if len(ParameterGrid(grid))>p['max_candidates']:raise ValueError('Search exceeds declared model budget')
        search=GridSearchCV(pipeline(name),grid,scoring=scoring,cv=checked_splits(idx,inner_n),n_jobs=1,error_score='raise',refit=True)
        search.fit(X.iloc[idx],y[idx]);return search
    def probabilities(model,frame):
        if hasattr(model,'predict_proba'):return model.predict_proba(frame)
        return None
    def summarize(truth,pred,prob):
        if classification:
            report={'balanced_accuracy':float(metrics.balanced_accuracy_score(truth,pred)),
                    'macro_f1':float(metrics.f1_score(truth,pred,average='macro',zero_division=0)),
                    'confusion_matrix':metrics.confusion_matrix(truth,pred,labels=np.arange(len(encoder.classes_))).tolist()}
            if prob is not None:
                report['log_loss']=float(metrics.log_loss(truth,prob,labels=np.arange(len(encoder.classes_))))
                if len(encoder.classes_)==2 and len(set(truth))==2:
                    report.update(roc_auc=float(metrics.roc_auc_score(truth,prob[:,1])),pr_auc=float(metrics.average_precision_score(truth,prob[:,1])),
                                  brier=float(metrics.brier_score_loss(truth,prob[:,1])))
            return report
        return {'mae':float(metrics.mean_absolute_error(truth,pred)),
                'rmse':float(np.sqrt(metrics.mean_squared_error(truth,pred))),
                'r2':float(metrics.r2_score(truth,pred)) if len(truth)>1 else None}
    models=p['models']
    if 'baseline' not in models:raise ValueError('Include a same-split baseline')
    if len(models)>20:raise ValueError('Select a bounded model comparison, not every model blindly')
    results={};predictions=[];folds=[];fitted={};curves=[];selections=[];histories=[];shap_outputs=[]
    for name in models:
        outer=[]
        for fold,(a,b) in enumerate(checked_splits(train,outer_n)):
            fit_idx=train[a];val_idx=train[b];search=fit_search(name,fit_idx);model=search.best_estimator_
            pred=model.predict(X.iloc[val_idx]);prob=probabilities(model,X.iloc[val_idx])
            outer.append(summarize(y[val_idx],pred,prob))
            selections.append({'model':name,'fold':fold,'selected_features':model[:-1].get_feature_names_out(features).tolist()})
            folds.append({'model':name,'fold':fold,'train_units':uid.iloc[fit_idx].tolist(),'validation_units':uid.iloc[val_idx].tolist(),'best_parameters':search.best_params_})
            predictions.extend({'sample_id':str(data.iloc[i][p['sample_key']]),'unit_id':uid.iloc[i],'model':name,'partition':'outer_cv','fold':fold,
                                'observed':float(y[i]),'predicted':float(pred[j])} for j,i in enumerate(val_idx))
        search=fit_search(name,train);model=search.best_estimator_;pred=model.predict(X.iloc[test]);prob=probabilities(model,X.iloc[test])
        calibration='none'
        if p.get('probability_calibration')=='sigmoid':
            if not classification or not len(cal):raise ValueError('Calibration requires separate calibration units')
            if len(set(y[cal]))!=len(encoder.classes_):raise ValueError('Calibration set lacks a class')
            def scores(idx):
                if hasattr(model,'decision_function'):
                    z=model.decision_function(X.iloc[idx]);return np.asarray(z).reshape(len(idx),-1)
                return np.log(np.clip(model.predict_proba(X.iloc[idx]),1e-12,1))
            calibrator=LogisticRegression(max_iter=10000).fit(scores(cal),y[cal])
            prob=calibrator.predict_proba(scores(test));pred=calibrator.predict(scores(test));calibration='separate_unit_sigmoid'
        interval=None
        if p.get('conformal_coverage'):
            if classification or not len(cal):raise ValueError('Regression split-conformal intervals require separate calibration units')
            coverage=p['conformal_coverage']
            if not 0<coverage<1:raise ValueError('Invalid coverage')
            residual=np.abs(y[cal]-model.predict(X.iloc[cal]));q=np.ceil((len(cal)+1)*coverage)/len(cal)
            if q>1:raise ValueError('Too few calibration units for requested finite-sample coverage')
            interval=float(np.quantile(residual,q,method='higher'))
        report={'outer_cv':outer,'heldout_test':summarize(y[test],pred,prob),'best_parameters':search.best_params_,'calibration':calibration,
                'learning_unit':unit,'model_selection_data':'outer_cv_only; never select by heldout test','checkpoint_resume':'not_supported; fresh new run required'}
        boot=[];rng=np.random.default_rng(seed)
        for _ in range(p.get('bootstrap_repeats',0)):
            draw=rng.integers(0,len(test),size=len(test))
            if classification and len(set(y[test][draw]))!=len(encoder.classes_):continue
            stat=summarize(y[test][draw],np.asarray(pred)[draw],None if prob is None else prob[draw])
            boot.append({k:v for k,v in stat.items() if isinstance(v,(int,float))})
        report['test_bootstrap']={'requested':p.get('bootstrap_repeats',0),'valid':len(boot),'unit':unit,
           'scope':'Conditional on fitted model and locked test cohort; not training-procedure uncertainty',
           'percentile_95':{k:np.quantile([r[k] for r in boot],[.025,.975]).tolist() for k in boot[0]} if boot else None}
        if classification and prob is not None and len(encoder.classes_)==2 and len(set(y[test]))==2:
            from sklearn.calibration import calibration_curve
            fpr,tpr,thr=metrics.roc_curve(y[test],prob[:,1])
            curves.extend({'model':name,'kind':'roc','x':float(a),'y':float(b),'threshold':float(c) if np.isfinite(c) else None} for a,b,c in zip(fpr,tpr,thr))
            precision,recall,thr=metrics.precision_recall_curve(y[test],prob[:,1])
            curves.extend({'model':name,'kind':'precision_recall','x':float(a),'y':float(b),'threshold':None} for a,b in zip(recall,precision))
            observed,estimated=calibration_curve(y[test],prob[:,1],n_bins=p.get('calibration_bins',5),strategy='quantile')
            curves.extend({'model':name,'kind':'calibration','x':float(a),'y':float(b),'threshold':None} for a,b in zip(estimated,observed))
        for epoch,loss in enumerate(getattr(model['model'],'loss_curve_',[])):histories.append({'model':name,'epoch':epoch,'loss':float(loss)})
        results[name]=report;fitted[name]=model
        if p.get('shap') is not None and name in p['shap']['models']:
            from shap_native import explain as native_shap
            cfg=p['shap'];kind=cfg['output']
            if classification:
                class_label=cfg.get('class_label')
                if class_label not in encoder.classes_:raise ValueError('SHAP must declare the actual encoded class label')
                cls=int(np.flatnonzero(encoder.classes_==class_label)[0])
                if kind=='probability':
                    if calibration=='separate_unit_sigmoid':
                        def explain_predict(frame):
                            z=np.asarray(model.decision_function(frame)).reshape(len(frame),-1) if hasattr(model,'decision_function') else np.log(np.clip(model.predict_proba(frame),1e-12,1))
                            return calibrator.predict_proba(z)[:,cls]
                    elif hasattr(model,'predict_proba'):
                        def explain_predict(frame):return model.predict_proba(frame)[:,cls]
                    else:raise ValueError('This native model has no probability output; do not relabel a margin as probability')
                elif kind=='decision_function' and hasattr(model,'decision_function') and len(encoder.classes_)==2:
                    def explain_predict(frame):return np.asarray(model.decision_function(frame))*(1 if cls==1 else -1)
                else:raise ValueError('Supported classification SHAP requires probability, or an explicit binary uncalibrated decision function')
            elif kind=='response':
                def explain_predict(frame):return model.predict(frame)
            else:raise ValueError('Regression SHAP uses response scale')
            shap_outputs.extend(native_shap(explain_predict,X,uid.tolist(),cfg,features,seed,out,name))
        for j,i in enumerate(test):
            row={'sample_id':str(data.iloc[i][p['sample_key']]),'unit_id':uid.iloc[i],'model':name,'partition':'locked_test',
                 'observed':float(y[i]),'predicted':float(pred[j])}
            if prob is not None:row.update({'probability_'+str(k):float(v) for k,v in enumerate(prob[j])})
            if interval is not None:row.update(lower=float(pred[j]-interval),upper=float(pred[j]+interval))
            predictions.append(row)
    pd.DataFrame(predictions).to_csv(out/'predictions.tsv',sep='\t',index=False)
    write(out/'metrics.json',results);write(out/'fold_membership.json',folds)
    write(out/'selection_stability.json',selections);write(out/'evaluation_curves.json',curves)
    write(out/'feature_contract.json',{'features':features,'classes':encoder.classes_.tolist() if classification else None,
         'all_learned_operations':'fit only within inner/outer training folds; calibration separate',
         'test_reuse_policy':'No model or threshold selection from test scores','scientific_validity':'not_established'})
    outputs=[(out/'predictions.tsv','predictions'),(out/'metrics.json','model_metrics'),(out/'fold_membership.json','split_provenance'),(out/'feature_contract.json','feature_contract'),
             (out/'selection_stability.json','selection_stability'),(out/'evaluation_curves.json','evaluation_curves')]
    outputs.extend(shap_outputs)
    if histories:
        pd.DataFrame(histories).to_csv(out/'training_history.tsv',sep='\t',index=False);outputs.append((out/'training_history.tsv','training_history'))
    if p.get('model_export')=='trusted_joblib':
        if p.get('allow_pickle_export') is not True:raise ValueError('Explicit private trusted-pickle export required')
        import joblib
        for name,model in fitted.items():
            if p.get('probability_calibration')=='sigmoid':raise ValueError('Calibrated artifact export must bind calibrator; this backend refuses incomplete export')
            joblib.dump(model,out/(name+'.joblib'));outputs.append((out/(name+'.joblib'),'model_artifact'))
        write(out/'model_artifact_warning.json',{'format':'trusted_pickle','load_untrusted':False,'automatic_load':False})
        outputs.append((out/'model_artifact_warning.json','model_security'))
    return outputs
