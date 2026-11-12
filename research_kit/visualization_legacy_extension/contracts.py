"""Frozen-result figure contracts. Standard library only; no model or statistics fitting."""
from pathlib import Path
import json,hashlib,math,re

KINDS={
 'heatmap':'Grouped matrices, frozen hierarchy and aligned supplied annotations',
 'spatial':'Registered spots, cells, molecules and segmentation polygons by section',
 'genome':'Frozen coverage, peaks, gene models, loops and Hi-C track companions',
 'oncoprint':'Multiple alterations per assayed cell with explicit missingness',
 'markers':'Stored embeddings, supplied marker values/fractions and donor counts',
 'circos':'Multi-track circular overview plus a linear companion',
 'interactive':'Shared frozen identities, keyboard selection and matched SVG snapshot',
 'palette':'Role-aware foreground/background and sequential luminance screening'}
SCHEMA='private-visual-increments/1'
def read(path):
    f=Path(path)
    if not 0<f.stat().st_size<=16_000_000:raise ValueError('Select bounded frozen JSON <=16 MB; use server-prepared subsets for larger results')
    return json.loads(f.read_text(encoding='utf-8-sig'),parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    with Path(path).open('x',encoding='utf8',newline='\n') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def num(v,lo=None,hi=None):
    if type(v) not in (int,float) or not math.isfinite(v) or lo is not None and v<lo or hi is not None and v>hi:raise ValueError('Finite number outside explicit display domain')
    return v
def text(v):
    if not isinstance(v,str) or not v.strip() or len(v)>2000:raise ValueError('Explicit bounded nonempty label required')
    return v
def axis(v):
    if not isinstance(v,list) or not v or any(not isinstance(x,str) or not x for x in v) or len(set(v))!=len(v):raise ValueError('Complete unique ordered identities required')
    return v
def fields(obj,allowed):
    if not isinstance(obj,dict) or set(obj)-set(allowed):raise ValueError('Unsupported display fields: '+str(set(obj)-set(allowed) if isinstance(obj,dict) else obj))
def scale(s):
    if not isinstance(s,list) or len(s)!=2 or num(s[0])>=num(s[1]):raise ValueError('Explicit common increasing value limits required')
def colors(p):
    if not isinstance(p,dict) or not p or any(not isinstance(k,str) or not re.fullmatch('#[0-9a-fA-F]{6}',v) for k,v in p.items()):raise ValueError('Explicit named sRGB palette required')
def matrix(d,key,rows,cols):
    v=d[key]
    if len(v)!=len(rows) or any(not isinstance(r,list) or len(r)!=len(cols) for r in v):raise ValueError('Complete matrix and declared identity axes differ')
    for row in v:
        for x in row:
            if x is not None:num(x)
def validate(s):
    fields(s,['schema','kind','title','alt_text','provenance','layout','palette','data'])
    if s.get('schema')!=SCHEMA or s.get('kind') not in KINDS:raise ValueError('Choose an exact versioned increment kind')
    for k in ('title','alt_text'):text(s.get(k))
    p=s['provenance'];fields(p,['source_id','source_sha256','value_unit','independent_unit','selection','transformations','synthetic'])
    for k in ('source_id','value_unit','independent_unit','selection','transformations'):text(p.get(k))
    if not re.fullmatch('[a-f0-9]{64}',p.get('source_sha256','')) or type(p.get('synthetic')) is not bool:raise ValueError('Exact source identity and synthetic scope required')
    l=s.get('layout',{});fields(l,['width_mm','height_mm','columns','rows','panel_width_mm','cell_pt','page_panels'])
    for k in ('width_mm','height_mm','panel_width_mm','cell_pt'):
        if k in l:num(l[k],1,1200)
    for k in ('columns','rows','page_panels'):
        if k in l and (type(l[k]) is not int or l[k]<1):raise ValueError('Positive explicit layout dimensions required')
    colors(s['palette']);d=s['data'];kind=s['kind']
    if not isinstance(d,dict):raise ValueError('Frozen data object required')
    if kind=='heatmap':
        fields(d,['rows','columns','values','limits','center','row_groups','column_groups','row_bars','column_bars','tree','value_label','row_labels','column_labels','raster_cells'])
        rows=axis(d['rows']);cols=axis(d['columns']);matrix(d,'values',rows,cols);scale(d['limits']);text(d['value_label'])
        if 'center' in d and d['center'] is not None:num(d['center'],*d['limits'])
        if any(x is not None and not d['limits'][0]<=x<=d['limits'][1] for r in d['values'] for x in r):raise ValueError('Values outside supplied scale cannot be silently clipped')
        for k,a in [('row_groups',rows),('column_groups',cols)]:
            if k in d and (set(d[k])!=set(a) or any(x not in s['palette'] for x in d[k].values())):raise ValueError('Complete supplied annotation identities required')
        for k,a in [('row_bars',rows),('column_bars',cols)]:
            if k in d:
                fields(d[k],['values','limits','label']);scale(d[k]['limits']);text(d[k]['label'])
                if set(d[k]['values'])!=set(a):raise ValueError('Supplied annotation axis differs')
                for x in d[k]['values'].values():num(x,*d[k]['limits'])
        if 'tree' in d:
            t=d['tree'];fields(t,['leaf_order','segments','height_unit']);text(t['height_unit'])
            if t['leaf_order']!=rows:raise ValueError('Frozen tree leaf order differs from displayed rows')
            for seg in t['segments']:
                if len(seg)!=4:raise ValueError('Frozen hierarchy segments require x1,y1,x2,y2')
                for x in (seg[0],seg[2]):num(x,0,1)
                for y in (seg[1],seg[3]):num(y,0,len(rows)-1)
        for key,a in [('row_labels',rows),('column_labels',cols)]:
            if key in d and set(d[key])!=set(a):raise ValueError('Label mapping must preserve every identity')
        if type(d.get('raster_cells',False)) is not bool:raise ValueError('Explicit raster-cell policy required')
    elif kind=='oncoprint':
        fields(d,['genes','samples','cells','gene_groups','sample_groups','sample_labels','gene_labels','supplied_tmb','tmb_provenance'])
        genes=axis(d['genes']);samples=axis(d['samples']);seen=set()
        for r in d['cells']:
            fields(r,['gene','sample','assayed','events']);key=(r['gene'],r['sample'])
            if key in seen or r['gene'] not in genes or r['sample'] not in samples or type(r['assayed']) is not bool or not isinstance(r['events'],list) or len(r['events'])!=len(set(r['events'])) or any(e not in s['palette'] for e in r['events']) or not r['assayed'] and r['events']:raise ValueError('Invalid or duplicate assayed/event identity')
            seen.add(key)
        if len(seen)!=len(genes)*len(samples):raise ValueError('Explicit complete tested/untested matrix required')
        for key,a in [('sample_groups',samples),('gene_groups',genes)]:
            if key in d and (set(d[key])!=set(a) or any(v not in s['palette'] for v in d[key].values())):raise ValueError('Complete clinical/group annotation required')
        for key,a in [('sample_labels',samples),('gene_labels',genes)]:
            if key in d:
                if set(d[key])!=set(a):raise ValueError('Complete display label identity required')
                for v in d[key].values():text(v)
        if 'supplied_tmb' in d:
            if set(d['supplied_tmb'])!=set(samples) or not d.get('tmb_provenance'):raise ValueError('TMB requires explicit supplied values, denominator and provenance')
            for x in d['supplied_tmb'].values():num(x,0)
    elif kind=='spatial':
        fields(d,['platform','sections','limits','value_label']);scale(d['limits']);text(d['value_label']);text(d['platform']);axis([x['id'] for x in d['sections']])
        for sec in d['sections']:
            fields(sec,['id','objects','transform','transform_provenance','physical_unit','pixel_size','bounds','background','background_sha256'])
            text(sec['physical_unit']);text(sec['transform_provenance']);num(sec['pixel_size'],1e-12);b=sec['bounds']
            if len(b)!=4 or num(b[0])>=num(b[1]) or num(b[2])>=num(b[3]):raise ValueError('Explicit spatial bounds required')
            a=sec['transform']
            if len(a)!=6:raise ValueError('Explicit affine a,b,c,d,e,f required; no registration fitting')
            for x in a:num(x)
            if abs(a[0]*a[3]-a[1]*a[2])<1e-15:raise ValueError('Singular spatial transform')
            axis([x['id'] for x in sec['objects']])
            for o in sec['objects']:
                fields(o,['id','type','group','x','y','radius','vertices','value'])
                if o['type'] not in ('spot','cell','molecule','segmentation') or o['group'] not in s['palette']:raise ValueError('Explicit spatial object type and identity palette required')
                num(o['value'],*d['limits']);num(o['x']);num(o['y'])
                if o['type']=='segmentation':
                    if len(o.get('vertices',[]))<3:raise ValueError('Actual supplied segmentation polygon required')
                    for xy in o['vertices']:
                        if len(xy)!=2:raise ValueError('Polygon coordinate axis differs')
                        for v in xy:num(v)
                else:num(o['radius'],1e-12)
    elif kind=='genome':
        fields(d,['assembly','chromosome','coordinate_definition','region','tracks']);text(d['assembly']);text(d['chromosome'])
        if d['coordinate_definition']!='0-based-half-open':raise ValueError('Convert coordinates upstream explicitly to 0-based half-open before track display')
        scale(d['region']);axis([r['id'] for r in d['tracks']])
        for t in d['tracks']:
            fields(t,['id','kind','label','unit','limits','records','normalization','source_sha256']);text(t['label']);text(t['unit']);text(t['normalization'])
            if t['kind'] not in ('coverage','peaks','genes','loops','hic'):raise ValueError('Unsupported frozen genomic track')
            if not re.fullmatch('[a-f0-9]{64}',t['source_sha256']):raise ValueError('Each track requires source identity')
            if t['kind'] in ('coverage','hic'):scale(t['limits'])
            for r in t['records']:
                if not d['region'][0]<=num(r['start'])<num(r['end'])<=d['region'][1]:raise ValueError('Interval is outside reviewed region')
                if t['kind'] in ('coverage','hic'):num(r['value'],*t['limits'])
                if t['kind']=='genes':
                    if r.get('strand') not in ('+','-'):raise ValueError('Explicit gene strand required')
                    if type(r.get('lane',0)) is not int or r.get('lane',0)<0:raise ValueError('Explicit nonnegative gene lane required')
                    for a,b in r.get('exons',[]):
                        if not r['start']<=a<b<=r['end']:raise ValueError('Exon outside gene interval')
                if t['kind']=='hic' and not d['region'][0]<=num(r['start2'])<num(r['end2'])<=d['region'][1]:raise ValueError('Hi-C second axis outside region')
    elif kind in ('markers','interactive'):
        fields(d,['objects','markers','summaries','summary_scope','groups','value_limits','embedding_label','representation','gene_labels'])
        groups=axis(d['groups']);markers=axis(d['markers']);scale(d['value_limits']);text(d['embedding_label']);text(d['representation'])
        if any(g not in s['palette'] for g in groups):raise ValueError('Complete stable group palette required')
        axis([x['id'] for x in d['objects']])
        for o in d['objects']:
            fields(o,['id','group','x','y','values','donor'])
            if o['group'] not in groups or set(o['values'])!=set(markers):raise ValueError('Complete stored marker/embedding identity required')
            text(o['donor']);num(o['x']);num(o['y'])
            for value in o['values'].values():
                if value is not None:num(value,*d['value_limits'])
        seen=set()
        for r in d['summaries']:
            fields(r,['group','marker','mean','fraction','n_donors','n_objects']);key=(r['group'],r['marker'])
            if key in seen or r['group'] not in groups or r['marker'] not in markers:raise ValueError('Duplicate/unknown supplied marker summary')
            seen.add(key);num(r['mean'],*d['value_limits']);num(r['fraction'],0,1)
            for k in ('n_donors','n_objects'):
                if type(r[k]) is not int or r[k]<1:raise ValueError('Explicit observed donor and object counts required')
        if len(seen)!=len(groups)*len(markers):raise ValueError('Complete supplied marker summary grid required; no hidden recomputation')
        scope=d.get('summary_scope',{'kind':'selected_objects'})
        fields(scope,['kind','source_id','source_sha256','selection'])
        if scope['kind']=='upstream_population':
            text(scope['source_id']);text(scope['selection'])
            if not re.fullmatch('[a-f0-9]{64}',scope['source_sha256']):raise ValueError('Upstream summary population requires its own exact source and selection')
        elif scope['kind']=='selected_objects':
            for r in d['summaries']:
                selected=[o for o in d['objects'] if o['group']==r['group'] and o['values'][r['marker']] is not None]
                if r['n_objects']!=len(selected) or r['n_donors']!=len({o['donor'] for o in selected}):raise ValueError('Supplied summary counts differ from selected nonmissing objects/donors; declare a separate upstream population explicitly')
        else:raise ValueError('Explicit selected_objects or upstream_population summary scope required')
    elif kind=='circos':
        fields(d,['sectors','tracks','links','coordinate_definition']);text(d['coordinate_definition']);sectors=axis([x['id'] for x in d['sectors']]);lengths={x['id']:num(x['length'],1e-12) for x in d['sectors']}
        for t in d['tracks']:
            fields(t,['label','unit','limits','center','records']);text(t['label']);text(t['unit']);scale(t['limits'])
            if 'center' in t:num(t['center'],*t['limits'])
            for r in t['records']:
                if r['sector'] not in sectors or not 0<=num(r['start'])<num(r['end'])<=lengths[r['sector']]:raise ValueError('Circular track interval axis invalid')
                num(r['value'],*t['limits'])
        for r in d['links']:
            for side in ('a','b'):
                if r[side] not in lengths:raise ValueError('Link outside sector identity axis')
                num(r[side+'_pos'],0,lengths[r[side]])
            if r['group'] not in s['palette']:raise ValueError('Link group palette missing')
    elif kind=='palette':
        fields(d,['colors','roles','background','alpha','ordered','title']);colors(d['colors']);colors({'background':d['background']});num(d['alpha'],0,1)
        if set(d['roles'])!=set(d['colors']) or any(x not in ('normal_text','large_text','graphical','categorical','sequential') for x in d['roles'].values()):raise ValueError('Declare the actual color role, not a universal WCAG claim')
    return s
