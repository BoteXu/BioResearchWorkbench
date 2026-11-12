"""Inductive graph-level GCN/GAT/GraphSAGE training on explicit independent-unit graphs."""
from runtime import read,write

def analyze(inputs,p,out,mode):
    import numpy as np
    import pandas as pd
    import torch
    import torch.nn.functional as F
    from torch_geometric.data import Data
    from torch_geometric.loader import DataLoader
    from torch_geometric.nn import GCNConv,GATConv,SAGEConv,global_mean_pool
    from sklearn.preprocessing import StandardScaler,LabelEncoder
    from sklearn.metrics import balanced_accuracy_score,f1_score,roc_auc_score,log_loss
    if p['validation_scheme']!='locked_three_way' or p['task']!='graph_classification':raise ValueError('This adapter is inductive graph classification with explicit train/tune/test, not a transductive node model')
    records=read(inputs['graphs'])
    if not records or len({r['unit_id'] for r in records})!=len(records):raise ValueError('Exactly one graph per independent biological unit')
    partitions={k:[r for r in records if r['partition']==k] for k in ('train','tune','test')}
    if sum(map(len,partitions.values()))!=len(records) or any(not v for v in partitions.values()):raise ValueError('Explicit complete nonempty partitions required')
    groups={k:{r['split_group'] for r in v} for k,v in partitions.items()}
    if any(groups[a]&groups[b] for a,b in (('train','tune'),('train','test'),('tune','test'))):raise ValueError('Graph family/cohort leakage')
    scaler=StandardScaler().fit(np.concatenate([r['node_features'] for r in partitions['train']],axis=0))
    encoder=LabelEncoder().fit([r['outcome'] for r in partitions['train']])
    for key in partitions:
        if set(r['outcome'] for r in partitions[key])!=set(encoder.classes_):raise ValueError('A graph partition lacks a class')
    graphs={}
    for key,items in partitions.items():
        graphs[key]=[]
        for record in items:
            x=np.asarray(record['node_features'],dtype=float);edge=np.asarray(record['edge_index'],dtype=int)
            if x.ndim!=2 or x.shape[1]!=len(p['node_feature_names']) or not np.isfinite(x).all() or edge.ndim!=2 or edge.shape[0]!=2 or edge.size==0 or edge.min()<0 or edge.max()>=len(x):raise ValueError('Invalid graph feature/edge axes')
            graphs[key].append(Data(x=torch.tensor(scaler.transform(x),dtype=torch.float32),edge_index=torch.tensor(edge,dtype=torch.long),
                              y=torch.tensor([int(encoder.transform([record['outcome']])[0])],dtype=torch.long)))
    class Network(torch.nn.Module):
        def __init__(self,architecture):
            super().__init__();conv={'gcn':GCNConv,'gat':GATConv,'graphsage':SAGEConv}[architecture]
            self.a=conv(len(p['node_feature_names']),p['hidden']);self.b=conv(p['hidden'],p['hidden']);self.head=torch.nn.Linear(p['hidden'],len(encoder.classes_))
        def forward(self,data):
            x=F.relu(self.a(data.x,data.edge_index));x=F.dropout(x,p['dropout'],training=self.training);x=F.relu(self.b(x,data.edge_index))
            return self.head(global_mean_pool(x,data.batch))
    device=torch.device(p['device'])
    def evaluate(model,key):
        model.eval();probs=[];truth=[]
        with torch.no_grad():
            for batch in DataLoader(graphs[key],batch_size=p['batch_size'],shuffle=False):
                batch=batch.to(device);probs.extend(torch.softmax(model(batch),dim=1).cpu().numpy().tolist());truth.extend(batch.y.cpu().numpy().tolist())
        prob=np.asarray(probs);pred=prob.argmax(axis=1)
        met={'balanced_accuracy':float(balanced_accuracy_score(truth,pred)),'macro_f1':float(f1_score(truth,pred,average='macro')),'log_loss':float(log_loss(truth,prob,labels=np.arange(len(encoder.classes_))))}
        if len(encoder.classes_)==2:met['roc_auc']=float(roc_auc_score(truth,prob[:,1]))
        return met,prob,truth
    histories=[];summaries=[];predictions=[]
    torch.set_num_threads(p['threads'])
    for architecture in p['architectures']:
        if architecture not in {'gcn','gat','graphsage'}:raise ValueError('Unknown fixed graph architecture')
        for seed in p['seeds']:
            torch.manual_seed(seed);model=Network(architecture).to(device);optimizer=torch.optim.Adam(model.parameters(),lr=p['learning_rate'],weight_decay=p['weight_decay'])
            best=None;best_loss=float('inf');stale=0;best_epoch=None
            for epoch in range(p['max_epochs']):
                model.train();loss_total=0;units=0
                for batch in DataLoader(graphs['train'],batch_size=p['batch_size'],shuffle=True):
                    batch=batch.to(device);optimizer.zero_grad();loss=F.cross_entropy(model(batch),batch.y);loss.backward();optimizer.step();loss_total+=float(loss.detach())*batch.num_graphs;units+=batch.num_graphs
                val,_,_=evaluate(model,'tune');histories.append({'architecture':architecture,'seed':seed,'epoch':epoch,'train_loss':loss_total/units,'tune_loss':val['log_loss']})
                if val['log_loss']<best_loss:
                    best_loss=val['log_loss'];best={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};best_epoch=epoch;stale=0
                else:stale+=1
                if stale>=p['patience']:break
            if best is None:raise ValueError('Graph training failed to yield a finite validated checkpoint')
            model.load_state_dict(best);met,prob,truth=evaluate(model,'test')
            summaries.append({'architecture':architecture,'seed':seed,'best_epoch':best_epoch,'tune_log_loss':best_loss,'locked_test':met})
            for i,record in enumerate(partitions['test']):predictions.append({'unit_id':record['unit_id'],'architecture':architecture,'seed':seed,'observed':truth[i],**{'probability_'+str(j):float(x) for j,x in enumerate(prob[i])}})
            if p.get('export_safetensors') is True:
                from safetensors.torch import save_file
                save_file(best,str(out/(architecture+'_'+str(seed)+'.safetensors')))
    pd.DataFrame(histories).to_csv(out/'training_history.tsv',sep='\t',index=False);pd.DataFrame(predictions).to_csv(out/'predictions.tsv',sep='\t',index=False)
    write(out/'metrics.json',summaries);write(out/'graph_contract.json',{'classes':encoder.classes_.tolist(),'node_features':p['node_feature_names'],
       'scaler_mean':scaler.mean_.tolist(),'scaler_scale':scaler.scale_.tolist(),'inductive':True,'split_units':{k:[r['unit_id'] for r in v] for k,v in partitions.items()},
       'test_used_for_early_stopping':False,'architecture_selection':'tune set only; reported test results must not be used to choose a winner',
       'resume':'not implemented; checkpoint is weights plus bound contract, not optimizer/RNG restart state'})
    outputs=[(out/'training_history.tsv','training_history'),(out/'predictions.tsv','predictions'),(out/'metrics.json','model_metrics'),(out/'graph_contract.json','feature_contract')]
    outputs += [(path,'model_artifact') for path in out.glob('*.safetensors')]
    return outputs
