"""Original SVG display of frozen evidence. No scientific packages, fits or inference."""
import math,html,base64,struct,zlib,binascii,textwrap
from pathlib import Path
from contracts import validate,sha
INK='#20354B';MUTED='#64748B';LINE='#DDE5EC';TEAL='#197F86';CORAL='#CF785E';LIGHT='#F5F8FA'
def esc(x):return html.escape(str(x),quote=True)
def rect(x,y,w,h,fill=LIGHT,stroke='none',extra=''):return f'<rect x="{x:.3f}" y="{y:.3f}" width="{max(0,w):.3f}" height="{max(0,h):.3f}" fill="{fill}" stroke="{stroke}" {extra}/>'
def line(x,y,a,b,c=LINE,width=.7,extra=''):return f'<line x1="{x:.3f}" y1="{y:.3f}" x2="{a:.3f}" y2="{b:.3f}" stroke="{c}" stroke-width="{width}" {extra}/>'
def txt(x,y,value,size=8.5,color=INK,anchor='start',extra=''):
    return f'<text x="{x:.3f}" y="{y:.3f}" font-family="Helvetica" font-size="{size}" fill="{color}" text-anchor="{anchor}" {extra}>{esc(value)}</text>'

def missing(x,y,w,h):
    # Explicit geometry survives both browser SVG and document conversion.
    return rect(x,y,w,h,'#EDF0F3')+line(x+1,y+1,x+w-1,y+h-1,'#94A3B0',.65)+line(x+w-1,y+1,x+1,y+h-1,'#94A3B0',.65)

def chosen(palette,labels):return {k:v for k,v in palette.items() if k in set(labels)}
def wrap(x,y,value,width,size=8.5,color=INK):
    capacity=max(5,int(width/(size*.55)));words=str(value).split();lines=[];row=''
    for word in words:
        if len(row)+len(word)+1>capacity:
            if row:lines.append(row);row=''
            while len(word)>capacity:lines.append(word[:capacity]);word=word[capacity:]
        row=(row+' '+word).strip()
    if row:lines.append(row)
    return ''.join(txt(x,y+i*size*1.3,t,size,color) for i,t in enumerate(lines)),max(1,len(lines))*size*1.3
def circle(x,y,r,fill,extra=''):return f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{max(0,r):.3f}" fill="{fill}" {extra}/>'
def path(d,stroke=TEAL,fill='none',width=1,extra=''):return f'<path d="{d}" stroke="{stroke}" fill="{fill}" stroke-width="{width}" {extra}/>'
def rgb(h):return [int(h[i:i+2],16) for i in (1,3,5)]
def color(v,limits,center=None):
    if v is None:return '#DADFE5'
    lo,hi=limits;t=(v-lo)/(hi-lo)
    if center is None:a,b='#F0F5F5','#197F86'
    elif v<=center:a,b='#35649A','#F8F7F2';t=(v-lo)/(center-lo) if center>lo else 1
    else:a,b='#F8F7F2','#C5634E';t=(v-center)/(hi-center) if hi>center else 1
    return '#'+''.join(f'{round(x+(y-x)*t):02x}' for x,y in zip(rgb(a),rgb(b)))
def legend(palette,x,y,width,size=8):
    out='';cursor=x;row=y
    for label,c in palette.items():
        need=14+len(label)*size*.53
        if cursor+need>x+width and cursor>x:row+=15;cursor=x
        out+=rect(cursor,row-7,7,7,c)+txt(cursor+11,row,label,size);cursor+=need+8
    return out,row-y+15
def scale_key(limits,x,y,w=100,center=None,label=''):
    out=''
    for i in range(60):out+=rect(x+i*w/60,y,w/60+.1,5,color(limits[0]+(limits[1]-limits[0])*i/59,limits,center))
    if center is not None and limits[0]<center<limits[1]:out+=txt(x+w*(center-limits[0])/(limits[1]-limits[0]),y+16,f'{center:g}',7,anchor='middle')
    return out+txt(x,y+16,f'{limits[0]:g}',7)+txt(x+w,y+16,f'{limits[1]:g}',7,anchor='end')+txt(x+w/2,y+28,label,7,anchor='middle')
def chunks(items,size):return [items[i:i+size] for i in range(0,len(items),size)]
def _png(matrix,limits,center):
    h=len(matrix);w=len(matrix[0]);raw=b''.join(b'\0'+bytes(c for v in row for c in (rgb(color(v,limits,center)) if v is not None else [218,222,228])) for row in matrix)
    def chunk(k,b):return struct.pack('>I',len(b))+k+b+struct.pack('>I',binascii.crc32(k+b)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
def heat_panels(s,w):
    d=s['data'];cell=s.get('layout',{}).get('cell_pt',13);cap=max(1,int((w-165)/cell));cap=math.ceil(len(d['columns'])/math.ceil(len(d['columns'])/cap));panels=[]
    for cc in chunks(list(enumerate(d['columns'])),cap):
        canvas=w;w=min(canvas,165+len(cc)*22)
        rows=d['rows'];label_width=min(w*.36,max(64,max(len(d.get('row_labels',{}).get(r,r)) for r in rows)*4.2));label_lines={r:textwrap.wrap(d.get('row_labels',{}).get(r,r),max(6,int((label_width-15)/4.2))) for r in rows};rh=max(13,cell,max(len(v) for v in label_lines.values())*10+2);x=label_width+(30 if 'tree' in d else 0);cw=min(22,(w-x-53)/len(cc));y=max(49,max(len(d.get('column_labels',{}).get(c,c)) for _,c in cc)*3.5+16);out=''
        if cw<6:raise ValueError('Matrix cells too narrow; enlarge panel width or cell_pt to paginate')
        for j,(ix,name) in enumerate(cc):
            if 'column_groups' in d:out+=rect(x+j*cw,y-13,cw-1,5,s['palette'][d['column_groups'][name]])
            label=d.get('column_labels',{}).get(name,name)
            out+=txt(x+j*cw+cw/2,y-18,label,7.5,extra=f'transform="rotate(-40 {x+j*cw+cw/2} {y-18})"')
        if d.get('raster_cells'):
            raw=_png([[r[i] for i,_ in cc] for r in d['values']],d['limits'],d.get('center'));b64=base64.b64encode(raw).decode();out+=f'<image x="{x}" y="{y}" width="{cw*len(cc)}" height="{rh*len(rows)}" preserveAspectRatio="none" style="image-rendering:pixelated" href="data:image/png;base64,{b64}"/>'
        for i,name in enumerate(rows):
            yy=y+i*rh
            for li,label in enumerate(label_lines[name]):out+=txt(x-12,yy+rh/2+(li-(len(label_lines[name])-1)/2)*10+3,label,8,anchor='end')
            if 'row_groups' in d:out+=rect(x-8,yy+1,4,rh-1,s['palette'][d['row_groups'][name]])
            for j,(ix,_) in enumerate(cc):
                v=d['values'][i][ix]
                if v is None:out+=missing(x+j*cw,yy,cw-.6,rh-.6)
                elif not d.get('raster_cells'):out+=rect(x+j*cw,yy,cw-.6,rh-.6,color(v,d['limits'],d.get('center')))
            if 'row_bars' in d:
                b=d['row_bars'];v=b['values'][name];lo,hi=b['limits'];xx=x+len(cc)*cw+7;zero=xx+(0-lo)/(hi-lo)*30 if lo<0<hi else xx;end=xx+(v-lo)/(hi-lo)*30
                out+=line(zero,yy,zero,yy+rh,LINE,.5)+rect(min(zero,end),yy+rh*.24,abs(end-zero),rh*.5,TEAL if v>=0 else CORAL)
        if 'tree' in d:
            for a,b,c,e in d['tree']['segments']:out+=line(9+a*24,y+(b+.5)*rh,9+c*24,y+(e+.5)*rh,MUTED,.65)
            out+=txt(6,y-4,'Frozen tree',6.8,MUTED)
        foot=y+len(rows)*rh+10
        if 'column_bars' in d:
            b=d['column_bars'];lo,hi=b['limits']
            for j,(_,name) in enumerate(cc):out+=rect(x+j*cw+1,foot+24-(b['values'][name]-lo)/(hi-lo)*24,cw-2,(b['values'][name]-lo)/(hi-lo)*24,TEAL)
            out+=txt(x-8,foot+16,b['label'],7,anchor='end');foot+=38
        out+=scale_key(d['limits'],x,foot,min(105,w-x-55),d.get('center'),d['value_label'])
        if 'row_bars' in d:out+=wrap(x+len(cc)*cw+4,y-15,d['row_bars']['label'],43,7)[0]
        leg,h=legend({k:v for k,v in s['palette'].items() if k in set(d.get('row_groups',{}).values())|set(d.get('column_groups',{}).values())},12,foot+44,w-24);out+=leg
        if any(v is None for row in d['values'] for v in row):out+=missing(12,foot+44+h+2,8,8)+txt(24,foot+44+h+9,'Missing supplied value',7,MUTED);h+=18
        out=f'<g transform="translate({(canvas-w)/2} 0)">'+out+'</g>'
        panels.append({'label':f'Grouped matrix · columns {cc[0][0]+1}–{cc[-1][0]+1}', 'svg':out,'height':foot+50+h,'object_ids':rows,'column_ids':[x[1] for x in cc]});w=canvas
    return panels
def onco_panels(s,w):
    d=s['data'];cell=s.get('layout',{}).get('cell_pt',13);cap=max(1,int((w-162)/cell));genes=d['genes'];data={(r['gene'],r['sample']):r for r in d['cells']};outpan=[]
    for cc in chunks(d['samples'],cap):
        x=88;cw=min(23,(w-x-64)/len(cc));rh=19;y=62;out=''
        for j,sample in enumerate(cc):
            n=sum(len(data[g,sample]['events']) for g in genes);maxn=max(1,max(sum(len(data[g,q]['events']) for g in genes) for q in d['samples']));bar=27*n/maxn
            out+=rect(x+j*cw+2,y-12-bar,cw-4,bar,TEAL)+txt(x+j*cw+cw/2,y-16-bar,str(n),7,anchor='middle')
            if 'sample_groups' in d:out+=rect(x+j*cw,y-8,cw-1,4,s['palette'][d['sample_groups'][sample]])
            out+=txt(x+j*cw+cw/2,y+len(genes)*rh+8,d.get('sample_labels',{}).get(sample,sample),7.3,extra=f'transform="rotate(55 {x+j*cw+cw/2} {y+len(genes)*rh+8})"')
        out+=txt(x,y-48,'Alteration events · count, not TMB',7.5,MUTED)
        for i,gene in enumerate(genes):
            yy=y+i*rh;out+=txt(x-9,yy+12,d.get('gene_labels',{}).get(gene,gene),8,anchor='end')
            if 'gene_groups' in d:out+=rect(x-6,yy,3,rh-1,s['palette'][d['gene_groups'][gene]])
            for j,sample in enumerate(cc):
                r=data[gene,sample];out+=rect(x+j*cw,yy,cw-1,rh-1,'#F1F4F6') if r['assayed'] else missing(x+j*cw,yy,cw-1,rh-1)
                for k,event in enumerate(r['events']):out+=rect(x+j*cw+1,yy+1+k*(rh-3)/len(r['events']),cw-3,(rh-3)/len(r['events'])-.3,s['palette'][event])
            tested=sum(data[gene,q]['assayed'] for q in d['samples']);altered=sum(bool(data[gene,q]['events']) for q in d['samples']);out+=txt(x+len(cc)*cw+7,yy+12,f'{altered}/{tested}',8,MUTED)
        out+=txt(x+len(cc)*cw+7,y-5,'Altered / tested',6.5,MUTED)
        foot=y+len(genes)*rh+45
        if 'supplied_tmb' in d:
            out+=txt(12,foot,'TMB supplied separately · '+d['tmb_provenance'],7,MUTED);foot+=15
            for j,sample in enumerate(cc):out+=txt(x+j*cw+cw/2,foot,str(d['supplied_tmb'][sample]),7,anchor='middle')
            foot+=15
        labels={e for row in d['cells'] for e in row['events']}|set(d.get('sample_groups',{}).values())|set(d.get('gene_groups',{}).values())
        leg,lh=legend(chosen(s['palette'],labels),12,foot,w-24);out+=leg+missing(12,foot+lh+3,8,8)+txt(24,foot+lh+10,'Not assayed; light cells = assayed, no listed alteration',7,MUTED)
        outpan.append({'label':f'Multi-event alterations · {cc[0]}–{cc[-1]}','svg':out,'height':foot+lh+25,'object_ids':cc,'gene_ids':genes})
    return outpan
def spatial_panels(s,w,root):
    d=s['data'];panels=[]
    for sec in d['sections']:
        bx,ex,by,ey=sec['bounds'];k=min((w-30)/(ex-bx),170/(ey-by));pw=(ex-bx)*k;ph=(ey-by)*k;ox=(w-pw)/2;oy=12;a,b,c,e,tx,ty=sec['transform'];out=''
        def point(x,y):return ox+(a*x+c*y+tx-bx)*k,oy+(b*x+e*y+ty-by)*k
        if sec.get('background'):
            f=(root/sec['background']).resolve(strict=True)
            if not f.is_relative_to(root.resolve()) or sha(f)!=sec.get('background_sha256'):raise ValueError('Background must match exact selected local source hash')
            raw=f.read_bytes()
            if len(raw)>12_000_000 or not raw.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Use a bounded local PNG display crop; no remote images')
            out+=f'<image x="{ox}" y="{oy}" width="{pw}" height="{ph}" preserveAspectRatio="none" href="data:image/png;base64,{base64.b64encode(raw).decode()}"/>'
        else:out+=rect(ox,oy,pw,ph,'#F0F3F3',LINE)
        for o in sec['objects']:
            x,y=point(o['x'],o['y'])
            if not ox<=x<=ox+pw or not oy<=y<=oy+ph:raise ValueError('Registered object center outside declared crop; select upstream crop explicitly')
            col=color(o['value'],d['limits']);title=f'<title>{esc(o["id"]+" | "+o["type"]+" | "+o["group"]+" | "+str(o["value"]))}</title>'
            if o['type']=='segmentation':
                pts=[point(*p) for p in o['vertices']]
                if any(not ox<=x<=ox+pw or not oy<=y<=oy+ph for x,y in pts):raise ValueError('Segmentation polygon outside reviewed crop')
                out+=f'<polygon points="'+ ' '.join(f'{x:.3f},{y:.3f}' for x,y in pts)+f'" fill="{col}" fill-opacity=".65" stroke="{s["palette"][o["group"]]}" stroke-width=".7">{title}</polygon>'
            else:
                # Radius is in source coordinate units; affine affects the entire disk.
                radius=o['radius'];m=f'matrix({a*k} {b*k} {c*k} {e*k} {ox+(tx-bx)*k} {oy+(ty-by)*k})'
                rx=radius*math.hypot(a,c)*k;ry=radius*math.hypot(b,e)*k
                if x-rx<ox or x+rx>ox+pw or y-ry<oy or y+ry>oy+ph:raise ValueError('Spatial disk extent outside declared crop')
                out+=f'<circle cx="{o["x"]}" cy="{o["y"]}" r="{radius}" transform="{m}" fill="{col}" stroke="{s["palette"][o["group"]]}" stroke-width="{.7/k}" fill-opacity=".9">{title}</circle>'
        bar=(ex-bx)*.2;out+=line(ox+9,oy+ph-11,ox+9+bar*k,oy+ph-11,INK,1.5)+txt(ox+9,oy+ph-16,f'{bar*sec["pixel_size"]:g} {sec["physical_unit"]}',7)
        foot=oy+ph+13;out+=scale_key(d['limits'],12,foot,90,label=d['value_label']);leg,lh=legend(chosen(s['palette'],[o['group'] for o in sec['objects']]),12,foot+46,w-24);out+=leg
        info,h=wrap(12,foot+46+lh+8,f'{d["platform"]} · {sec["transform_provenance"]}',w-24,7,MUTED);out+=info
        panels.append({'label':sec['id']+' · registered physical objects','svg':out,'height':foot+60+h+lh,'object_ids':[o['id'] for o in sec['objects']]})
    return panels
def genome_panels(s,w):
    d=s['data'];a,b=d['region'];x=86;pw=w-x-18;out='';y=14
    def px(v):return x+(v-a)/(b-a)*pw
    for t in d['tracks']:
        lanes=max([r.get('lane',0) for r in t['records']]+[0])+1 if t['kind']=='genes' else 1
        hh=80 if t['kind']=='hic' else max(45,lanes*24) if t['kind']=='genes' else 45;out+=rect(x,y,pw,hh,'#F7F9FB')+wrap(3,y+12,t['label'],78,8)[0]+txt(3,y+hh-5,t['unit'],6.8,MUTED)
        if t['kind']=='coverage':
            lo,hi=t['limits'];prev=None
            for r in t['records']:
                py=y+hh-6-(r['value']-lo)/(hi-lo)*(hh-12);out+=line(px(r['start']),py,px(r['end']),py,TEAL,1.2)
                if prev is not None and prev['end']==r['start']:out+=line(px(r['start']),prev['py'],px(r['start']),py,TEAL,1.2)
                prev={**r,'py':py}
            out+=txt(x+pw-3,y+9,f'{lo:g}–{hi:g}',6.5,MUTED,'end')
        elif t['kind']=='peaks':
            for r in t['records']:out+=rect(px(r['start']),y+17,max(1,px(r['end'])-px(r['start'])),10,CORAL)
        elif t['kind']=='genes':
            lanes=max([r.get('lane',0) for r in t['records']]+[0])+1
            for r in t['records']:
                yy=y+13+r.get('lane',0)*20;out+=line(px(r['start']),yy,px(r['end']),yy,TEAL,1)
                for l,h in r.get('exons',[]):out+=rect(px(l),yy-3,max(1,px(h)-px(l)),6,TEAL)
                mid=(px(r['start'])+px(r['end']))/2;sgn=1 if r['strand']=='+' else -1;out+=path(f'M {mid-3*sgn} {yy-7} L {mid} {yy-4} L {mid-3*sgn} {yy-1}',INK)+txt(px(r['start']),yy-9,r.get('label','gene'),6.8)
        elif t['kind']=='loops':
            for r in t['records']:
                left,right=px(r['start']),px(r['end']);out+=path(f'M {left} {y+hh-4} Q {(left+right)/2} {y-hh*.4} {right} {y+hh-4}',TEAL,'none',.8)
        else:
            for r in t['records']:
                yy=y+(r['start2']-a)/(b-a)*hh;out+=rect(px(r['start']),yy,max(.5,px(r['end'])-px(r['start'])),max(.5,(r['end2']-r['start2'])/(b-a)*hh),color(r['value'],t['limits']))
            out+=txt(x,y-3,f'Second locus: {a:g} to {b:g} downward',6.5,MUTED)
            out+=scale_key(t['limits'],x,y+hh+6,75,label='Contact score');y+=38
        y+=hh+10
    for i in range(5):
        v=a+(b-a)*i/4;out+=line(px(v),y-8,px(v),y-4,MUTED)+txt(px(v),y+5,f'{v:g}',7,MUTED,'middle')
    out+=txt(x,y+21,f'{d["chromosome"]} · {d["assembly"]} · 0-based half-open',7.5)
    return [{'label':'Aligned frozen genomic evidence','svg':out,'height':y+38,'object_ids':[t['id'] for t in d['tracks']]}]
def marker_panels(s,w):
    d=s['data'];panels=[];objects=d['objects'];xs=[r['x'] for r in objects];ys=[r['y'] for r in objects];lx,hx=min(xs),max(xs);ly,hy=min(ys),max(ys);span=max(hx-lx,hy-ly,1);mx=(hx+lx)/2;my=(hy+ly)/2;py=12;side=min(w-40,240);px=(w-side)/2
    def point(o):return px+side*(.5+(o['x']-mx)/(span*1.12)),py+side*(.5-(o['y']-my)/(span*1.12))
    for feature in [None]+d['markers']:
        out=rect(px,py,side,side,'#F7F9FA')
        for o in objects:
            x,y=point(o);co=s['palette'][o['group']] if feature is None else color(o['values'][feature],d['value_limits']);out+=f'<g data-object="{esc(o["id"])}" data-group="{esc(o["group"])}" tabindex="0" aria-label="{esc(o["id"]+", "+o["group"]+", donor "+o["donor"])}">'+circle(x,y,2.1,co)+f'<title>{esc(o["id"]+" | "+o["group"])}</title></g>'
        foot=py+side+17
        if feature is None:
            leg,lh=legend(chosen(s['palette'],d['groups']),12,foot,w-24);out+=leg;foot+=lh+12
        else:
            out+=scale_key(d['value_limits'],20,foot,100,label=d['representation']);foot+=42
        out+=txt(20,foot,d['embedding_label']+' · stored coordinates',7,MUTED)
        panels.append({'label':'Cell identities' if feature is None else d.get('gene_labels',{}).get(feature,feature),'svg':out,'height':foot+16,'object_ids':[o['id'] for o in objects]})
    # Supplied summaries, with area proportional to fraction, never diameter.
    marker_cap=max(1,int((w-86)/28));marker_cap=math.ceil(len(d['markers'])/math.ceil(len(d['markers'])/marker_cap))
    for marker_part in chunks(d['markers'],marker_cap):
        out='';x=84;y=26;cw=(w-x-20)/len(marker_part);rh=25;summary={(r['group'],r['marker']):r for r in d['summaries']}
        for j,m in enumerate(marker_part):out+=txt(x+(j+.5)*cw,y-11,d.get('gene_labels',{}).get(m,m),7.5,anchor='middle')
        for i,g in enumerate(d['groups']):
            donors={summary[g,m]['n_donors'] for m in marker_part};nd='/'.join(map(str,sorted(donors)));out+=txt(x-8,y+(i+.5)*rh+3,g,8,'#20354B','end')+txt(5,y+(i+.5)*rh+12,'donors '+nd,6.5,MUTED)
            for j,m in enumerate(marker_part):
                r=summary[g,m];out+=circle(x+(j+.5)*cw,y+(i+.5)*rh,8*math.sqrt(r['fraction']),color(r['mean'],d['value_limits']),f'stroke="{LINE}" stroke-width=".5"')
                if r['fraction']==0:out+=circle(x+(j+.5)*cw,y+(i+.5)*rh,1,'white',f'stroke="{MUTED}" stroke-width=".6"')
        foot=y+len(d['groups'])*rh+13;out+=scale_key(d['value_limits'],12,foot,90,label='Supplied mean')
        for j,f in enumerate([.25,.5,1]):out+=circle(142+j*30,foot+6,8*math.sqrt(f),TEAL)+txt(142+j*30,foot+25,f'{f:g}',7,anchor='middle')
        out+=txt(124,foot+39,'Area = supplied detected fraction',6.8,MUTED)
        summary_label='Marker specificity · upstream population' if d.get('summary_scope',{}).get('kind')=='upstream_population' else 'Marker specificity · supplied summaries'
        panels.append({'label':summary_label,'svg':out,'height':foot+53,'object_ids':d['groups'],'marker_ids':marker_part})
    return panels
def circos_panels(s,w):
    d=s['data'];cx=w*.31;cy=155;r=min(w*.25,103);out='';ids=[x['id'] for x in d['sectors']];total=sum(x['length'] for x in d['sectors']);angles={};cursor=-math.pi/2;gap=.10
    for sec in d['sectors']:
        length=sec['length']/total*(2*math.pi-gap*len(ids));angles[sec['id']]=(cursor,cursor+length,sec['length']);cursor+=length+gap
    def polar(theta,rr):return cx+rr*math.cos(theta),cy+rr*math.sin(theta)
    def theta(sector,pos):a,b,l=angles[sector];return a+(b-a)*pos/l
    def arc(a,b,inner,outer,co):
        x1,y1=polar(a,outer);x2,y2=polar(b,outer);x3,y3=polar(b,inner);x4,y4=polar(a,inner);large=int(b-a>math.pi)
        return path(f'M {x1} {y1} A {outer} {outer} 0 {large} 1 {x2} {y2} L {x3} {y3} A {inner} {inner} 0 {large} 0 {x4} {y4} Z','white',co,.5)
    for i,sec in enumerate(d['sectors']):
        a,b,_=angles[sec['id']];co=list(s['palette'].values())[i%len(s['palette'])];out+=arc(a,b,r,r+5,co);x,y=polar((a+b)/2,r+18);out+=txt(x,y,sec['id'],8,anchor='middle')
    if len(d['tracks'])>4:raise ValueError('Use additional circular panels for more than four tracks; do not compress track readability')
    for j,t in enumerate(d['tracks']):
        outer=r-5-j*14;inner=outer-11
        for q in t['records']:out+=arc(theta(q['sector'],q['start']),theta(q['sector'],q['end']),inner,outer,color(q['value'],t['limits'],t.get('center')))
    inner=r-8-len(d['tracks'])*14
    for q in d['links']:
        a,b=polar(theta(q['a'],q['a_pos']),inner);c,e=polar(theta(q['b'],q['b_pos']),inner);out+=path(f'M {a} {b} Q {cx} {cy} {c} {e}',s['palette'][q['group']],'none',1,'opacity=".6"')
    # Mandatory linear companion preserves the same sector, track, interval and scale.
    xx=w*.65;ww=w-xx-14;yy=32;out+=txt(xx,yy-13,'Linear companion',9)
    for sec in d['sectors']:
        out+=txt(xx,yy,sec['id'],8)
        for j,t in enumerate(d['tracks']):
            y=yy+14+j*28;out+=txt(xx,y-3,t['label'],6.8,MUTED)+rect(xx,y,ww,10,LIGHT)
            for q in t['records']:
                if q['sector']==sec['id']:out+=rect(xx+q['start']/sec['length']*ww,y,(q['end']-q['start'])/sec['length']*ww,10,color(q['value'],t['limits'],t.get('center')))
        bottom=yy+14+(len(d['tracks'])-1)*28+10
        out+=txt(xx,bottom+11,'0',6.5,MUTED)+txt(xx+ww,bottom+11,f'{sec["length"]:g}',6.5,MUTED,'end')
        yy+=len(d['tracks'])*28+43
    foot=max(cy+r+38,yy)
    label_svg,label_h=wrap(12,foot,'Rings, outer to inner: '+', '.join(t['label'] for t in d['tracks']),w-24,7,MUTED);out+=label_svg;foot+=label_h+12
    scale_cols=max(1,int((w-24)/118))
    for j,t in enumerate(d['tracks']):out+=scale_key(t['limits'],15+(j%scale_cols)*118,foot+(j//scale_cols)*43,90,t.get('center'),label=t['label']+' ['+t['unit']+']')
    foot+=math.ceil(len(d['tracks'])/scale_cols)*43
    leg,lh=legend(chosen(s['palette'],[q['group'] for q in d['links']]),12,foot+8,w-24);out+=leg
    return [{'label':'Circular overview + matched linear scales','svg':out,'height':foot+lh+24,'object_ids':ids}]
def palette_panels(s,w):
    from audits import palette_audit
    audit=palette_audit(s['data']);out='';y=26
    for row in audit['colors']:
        out+=rect(12,y-12,36,21,row['display_color'],LINE)+txt(58,y,row['name'],9)+txt(w-12,y,f'{row["contrast"]:.2f}:1 · '+row['decision'],8,MUTED,'end');y+=35
        out+=txt(58,y-21,row['role']+' · '+row['color'],7,MUTED)
    msg,h=wrap(12,y+8,'Screening only. Contrast applies to the declared role; grayscale is not color-vision certification.',w-24,8,MUTED);out+=msg
    return [{'label':'Color roles on the actual composited background','svg':out,'height':y+h+28,'object_ids':list(s['data']['colors'])}]
def render_svg(s,root):
    validate(s);l=s.get('layout',{});width=l.get('width_mm',178)*72/25.4
    if width<220:raise ValueError('This evidence composition needs at least 78 mm; use fewer columns or a wider figure')
    default_cols=2 if s['kind'] in ('markers','interactive','spatial') and width>460 else 1
    cols=l.get('columns',default_cols);gap=20;outer=18;pw=(width-outer*2-gap*(cols-1))/cols
    if 'panel_width_mm' in l:
        requested=l['panel_width_mm']*72/25.4
        if requested>pw+1e-6:raise ValueError('Requested panel width exceeds page/column capacity')
        pw=requested
    if pw<170:raise ValueError('Requested columns make evidence panels unreadable; reduce columns or enlarge width')
    functions={'heatmap':heat_panels,'oncoprint':onco_panels,'genome':genome_panels,'markers':marker_panels,'interactive':marker_panels,'circos':circos_panels,'palette':palette_panels}
    panels=spatial_panels(s,pw,root) if s['kind']=='spatial' else functions[s['kind']](s,pw)
    maxpan=l.get('page_panels',max(1,l.get('rows',3)*cols))
    if 'rows' in l and maxpan>l['rows']*cols:raise ValueError('page_panels exceeds explicit row/column capacity')
    pages=[]
    for part in chunks(panels,maxpan):
        title_svg,title_h=wrap(18,44,s['title'],width-36,15)
        unit_svg,unit_h=wrap(18,44+title_h+7,s['provenance']['value_unit']+' · independent unit: '+s['provenance']['independent_unit'],width-36,7.5,MUTED)
        header_h=44+title_h+7+unit_h+17
        used_rows=math.ceil(len(part)/cols);rh=[max(p['height'] for p in part[i*cols:(i+1)*cols])+max(wrap(0,0,p['label'],pw,9)[1] for p in part[i*cols:(i+1)*cols])+19 for i in range(used_rows)];required=header_h+sum(rh)+38
        height=l.get('height_mm',required*25.4/72)*72/25.4
        if height+1e-6<required:raise ValueError(f'Height would clip evidence: need at least {required*25.4/72:.1f} mm or paginate with fewer page_panels')
        header=f'<svg xmlns="http://www.w3.org/2000/svg" width="{width*25.4/72:.3f}mm" height="{height*25.4/72:.3f}mm" viewBox="0 0 {width:.3f} {height:.3f}" role="img" aria-labelledby="fig-title fig-description"><title id="fig-title">{esc(s["title"])}</title><desc id="fig-description">{esc(s["alt_text"])}</desc><defs><pattern id="missing" width="5" height="5" patternUnits="userSpaceOnUse"><rect width="5" height="5" fill="#EDF0F3"/><path d="M -1 1 L 1 -1 M 0 5 L 5 0 M 4 6 L 6 4" stroke="#A4AFBA" stroke-width=".6"/></pattern></defs><style>text{{font-family:Arial,Helvetica,sans-serif}} [data-object]:focus{{outline:none;filter:drop-shadow(0 0 2px #172B4D)}} .dim{{opacity:.10}} .selected circle{{stroke:#172B4D;stroke-width:1.1}}</style>'
        svg=header+rect(0,0,width,height,'white')+txt(18,20,'BIORESEARCH · FROZEN RESULTS',7.2,MUTED)+txt(width-18,20,'SYNTHETIC EXAMPLE' if s['provenance']['synthetic'] else s['kind'].upper(),7.2,MUTED,'end')
        svg+=title_svg+unit_svg
        cursor=header_h
        for i,p in enumerate(part):
            row=i//cols;col=i%cols;xx=(width-pw)/2 if len(part)==1 else outer+col*(pw+gap);yy=cursor+sum(rh[:row]);lab,lh=wrap(xx,yy,p['label'],pw,9)
            svg+=lab+f'<g transform="translate({xx} {yy+lh+5})">'+p['svg']+'</g>'
        svg+=line(18,height-29,width-18,height-29)+txt(18,height-16,'Supplied results preserved · '+('software example, not biological evidence' if s['provenance']['synthetic'] else 'see source receipt for selection and limitations'),6.7,MUTED)+txt(width-18,height-16,f'{len(pages)+1}',6.7,MUTED,'end')+'</svg>'
        pages.append({'svg':svg,'width_mm':width*25.4/72,'height_mm':height*25.4/72,'panels':[{k:v for k,v in p.items() if k!='svg'} for p in part]})
    return pages
