"""Private visual increments: actual frozen displays and scoped adapters, never analysis fitting."""
from pathlib import Path
import argparse,json,sys,copy
from contracts import KINDS,read,write,sha,digest,validate

def render(s,root,out):
    from display import render_svg
    validate(s);data_before=digest(s['data']);pages=render_svg(s,Path(root));out=Path(out);out.mkdir(parents=True,exist_ok=False)
    write(out/'source.figure.json',s);files=[]
    for i,page in enumerate(pages,1):
        f=out/f'figure_{i:02}.svg';f.write_text(page['svg'],encoding='utf8');files.append({'path':f.name,'sha256':sha(f),'width_mm':page['width_mm'],'height_mm':page['height_mm'],'panels':page['panels']})
        if s['kind']=='interactive' and 'data-object=' in page['svg']:
            from interactive import viewer
            h=out/f'viewer_{i:02}.html';h.write_text(viewer(page['svg'],s,digest(s)),encoding='utf8');files.append({'path':h.name,'sha256':sha(h)})
    if digest(s['data'])!=data_before:raise ValueError('Renderer altered frozen input')
    if s['kind']=='palette':
        from audits import palette_audit
        write(out/'palette_screen.json',palette_audit(s['data']))
    receipt={'schema':'private-visual-receipt/1','state':'RENDERED_UNREVIEWED','kind':s['kind'],'input_spec_sha256':digest(s),'frozen_data_sha256':data_before,'source_sha256':{f.name:sha(f) for f in Path(__file__).parent.glob('*.py')},'files':files,'provenance':s['provenance'],'analysis_fitted':False,'input_mutated':False,'visual_acceptance':False,'scientific_acceptance':'NOT_ESTABLISHED','public_upload':False};write(out/'receipt.private.json',receipt);return receipt

def gallery(out,scale_cases=False):
    from examples import example
    out=Path(out);out.mkdir(parents=True,exist_ok=False);records=[]
    for kind in KINDS:
        for size in (['small','medium','large'] if scale_cases else ['medium']):
            s=example(kind,size);name=kind+'_'+size;receipt=render(s,out,out/name);records.append({'id':name,'kind':kind,'size':size,'path':name,'pages':len([f for f in receipt['files'] if f['path'].endswith('.svg')])})
    # Layout changes keep values/identity fixed, not alternative scientific results.
    for kind in KINDS:
        s=example(kind,'medium');s['layout'].update(width_mm=260,columns=2 if kind in ('spatial','markers','interactive') else 1,page_panels=2);name=kind+'_custom';r=render(s,out,out/name);records.append({'id':name,'kind':kind,'size':'custom layout','path':name,'pages':len([f for f in r['files'] if f['path'].endswith('.svg')])})
    write(out/'index.private.json',records)
    import html
    cards=[]
    for r in records:
        frames=''.join(f'<object type="image/svg+xml" data="{r["path"]}/figure_{i:02}.svg" aria-label="{html.escape(r["id"])} page {i}"></object>' for i in range(1,r['pages']+1));cards.append('<section id="'+r['id']+'"><h2>'+r['id']+'</h2>'+frames+'</section>')
    links=' '.join(f'<a href="#{r["id"]}">{r["id"]}</a>' for r in records)
    (out/'index.html').write_text('<!doctype html><html><meta charset="utf-8"><title>Private visual increments</title><style>body{font:16px Arial;margin:24px;background:#edf2f6;color:#20354b}nav{line-height:2}nav a{margin-right:12px}section{margin:36px auto;max-width:1400px}object{display:block;width:100%;min-height:640px;margin:16px auto;background:white;border:1px solid #dce4ea}</style><h1>Frozen visual increments · actual synthetic examples</h1><p>Software display fixtures; not biological evidence. Every SVG is editable. Actual visual review is separate.</p><nav>'+links+'</nav>'+''.join(cards)+'</html>',encoding='utf8')
    return {'state':'GALLERY_RENDERED_UNREVIEWED','cases':len(records),'pages':sum(r['pages'] for r in records),'analysis_fitted':False}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('catalog')
    ex=sub.add_parser('example');ex.add_argument('kind',choices=KINDS);ex.add_argument('--size',choices=['small','medium','large'],default='medium');ex.add_argument('--output',required=True,type=Path)
    pl=sub.add_parser('plan');pl.add_argument('--spec',required=True,type=Path);pl.add_argument('--output',required=True,type=Path)
    rr=sub.add_parser('render');rr.add_argument('--spec',required=True,type=Path);rr.add_argument('--output',required=True,type=Path)
    gg=sub.add_parser('gallery');gg.add_argument('--output',required=True,type=Path);gg.add_argument('--scale-cases',action='store_true')
    aa=sub.add_parser('audit');aa.add_argument('--file',required=True,type=Path);aa.add_argument('--width-mm',type=float);aa.add_argument('--min-dpi',type=float,default=300);aa.add_argument('--output',type=Path)
    dd=sub.add_parser('document-export');dd.add_argument('--svg',required=True,type=Path);dd.add_argument('--output',required=True,type=Path);dd.add_argument('--preview-width',type=int,default=1400)
    nt=sub.add_parser('native-plan');nt.add_argument('--spec',required=True,type=Path);nt.add_argument('--backend',choices=['Gviz','pyGenomeTracks'],required=True);nt.add_argument('--assets',type=Path);nt.add_argument('--output',type=Path,required=True)
    a=p.parse_args(argv)
    if a.command=='catalog':result={'version':'1.0-private','routes':KINDS,'export_metadata_audit':True,'native_adapters':['AnnData frozen snapshot','pyGenomeTracks','Gviz'],'server_native_runtime':'NOT_RUN_SERVER_UNAVAILABLE','graphics_runtime':'see exact render and review receipts','public_upload':False}
    elif a.command=='example':
        from examples import example
        s=example(a.kind,a.size);validate(s);write(a.output,s);result={'state':'SYNTHETIC_SPEC_EXPORTED','kind':a.kind}
    elif a.command=='plan':
        s=read(a.spec);validate(s);from display import render_svg
        pages=render_svg(s,a.spec.resolve().parent);result={'state':'PREFLIGHT_ONLY','source_sha256':sha(a.spec),'pages':[{k:v for k,v in q.items() if k!='svg'} for q in pages],'analysis_fitted':False};write(a.output,result)
    elif a.command=='render':result=render(read(a.spec),a.spec.resolve().parent,a.output)
    elif a.command=='gallery':result=gallery(a.output,a.scale_cases)
    elif a.command=='audit':
        from audits import inspect
        result=inspect(a.file,a.width_mm,a.min_dpi)
        if a.output:write(a.output,result)
    elif a.command=='document-export':
        from audits import export_document
        result=export_document(a.svg,a.output,a.preview_width)
    else:
        from native_tracks import native_plan
        result=native_plan(read(a.spec),a.output,a.backend,read(a.assets) if a.assets else None)
    print(json.dumps(result,ensure_ascii=False,allow_nan=False));return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,KeyError,TypeError,OSError) as e:print(json.dumps({'state':'HOLD','error':str(e),'analysis_fitted':False,'public_upload':False},ensure_ascii=False));raise SystemExit(2)
