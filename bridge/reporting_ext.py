"""Offline readable HTML reports and result review; escaped content, no external resources or active scripts."""
import csv
import hashlib
import html
import json
from pathlib import Path
from urllib.parse import quote


def render_report(folder,data):
    folder=Path(folder)
    esc=lambda v:html.escape(str(v),quote=True)
    title=esc(data.get('workflow','Analysis report').replace('_',' '))
    sections=['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\' data:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'"><title>'+title+'</title><style>body{font:16px system-ui,sans-serif;color:#183044;background:#f5f7fa;margin:0}main{max-width:1100px;margin:auto;padding:24px}section{background:white;padding:20px;margin:16px 0;border-radius:10px;overflow:auto}h1,h2{line-height:1.3}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid #dbe3e8;padding:8px;text-align:left;vertical-align:top}th{background:#edf3f6}pre{white-space:pre-wrap;overflow-wrap:anywhere}img{max-width:100%;height:auto}a{color:#075b8c}.notice{border-left:5px solid #d29a30;padding:12px;background:#fff6df}</style></head><body><main><h1>'+title+'</h1><p class="notice">Engineering completion does not establish scientific validity. Review units, source provenance, design, QC, uncertainty and limitations.</p>']
    context=data.get('context',{})
    if context:
        sections.append('<section><h2>Study and input context</h2><table>'+''.join('<tr><th>'+esc(k)+'</th><td>'+esc(v)+'</td></tr>' for k,v in context.items())+'</table></section>')
    important={k:v for k,v in data.items() if k not in {'outputs','context','output_directory','limitations','input_hashes'}}
    sections.append('<section><h2>QC, design and analysis summary</h2><pre>'+esc(json.dumps(important,indent=2,ensure_ascii=False))+'</pre></section>')
    limits=data.get('limitations',[])
    if limits: sections.append('<section><h2>Interpretation limits</h2><ul>'+''.join('<li>'+esc(v)+'</li>' for v in limits)+'</ul></section>')
    rows=[]
    for item in data.get('outputs',[]):
        name=item['name'];path=(folder/name).resolve();path.relative_to(folder.resolve())
        href=quote(name,safe='/')
        rows.append('<tr><td><a href="'+esc(href)+'">'+esc(name)+'</a></td><td>'+esc(item['bytes'])+'</td><td>'+esc(item['sha256'])+'</td></tr>')
        if path.suffix.lower()=='.png': sections.append('<section><h2>'+esc(name)+'</h2><img src="'+esc(href)+'" alt="'+esc(name)+'"></section>')
        if path.suffix.lower()=='.csv' and path.stat().st_size<=10000000:
            with path.open(encoding='utf-8-sig',newline='') as f:
                reader=csv.reader(f);header=next(reader,[]);preview=[]
                for i,row in enumerate(reader):
                    if i==10: break
                    preview.append(row[:12])
            sections.append('<section><h2>'+esc(name)+' — first ten rows</h2><table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in header[:12])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in preview)+'</tbody></table><p>Preview only; open the complete file for all rows and columns.</p></section>')
    sections.append('<section><h2>Complete output manifest</h2><table><tr><th>File</th><th>Bytes</th><th>SHA256</th></tr>'+''.join(rows)+'</table></section></main></body></html>')
    (folder/'report.html').write_text(''.join(sections),encoding='utf8')


def audit_analysis_result(summary_path: str, expected_contrast: str, expected_units: dict = None) -> dict:
    """Check a returned analysis summary, output hashes, context, QC gate and expected contrast; do not infer biological truth."""
    path=Path(summary_path).resolve(strict=True)
    if path.stat().st_size>10000000: raise ValueError('Summary exceeds bounded review size')
    data=json.loads(path.read_text(encoding='utf8'));root=path.parent;issues=[];files=[]
    for item in data.get('outputs',[]):
        relative=Path(item['name'])
        if relative.is_absolute() or '..' in relative.parts: raise ValueError('Unsafe output manifest path')
        p=(root/relative).resolve();p.relative_to(root)
        ok=p.is_file() and p.stat().st_size==item['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
        files.append({'name':item['name'],'integrity_pass':ok})
        if not ok: issues.append('output_integrity_failed:'+item['name'])
    if not files: issues.append('missing_output_manifest')
    context=data.get('context',{})
    if context.get('contrast')!=expected_contrast: issues.append('contrast_context_mismatch')
    if expected_units and data.get('biological_units')!=expected_units: issues.append('independent_unit_count_mismatch_or_unavailable')
    qc=data.get('preanalysis_qc',{})
    if data.get('workflow') in {'bulk_rnaseq','normalized_expression','designed_expression'} and qc.get('qc_gate_pass') is not True: issues.append('missing_passed_preanalysis_qc')
    if not context or not data.get('limitations'): issues.append('missing_interpretation_context')
    return {'success':True,'review_gate_pass':not issues,'issues':issues,'files':files,'workflow':data.get('workflow'),'limitations':['Context and unit counts are caller-declared; source verification remains necessary.','Hash matching does not establish model validity, correct thresholds or truth of scientific claims.','A complete review includes full result tables and diagnostics, not only significant rows.']}
