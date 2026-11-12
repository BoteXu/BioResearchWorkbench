"""Native local-asset IGV reports for an explicitly selected variant/track scope."""
from pathlib import Path
import sys,re,subprocess,html
from runtime import read,write,sha

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate
    from native_genetics import reference_manifest
    validate(mode,p,verify_versions=True)
    import pysam,pandas as pd,inspect,igv_reports.report as native
    if sha(inspect.getsourcefile(native))!='8d8a29035fde02a98067ac22386ff36afabbd0b5c8ccf45b63d76d3fba0ac53d':raise ValueError('Native IGV report implementation differs from reviewed source')
    assets,members=reference_manifest(inputs['asset_manifest'])
    if not assets.get('source_url') or not assets.get('license') or assets.get('offline_template') not in members:raise ValueError('Exact existing trusted offline IGV template/assets and license required')
    template=members[assets['offline_template']].read_text(encoding='utf8')
    # The template must already embed its reviewed JS/CSS locally. Native
    # --standalone downloads CDN resources, so it is deliberately not used.
    if re.search(r'<(?:script|link|iframe|img|source)\b[^>]*(?:src|href)\s*=\s*[\"\'](?:https?:)?//',template,re.I):raise ValueError('Selected template has live external resources; provision reviewed offline assets first')
    if not all(token in template for token in ['@TABLE_JSON@','@SESSION_DICTIONARY@']):
        # Exact upstream placeholder spelling is source-defined, never guessed.
        import importlib.resources
        original=Path(native.__file__).parent/'templates/variant_template.html'
        original_text=original.read_text(encoding='utf8')
        tokens=set(re.findall(r'@[A-Z_]+@',original_text))
        if not tokens or not tokens<=set(re.findall(r'@[A-Z_]+@',template)):raise ValueError('Offline template lacks the actual native report placeholders')
    csp='<meta http-equiv="Content-Security-Policy" content="default-src &apos;none&apos;; script-src &apos;unsafe-inline&apos;; style-src &apos;unsafe-inline&apos;; connect-src data: blob:; img-src data: blob:; font-src data:; worker-src blob:; frame-src &apos;none&apos;; form-action &apos;none&apos;; base-uri &apos;none&apos;">'
    if '<head>' not in template:raise ValueError('Reviewed report template lacks a head for its offline privacy policy')
    template=template.replace('<head>','<head>\n'+csp,1)
    safe_template=out/'igv_offline_template.html';safe_template.write_text(template,encoding='utf8')
    fasta=inputs['reference_fasta']
    if inputs['reference_fai'].resolve()!=Path(str(fasta)+'.fai').resolve() or inputs['bam_index'].resolve() not in {Path(str(inputs['bam'])+'.bai').resolve(),inputs['bam'].with_suffix('.bai').resolve()}:raise ValueError('Actual existing FASTA/BAM index identities required; no automatic indexing')
    ref=pysam.FastaFile(str(fasta));bam=pysam.AlignmentFile(str(inputs['bam']),'rb',index_filename=str(inputs['bam_index']));rows=[]
    if bam.references!=ref.references or tuple(bam.lengths)!=tuple(ref.lengths):raise ValueError('Actual BAM reference sequences/order/length differ from selected genome; no chr alias rewriting')
    with pysam.VariantFile(str(inputs['variants'])) as variants:
        for i,variant in enumerate(variants):
            if i>=p['maximum_sites']:raise ValueError('Selected IGV report exceeds explicit site budget')
            if variant.contig not in ref.references or variant.ref!=ref.fetch(variant.contig,variant.start,variant.start+len(variant.ref)).upper():raise ValueError('Actual VCF reference allele does not match the selected genome')
            if variant.stop-variant.start>p['maximum_variant_length']:raise ValueError('Structural/split-screen variants require a separately reviewed view contract')
            from itertools import islice
            start=max(0,variant.start-p['flank_bp']);end=min(ref.get_reference_length(variant.contig),variant.stop+p['flank_bp']);n_reads=sum(1 for _ in islice(bam.fetch(variant.contig,start,end),p['maximum_reads_per_site']+1))
            if n_reads>p['maximum_reads_per_site']:raise ValueError('Actual selected view exceeds explicit per-site read budget')
            rows.append({'source_record_index':i,'contig':variant.contig,'position_1based':variant.pos,'source_id':variant.id,'ref':variant.ref,'alt':','.join(variant.alts or []),'region_start_0based':start,'region_end_0based':end,'raw_region_read_count':n_reads})
    ref.close();bam.close()
    if not rows:raise ValueError('No selected actual variant sites; no empty clinical interpretation')
    # Existing package in this exact server interpreter; no public genome URLs,
    # track configs, ID links, remote fetches or arbitrary header HTML admitted.
    args=[sys.executable,'-m','igv_reports.report',str(inputs['variants']),'--fasta',str(fasta),'--tracks',str(inputs['bam']),'--template',str(safe_template),'--output',str(out/'igv_report.html'),'--flanking',str(p['flank_bp']),'--window',str(p['initial_window_bp']),'--exclude-flags',str(p['exclude_flags'])]
    write(out/'igv_command.private.json',{'argv':args,'offline_assets':sha(inputs['asset_manifest']),'public_upload':False,'browser_acceptance':'NOT_RUN'})
    with (out/'igv.stdout.log').open('xb') as so,(out/'igv.stderr.log').open('xb') as se:proc=subprocess.run(args,stdout=so,stderr=se,check=False)
    if proc.returncode:raise RuntimeError('Native IGV report failed; retain actual logs and do not retry automatically')
    result=out/'igv_report.html';text=result.read_text(encoding='utf8')
    if re.search(r'<(?:script|link|iframe|img|source)\b[^>]*(?:src|href)\s*=\s*[\"\'](?:https?:)?//',text,re.I) or re.search(r'@[A-Z_]+@',text) or 'data:' not in text:raise ValueError('Native report has unresolved data/template channels or external assets')
    pd.DataFrame(rows).to_csv(out/'igv_scope.tsv',sep='\t',index=False)
    write(out/'diagnostics.json',{'mode':mode,'software_versions':p['software_versions'],'n_sites':len(rows),'assembly':p['assembly'],'actual_reference_and_alleles_checked':True,'browser_acceptance':'NOT_RUN','scientific_acceptance':'NOT_ESTABLISHED','interpretation':'Actual native IGV report generation from scoped variants and owned BAM/FASTA, existing offline assets. Region raw read counts are scope diagnostics, not variant support/allele balance. HTML contains private data; keep private. Actual browser rendering, strand/mapping/read evidence review and clinical interpretation are separate unverified gates.'})
    outputs=[(result,'genome_browser_report'),(out/'igv_scope.tsv','genome_view_scope'),(out/'igv_command.private.json','native_command'),(out/'diagnostics.json','diagnostics')]
    for name in ['igv.stdout.log','igv.stderr.log']:
        if (out/name).stat().st_size:outputs.append((out/name,'backend_log'))
    write(out/'versions.json',p['software_versions']);outputs.append((out/'versions.json','backend_versions'));return outputs
