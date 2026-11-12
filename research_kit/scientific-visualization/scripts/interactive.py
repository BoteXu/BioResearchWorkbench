"""Offline interaction outputs with real payloads, not structural placeholders."""
from pathlib import Path
import json,html,re,base64

def _json(x):return json.dumps(x,ensure_ascii=False,allow_nan=False).replace('<','\\u003c')
def _save(text,outdir,stem,overwrite=False):
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]*',stem) or '..' in stem:raise ValueError('Plain output stem required')
    p=Path(outdir)/(stem+'.html');p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists() and not overwrite:raise FileExistsError(p)
    css=''
    for suffix,weight in [('Regular',400),('Bold',700)]:
        font=Path(__file__).resolve().parents[1]/'assets/fonts'/('LiberationSans-'+suffix+'.ttf')
        css+='@font-face{font-family:"Liberation Sans";font-weight:'+str(weight)+';src:url(data:font/ttf;base64,'+base64.b64encode(font.read_bytes()).decode()+')}\n'
    text=text.replace('<style>','<style>'+css,1).replace("worker-src blob:;","worker-src blob:; font-src data:;")
    p.write_text(text,encoding='utf8');return p

def molecular_view(data,outdir,stem='fig_pose3d',overwrite=False):
    js=(Path(__file__).resolve().parents[1]/'assets/viewer/3Dmol-min.js').read_text(encoding='utf8')
    if not data.get('pdb') and not data.get('cube'):raise ValueError('Actual molecular PDB or orbital/field cube required')
    payload=_json(data)
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; worker-src blob:;"><title>Scientific molecular viewer</title><style>body{margin:0;color:#253442;font:15px 'Liberation Sans',Arial;background:white}header{padding:18px 24px;border-bottom:1px solid #dce4e9}h1{font-size:22px;margin:0 0 8px}button,select,input{margin-right:8px;padding:6px}#viewer{width:100%;height:720px;position:relative}#status{color:#617281}</style><header><h1 id="title"></h1><button id="rotate">Rotate</button><button id="reset">Reset view</button><select id="style"><option value="cartoon">Cartoon</option><option value="stick">Stick</option><option value="sphere">Sphere</option></select><label>Frame <input type="range" id="frame" min="0" max="0" value="0"></label><span id="status"></span></header><div id="viewer"></div><script>'''+js+'''</script><script>
const DATA='''+payload+''';const v=$3Dmol.createViewer('viewer',{backgroundColor:'white'});window.viewer=v;
document.getElementById('title').textContent=DATA.title||'Molecular structure';
let models=[];if(DATA.frames&&DATA.frames.length){for(let f of DATA.frames)models.push(v.addModel(f,'pdb'));for(let m of models)m.hide();models[0].show();}else if(DATA.pdb){models.push(v.addModel(DATA.pdb,'pdb'));}
document.getElementById('style').value=DATA.default_style||'stick';
function style(){let mode=document.getElementById('style').value;v.setStyle({},{[mode]:{colorscheme:'Jmol',radius:mode==='sphere'?.65:.16}});if(mode==='cartoon')v.setStyle({hetflag:true},{stick:{colorscheme:'Jmol',radius:.18}});v.render();}
if(DATA.cube){
 if(!models.length)models.push(v.addModel(DATA.cube,'cube'));
 if(DATA.render_mode==='volume'){
  v.addVolumetricRender(new $3Dmol.VolumeData(DATA.cube,'cube'),{transferfn:DATA.transferfn||[{value:-.1,color:'#3B6F91',opacity:.2},{value:-.02,color:'#3B6F91',opacity:.12},{value:0,color:'white',opacity:0},{value:.02,color:'#CA7354',opacity:.12},{value:.1,color:'#CA7354',opacity:.2}],subsamples:5});
 }else{v.addVolumetricData(DATA.cube,'cube',{isoval:DATA.isovalue||.03,color:'#CA7354',opacity:.75});v.addVolumetricData(DATA.cube,'cube',{isoval:-(DATA.isovalue||.03),color:'#3B6F91',opacity:.75});}
}
style();v.zoomTo();v.rotate(20,'x');v.rotate(25,'y');v.zoom(1.2);v.render();let spinning=false;
document.getElementById('rotate').onclick=()=>{spinning=!spinning;v.spin('y',spinning?.7:0);};
document.getElementById('reset').onclick=()=>{v.spin('y',0);spinning=false;v.zoomTo();v.render();};
document.getElementById('style').onchange=style;
const slider=document.getElementById('frame');slider.max=Math.max(0,models.length-1);slider.disabled=models.length<2;
slider.oninput=()=>{for(let m of models)m.hide();models[+slider.value].show();v.render();document.getElementById('status').textContent='Frame '+slider.value+(DATA.times?' · '+DATA.times[+slider.value]+' ns':'');};
document.getElementById('status').textContent=(DATA.cube?(DATA.render_mode==='volume'?'Volumetric ray rendering · supplied orbital field':'Orbital isosurfaces'):(models.length+' supplied structure frame(s)'))+' · offline';window.renderReady=true;
if(DATA.cube){let key=document.createElement('p');key.style.cssText='margin:10px 0 0;color:#617281;font-size:13px';key.textContent='Blue: negative field; coral: positive field. '+(DATA.render_mode==='volume'?'Transfer-function volume rendering.':'Isosurfaces: ±'+(DATA.isovalue||.03)+'.')+' Units: '+(DATA.field_unit||'supplied field units')+'.';document.querySelector('header').append(key);}
</script></html>'''
    return _save(page,outdir,stem,overwrite)

def embedding_view(data,outdir,stem='fig_umap_dashboard',overwrite=False,theme=None):
    import numpy as np
    xy=np.asarray(data['embedding'],float)
    if xy.ndim!=2 or xy.shape[1]!=2 or not np.isfinite(xy).all():raise ValueError('Finite two-dimensional stored coordinates required')
    if len(xy)!=len(data['groups']) or len(xy)!=len(data['sample_ids']) or len(set(data['sample_ids']))!=len(xy):raise ValueError('Unique aligned observation identities required')
    from design_system import identity_colors
    data={**data,'identity_colors':data.get('identity_colors') or identity_colors(dict(theme or {}),data['group_order'])}
    p=_json(data)
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Embedding explorer</title><style>body{font:15px 'Liberation Sans',Arial;color:#253442;margin:24px;background:white}h1{font-size:23px}button,select{padding:7px;margin-right:8px}svg{display:block;border:1px solid #e2e8ec;max-width:1100px;width:100%;height:auto}#tip{position:fixed;pointer-events:none;background:white;border:1px solid #c5d0d8;padding:6px;display:none}circle{cursor:crosshair}#legend{padding:12px 0}</style><h1>Supplied cell embedding · identity explorer</h1><label>Identity <select id="group"></select></label><button id="reset">Reset</button><span id="count"></span><div id="legend"></div><svg id="plot" viewBox="0 0 1100 700"></svg><div id="tip"></div><script>
const DATA='''+p+''';const s=document.getElementById('plot'),ns='http://www.w3.org/2000/svg',sel=document.getElementById('group'),tip=document.getElementById('tip');let colors=['#3B6F91','#CA7354','#4C9685','#9279AE','#BE9848','#6E91AD','#B17890','#879878'];
const groups=DATA.group_order;colors=groups.map(g=>DATA.identity_colors[g]);let all=document.createElement('option');all.textContent='All';all.value='All';sel.append(all);for(let g of groups){let o=document.createElement('option');o.value=g;o.textContent=g;sel.append(o);}let xs=DATA.embedding.map(x=>x[0]),ys=DATA.embedding.map(x=>x[1]),xmin=Math.min(...xs),xmax=Math.max(...xs),ymin=Math.min(...ys),ymax=Math.max(...ys);if(xmax===xmin)xmax=xmin+1;if(ymax===ymin)ymax=ymin+1;
const scale=Math.min(1020/(xmax-xmin),620/(ymax-ymin)),cx=(xmin+xmax)/2,cy=(ymin+ymax)/2;window.coordinateScale={x:scale,y:scale};
function draw(){s.replaceChildren();let n=0;DATA.embedding.forEach((xy,i)=>{if(sel.value!=='All'&&DATA.groups[i]!==sel.value)return;let c=document.createElementNS(ns,'circle');c.setAttribute('cx',550+(xy[0]-cx)*scale);c.setAttribute('cy',350-(xy[1]-cy)*scale);c.setAttribute('r',DATA.embedding.length<50?5:2.3);c.setAttribute('fill',colors[groups.indexOf(DATA.groups[i])]);c.setAttribute('opacity',.78);c.onmousemove=e=>{tip.textContent=DATA.sample_ids[i]+' · '+DATA.groups[i];tip.style.cssText='display:block;left:'+(e.clientX+12)+'px;top:'+(e.clientY+12)+'px';};c.onmouseleave=()=>tip.style.display='none';s.append(c);n++;});document.getElementById('count').textContent=n+' observations';}sel.onchange=draw;document.getElementById('reset').onclick=()=>{sel.value='All';draw();};document.getElementById('legend').textContent='Stored UMAP coordinates; no embedding fitted here. Select a cell identity; hover for exact cell ID.';draw();
document.querySelector('h1').textContent='Supplied '+(DATA.coordinate_type||'UMAP')+' coordinates · identity explorer';
document.getElementById('legend').textContent='Select an identity or hover for its exact observation ID. Coordinates remain fixed.';
let legend=document.createElement('div');legend.style.cssText='display:flex;flex-wrap:wrap;gap:12px;padding:0 0 14px';
groups.forEach((g,i)=>{let item=document.createElement('span');let dot=document.createElement('span');dot.style.cssText='display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;background:'+colors[i];item.append(dot,document.createTextNode(g));legend.append(item);});s.before(legend);
window.renderReady=true;
</script></html>'''
    return _save(page,outdir,stem,overwrite)

__all__=['molecular_view','embedding_view']
