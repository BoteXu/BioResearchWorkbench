"""Descriptive, within-unit rerun comparisons. No inferential p-values are manufactured."""
from pathlib import Path
import csv

def compare(root,spec,variants):
    import numpy as np
    from scipy.stats import spearmanr
    def load(label):
        with (Path(root)/label/(spec['roles'][0]+'.tsv')).open(encoding='utf-8-sig',newline='') as f:
            data=list(csv.DictReader(f,delimiter='\t'))
        index={tuple(r[k] for k in spec['comparison_keys']):r for r in data}
        if len(index)!=len(data):raise ValueError('Duplicate comparison identities')
        return index
    base=load('primary');output=[];score=spec['comparison_score']
    for alt in variants:
        other=load(alt['label']);units=sorted({k[0] for k in base}|{k[0] for k in other})
        for unit in units:
            a={k:r for k,r in base.items() if k[0]==unit};b={k:r for k,r in other.items() if k[0]==unit};shared=sorted(set(a)&set(b))
            if not shared:raise ValueError('No comparable scientific identities after sensitivity rerun')
            x=np.array([float(a[k][score]) for k in shared]);y=np.array([float(b[k][score]) for k in shared])
            if not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('Nonfinite sensitivity scores')
            r=float(spearmanr(x,y).statistic) if len(x)>2 and np.ptp(x)>0 and np.ptp(y)>0 else None
            signed=spec.get('signed_score',False);center=spec.get('score_null',0)
            if signed:direction=float(np.mean(np.sign(x-center)==np.sign(y-center)))
            else:direction=None
            k=min(20,len(shared));ix=set(np.argsort(abs(x-center))[-k:]);iy=set(np.argsort(abs(y-center))[-k:])
            from return_binding import comparison_scope
            kind=comparison_scope(alt['parameters'],spec)
            output.append({'variant':alt['label'],'unit_id':unit,'shared_features':len(shared),'primary_features':len(a),'alternate_features':len(b),'primary_missing_in_alternate':len(set(a)-set(b)),'alternate_new_features':len(set(b)-set(a)),'mean_absolute_score_change':float(abs(x-y).mean()),'spearman_descriptive':r,'direction_agreement':direction,'top_k':k,'top_k_Jaccard':len(ix&iy)/len(ix|iy),'comparison_score':score,'comparison_scope':kind,'biological_replication_established':False,'scientific_robustness_established':False})
    return output
