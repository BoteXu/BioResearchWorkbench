"""Prepare fixed native track commands and data; preparation is never dispatch."""
from pathlib import Path
import json,csv,re
from contracts import validate,write,sha,num,digest
def native_plan(s,out,backend,assets=None):
    validate(s)
    if s['kind']!='genome' or backend not in ('pyGenomeTracks','Gviz'):raise ValueError('Native track preparation requires frozen genome specification')
    out=Path(out);out.mkdir(parents=True,exist_ok=False);d=s['data'];manifest=[]
    for i,t in enumerate(d['tracks']):
        if any(ch in t['label'] for ch in ('\n','\r','[',']')):raise ValueError('Track label cannot inject native configuration sections')
        f=out/f'track_{i}.tsv';keys=list(dict.fromkeys(k for row in t['records'] for k in row))
        with f.open('x',encoding='utf8',newline='') as stream:
            wr=csv.DictWriter(stream,fieldnames=keys,delimiter='\t');wr.writeheader()
            for r in t['records']:wr.writerow({k:json.dumps(v) if isinstance(v,list) else v for k,v in r.items()})
        manifest.append({'id':t['id'],'kind':t['kind'],'unit':t['unit'],'limits':t.get('limits'),'path':f.name,'sha256':sha(f),'normalization':t['normalization']})
    if backend=='pyGenomeTracks':
        # Native file formats must be supplied explicitly, not inferred from frozen tables.
        if not isinstance(assets,list) or len(assets)!=len(d['tracks']):raise ValueError('Provide one reviewed server-side native asset for every track')
        sections=[]
        for i,(t,a) in enumerate(zip(d['tracks'],assets)):
            if set(a)!={'track_id','path','sha256','file_type'} or a['track_id']!=t['id'] or a['file_type'] not in ('bigwig','bed','gtf','links','hic_matrix'):raise ValueError('Explicit native track format/identity required')
            allowed={'coverage':{'bigwig'},'peaks':{'bed'},'genes':{'gtf','bed'},'loops':{'links'},'hic':{'hic_matrix'}}
            if a['file_type'] not in allowed[t['kind']]:raise ValueError('Native format does not match track semantics')
            if not re.fullmatch('[a-f0-9]{64}',a['sha256']) or not re.fullmatch(r'[A-Za-z0-9_./-]+',a['path']) or a['path'].startswith('/') or '..' in Path(a['path']).parts:raise ValueError('Use a reviewed relative staged native asset name and SHA256')
            body=f'[track_{i}]\nfile = {a["path"]}\nfile_type = {a["file_type"]}\ntitle = {t["label"]}\nheight = 2\n'
            if t['kind']=='coverage':body+=f'min_value = {t["limits"][0]}\nmax_value = {t["limits"][1]}\n'
            sections.append(body)
        (out/'tracks.ini').write_text('\n'.join(sections)+'\n[x-axis]\n',encoding='utf8')
        argv=['pyGenomeTracks','--tracks','tracks.ini','--region',f'{d["chromosome"]}:{int(d["region"][0])}-{int(d["region"][1])}','--outFileName','native_tracks.pdf','--width',str(s.get('layout',{}).get('width_mm',178)/10)]
    else:
        if any(t['kind'] not in ('coverage','peaks','genes') for t in d['tracks']):raise ValueError('Gviz adapter supports frozen coverage/peaks/gene intervals; use main SVG or pyGenomeTracks for loops/Hi-C')
        r=['suppressPackageStartupMessages(library(Gviz))','suppressPackageStartupMessages(library(GenomicRanges))',"tr <- list()"]
        for i,t in enumerate(d['tracks']):
            r.append(f'd <- read.delim("track_{i}.tsv", stringsAsFactors=FALSE)');q=json.dumps
            if t['kind']=='coverage':r.append(f'tr[[{i+1}]] <- DataTrack(start=d$start+1,end=d$end,data=d$value,chromosome={q(d["chromosome"])},genome={q(d["assembly"])},name={q(t["label"]+" ["+t["unit"]+"]")},type="histogram",ylim=c({t["limits"][0]},{t["limits"][1]}))')
            elif t['kind']=='genes':
                ef=out/f'exons_{i}.tsv'
                with ef.open('x',encoding='utf8',newline='') as stream:
                    wr=csv.DictWriter(stream,fieldnames=['start','end','gene','transcript','symbol','strand','exon'],delimiter='\t');wr.writeheader()
                    for gi,g in enumerate(t['records']):
                        for ei,(a,b) in enumerate(g.get('exons',[])):wr.writerow({'start':a+1,'end':b,'gene':f'gene_{gi}','transcript':f'transcript_{gi}','symbol':g.get('label',f'gene_{gi}'),'strand':g['strand'],'exon':f'exon_{gi}_{ei}'})
                r+= [f'e <- read.delim("exons_{i}.tsv", stringsAsFactors=FALSE)',f'gr <- GRanges(seqnames={q(d["chromosome"])},ranges=IRanges(e$start,e$end),strand=e$strand,gene=e$gene,transcript=e$transcript,symbol=e$symbol,exon=e$exon)',f'tr[[{i+1}]] <- GeneRegionTrack(gr, genome={q(d["assembly"])},chromosome={q(d["chromosome"])},name={q(t["label"])},transcriptAnnotation="symbol")']
            else:r.append(f'tr[[{i+1}]] <- AnnotationTrack(start=d$start+1,end=d$end,chromosome={q(d["chromosome"])},genome={q(d["assembly"])},name={q(t["label"])})')
        r+=['pdf("native_tracks.pdf", width='+str(s.get('layout',{}).get('width_mm',178)/25.4)+', height='+str(max(3,len(d['tracks'])*.65))+')',f'plotTracks(tr,from={d["region"][0]+1},to={d["region"][1]},chromosome={json.dumps(d["chromosome"])})','dev.off()']
        (out/'native_tracks.R').write_text('\n'.join(r)+'\n',encoding='utf8');argv=['Rscript','--vanilla','native_tracks.R']
    plan={'schema':'native-track-render/1','state':'PREPARED_NOT_DISPATCHED','backend':backend,'argv':argv,'frozen_tracks':manifest,'native_assets':assets or [],'dispatch_authorized':False,'expected_host':'REQUIRED_CURRENT_COMPUTE_HOST','node_role':'compute','expected_executable_sha256':'REQUIRED_EXISTING_SERVER_BINARY_SHA256','expected_versions':{},'native_backend_runtime':'NOT_RUN_SERVER_UNAVAILABLE','analysis_performed':False,'public_upload':False,'generated_files':[{'path':f.name,'sha256':sha(f)} for f in sorted(out.iterdir()) if f.is_file()]};plan['review_sha256']=digest({k:v for k,v in plan.items() if k not in ('dispatch_authorized','review_sha256')});write(out/'native_plan.json',plan)
    return plan
