"""Explicit synthetic display fixtures, not simulated biological analysis or reference results."""
import math,copy
from contracts import SCHEMA,digest
PAL={'Control':'#197F86','Treated':'#CF785E','B_cell':'#4674A5','T_cell':'#5C9279','Myeloid':'#AB8052','Missense':'#477EAE','Truncating':'#303F53','Amp':'#B68F38','Fusion':'#8B72A0'}
def example(kind,size='medium'):
    level={'small':0,'medium':1,'large':2}[size]
    s={'schema':SCHEMA,'kind':kind,'title':{'heatmap':'Coordinated expression and sample annotations','oncoprint':'Cohort alterations without losing overlapping events','spatial':'Spatial evidence at its recorded geometry','genome':'A locus viewed across complementary measurements','markers':'Cell identities and multi-marker evidence','interactive':'Linked cell identities and marker evidence','circos':'Genomic context with a readable linear companion','palette':'Colors evaluated in their actual visual roles'}[kind],'alt_text':'Synthetic software display example. Supplied values and identities are preserved; no biological evidence or new analysis.','provenance':{'source_id':'synthetic-display-fixture-v1','source_sha256':'0'*64,'value_unit':'supplied display units','independent_unit':'explicit synthetic donor; objects are not independent replicates','selection':'all identities in this frozen software fixture','transformations':'display mappings only; no model/normalization/clustering/density fit','synthetic':True},'layout':{'width_mm':178,'page_panels':6},'palette':copy.deepcopy(PAL)}
    if kind=='heatmap':
        nr=[6,12,24][level];nc=[6,12,30][level];rows=[f'Gene_{i+1:02}' for i in range(nr)];cols=[f'S{i+1:02}' for i in range(nc)]
        values=[[None if (i+j)%31==0 else round((((i*7+j*3)%19)-9)/3,2) for j in range(nc)] for i in range(nr)]
        tree=[]
        for i in range(0,nr-1,2):tree.extend([[1,i,.3,i],[.3,i,.3,i+1],[.3,i+1,1,i+1]])
        s['data']={'rows':rows,'columns':cols,'values':values,'limits':[-3,3],'center':0,'value_label':'Supplied standardized expression','row_groups':{r:('Control' if i<nr/2 else 'Treated') for i,r in enumerate(rows)},'column_groups':{c:('Control' if j<nc/2 else 'Treated') for j,c in enumerate(cols)},'row_bars':{'values':{r:((i*3)%9-4)/2 for i,r in enumerate(rows)},'limits':[-2,2],'label':'Supplied effect'},'column_bars':{'values':{c:40+(j*13)%60 for j,c in enumerate(cols)},'limits':[0,100],'label':'QC score'},'tree':{'leaf_order':rows,'segments':tree,'height_unit':'supplied scaled height; illustrative disconnected pairs'},'raster_cells':level==2}
    elif kind=='oncoprint':
        genes=[f'Driver_{i+1:02}' for i in range([5,8,14][level])];samples=[f'S{i+1:02}' for i in range([8,16,42][level])];events=['Missense','Truncating','Amp','Fusion'];cells=[]
        for i,g in enumerate(genes):
            for j,c in enumerate(samples):
                assayed=(i+j)%17!=0;ev=[] if not assayed or (i*3+j)%4 else [events[(i+j)%4]]
                if ev and (i+j)%3==0:ev.append(events[(i+j+1)%4])
                cells.append({'gene':g,'sample':c,'assayed':assayed,'events':ev})
        s['data']={'genes':genes,'samples':samples,'cells':cells,'sample_groups':{x:('Control' if i<len(samples)/2 else 'Treated') for i,x in enumerate(samples)}}
    elif kind=='spatial':
        sections=[]
        for fov in range([1,2,4][level]):
            objects=[]
            for i in range([12,24,48][level]):
                x=10+(i%8)*11;y=10+(i//8)*9;typ='spot' if fov%2==0 else 'segmentation';o={'id':f'Section{fov}_object_{i:03}','type':typ,'group':'Control' if i%2==0 else 'Treated','x':x,'y':y,'value':round((i*3%17)/4,2)}
                if typ=='segmentation':o['vertices']=[[x-3,y-2],[x+3,y-2],[x+4,y+1],[x+1,y+3],[x-3,y+2]]
                else:o['radius']=3
                objects.append(o)
            sections.append({'id':f'Section {fov+1} · '+('capture spots' if fov%2==0 else 'segmented cells'),'objects':objects,'transform':[1,0,0,1,0,0],'transform_provenance':'Explicit identity registration; synthetic geometry','physical_unit':'µm','pixel_size':2,'bounds':[0,100,0,72]})
        s['data']={'platform':'Synthetic platform-specific geometries','sections':sections,'limits':[0,4],'value_label':'Supplied expression'}
    elif kind=='genome':
        tracks=[];sha='1'*64
        for k,group in enumerate(['Control','Treated']):tracks.append({'id':'coverage_'+group,'kind':'coverage','label':group+' coverage','unit':'provided CPM','limits':[0,12],'normalization':'supplied CPM from upstream; no renderer normalization','source_sha256':sha,'records':[{'start':1000+i*50,'end':1050+i*50,'value':1+(i*3+k*4)%11} for i in range(20)]})
        tracks.extend([
            {'id':'peaks','kind':'peaks','label':'Accessible peaks','unit':'called intervals','normalization':'none; supplied peak calls','source_sha256':sha,'records':[{'start':1100,'end':1230},{'start':1450,'end':1600},{'start':1790,'end':1860}]},
            {'id':'genes','kind':'genes','label':'Gene structure','unit':'exons / strand','normalization':'none; supplied annotation','source_sha256':sha,'records':[{'start':1100,'end':1450,'strand':'+','label':'GENE_A','lane':0,'exons':[[1100,1180],[1300,1350],[1400,1450]]},{'start':1500,'end':1910,'strand':'-','label':'GENE_B','lane':1,'exons':[[1500,1580],[1700,1760],[1850,1910]]}]},
            {'id':'loops','kind':'loops','label':'Candidate contacts','unit':'supplied loop calls','normalization':'none','source_sha256':sha,'records':[{'start':1150,'end':1550},{'start':1350,'end':1800}]},
            {'id':'hic','kind':'hic','label':'Contact matrix','unit':'supplied contact score','limits':[0,10],'normalization':'frozen supplied matrix','source_sha256':sha,'records':[{'start':1000+i*100,'end':1100+i*100,'start2':1000+j*100,'end2':1100+j*100,'value':10-abs(i-j)} for i in range(10) for j in range(10)]}])
        s['data']={'assembly':'SYNTHETIC_ASSEMBLY','chromosome':'chrExample','coordinate_definition':'0-based-half-open','region':[1000,2000],'tracks':tracks}
    elif kind in ('markers','interactive'):
        n=[48,96,240][level];markers=['CD3D','MS4A1','LYZ','IL7R','FCER1G','CD79A','NKG7','CST3','GNLY'][:[3,5,9][level]];groups=['B_cell','T_cell','Myeloid'];objects=[]
        for i in range(n):
            g=groups[i%3];j=i//3;angle=j*2.39996;radius=1+(j%9)/8;cx=[-3,0,3][i%3];cy=[1,-2,1][i%3]
            objects.append({'id':f'Cell_{i+1:03}','group':g,'donor':f'Donor_{j%4+1}','x':round(cx+radius*math.cos(angle),4),'y':round(cy+radius*math.sin(angle),4),'values':{m:round(((i*5+k*3)%21)/5,2) for k,m in enumerate(markers)}})
        summaries=[{'group':g,'marker':m,'mean':round(((gi*7+mi*5)%19)/5,2),'fraction':[.1,.35,.6,.9][(gi+mi)%4],'n_donors':4,'n_objects':n//3} for gi,g in enumerate(groups) for mi,m in enumerate(markers)]
        s['data']={'objects':objects,'markers':markers,'summaries':summaries,'groups':groups,'value_limits':[0,4],'embedding_label':'Stored embedding','representation':'Supplied log-expression'}
    elif kind=='circos':
        sectors=[{'id':'chrA','length':100},{'id':'chrB','length':80},{'id':'chrC','length':120},{'id':'chrD','length':60}]
        tracks=[{'label':label,'unit':'supplied score','limits':[-2,2],'center':0,'records':[{'sector':sec['id'],'start':j*sec['length']/10,'end':(j+1)*sec['length']/10,'value':((j*3+k)%9-4)/2} for sec in sectors for j in range(10)]} for k,label in enumerate(['RNA','Accessibility','Protein'][:[1,2,3][level]])]
        s['data']={'sectors':sectors,'tracks':tracks,'links':[{'a':'chrA','a_pos':25,'b':'chrC','b_pos':50,'group':'Control'},{'a':'chrB','a_pos':50,'b':'chrD','b_pos':20,'group':'Treated'}],'coordinate_definition':'explicit synthetic sector coordinates; no inference of circular genomes'}
    else:
        s['data']={'colors':{'Ink':'#20354B','Teal':'#197F86','Coral':'#CF785E','Faint annotation':'#B1C0CD'},'roles':{'Ink':'normal_text','Teal':'graphical','Coral':'graphical','Faint annotation':'normal_text'},'background':'#FFFFFF','alpha':1,'ordered':False,'title':'Roles, not a universal palette pass'}
    if kind in ('heatmap','oncoprint'):s['layout']['page_panels']=1
    if kind in ('markers','interactive'):s['layout']['page_panels']=4
    if kind=='genome':
        n=[10,20,40][level];step=1000/n
        for k,t in enumerate(s['data']['tracks'][:2]):t['records']=[{'start':1000+i*step,'end':1000+(i+1)*step,'value':1+(i*3+k*4)%11} for i in range(n)]
        genes=s['data']['tracks'][3]['records']
        if level==2:
            genes.extend([{'start':1050+i*140,'end':1250+i*140,'strand':'+' if i%2 else '-','label':f'ALT_{i+1}','lane':i+2,'exons':[[1050+i*140,1090+i*140],[1200+i*140,1250+i*140]]} for i in range(4)])
    s['provenance']['source_sha256']=digest(s['data']);return s
