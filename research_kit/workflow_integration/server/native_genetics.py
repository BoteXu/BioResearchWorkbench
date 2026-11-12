"""Offline native VEP and LDSC execution using selected existing server software."""
from pathlib import Path
import subprocess,os,re,gzip
from runtime import read,write,sha,selected

def existing_file(value,digest):
    f=Path(value)
    if not f.is_absolute() or not f.is_file() or sha(f)!=digest:raise ValueError('Existing exact source-reviewed server executable/script required')
    return f

def reference_manifest(path):
    manifest=read(path)
    if not isinstance(manifest,dict) or not isinstance(manifest.get('files'),list) or not manifest['files']:raise ValueError('Versioned actual server reference manifest required')
    checked={}
    for row in manifest['files']:
        f=selected(path.parent,row['path'])
        if sha(f)!=row['sha256'] or row['path'] in checked:raise ValueError('Reference bytes changed or duplicate reference member')
        checked[row['path']]=f
    return manifest,checked

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate
    validate(mode,p,verify_versions=True)
    import numpy as np,pandas as pd
    outputs=[];diag={'mode':mode,'software_versions':p['software_versions'],'scientific_acceptance':'NOT_ESTABLISHED'}
    def run(argv):
        env=os.environ.copy();env={k:v for k,v in env.items() if not k.startswith('VEP_')};env.update(HF_HUB_OFFLINE='1',WANDB_MODE='offline')
        write(out/'native_command.private.json',{'argv':[str(x) for x in argv],'automatic_install':False,'remote_database_access':False});outputs.append((out/'native_command.private.json','native_command'))
        with (out/'native.stdout.log').open('xb') as stdout,(out/'native.stderr.log').open('xb') as stderr:
            proc=subprocess.run([str(x) for x in argv],stdout=stdout,stderr=stderr,env=env,check=False)
        for fn,role in [('native.stdout.log','backend_stdout'),('native.stderr.log','backend_stderr')]:
            if (out/fn).stat().st_size:outputs.append((out/fn,role))
        if proc.returncode:raise RuntimeError('Actual native genetics command failed; inspect preserved logs and outputs, never retry automatically')
    if mode=='vep_offline':
        import pysam
        exe=existing_file(p['vep_executable'],p['vep_executable_sha256']);manifest,members=reference_manifest(inputs['cache_manifest'])
        if manifest.get('assembly')!=p['assembly'] or manifest.get('species')!=p['species'] or str(manifest.get('cache_version'))!=str(p['cache_version']):raise ValueError('Native cache assembly/species/version mismatch')
        cache_dir=(inputs['cache_manifest'].parent/manifest['cache_directory']).resolve()
        if not cache_dir.is_relative_to(inputs['cache_manifest'].parent.resolve()) or not cache_dir.is_dir():raise ValueError('Cache directory outside selected reference scope')
        # Fail if a cache file was added/changed without updating the exact manifest.
        actual={f.resolve() for f in cache_dir.rglob('*') if f.is_file()}
        if actual!={f.resolve() for f in members.values()}:raise ValueError('Reference manifest does not cover the exact selected VEP cache tree')
        if inputs['reference_fai'].resolve()!=Path(str(inputs['reference_fasta'])+'.fai').resolve():raise ValueError('Exact existing selected FASTA index required; no automatic index creation')
        if inputs['reference_fasta'].suffix.lower() not in {'.fa','.fasta','.fna'}:raise ValueError('This route requires an existing uncompressed FASTA and index; compressed references need a separately bound GZI route')
        fa=pysam.FastaFile(str(inputs['reference_fasta']));before=[]
        with pysam.VariantFile(str(inputs['variants'])) as source:
            for record in source:
                if len(before)>=p['maximum_variants']:raise ValueError('Selected offline annotation task exceeds reviewed server variant budget')
                if not record.alts or any(not re.fullmatch('[ACGTN]+',alt) for alt in record.alts):raise ValueError('This route supports normalized sequence alleles, not symbolic structural variants')
                if record.contig not in fa.references or fa.fetch(record.contig,record.start,record.start+len(record.ref)).upper()!=record.ref:raise ValueError('Literal input reference allele/contig does not match the selected FASTA; no chr stripping or automatic allele substitution')
                before.append((record.contig,record.pos,record.id,record.ref,tuple(record.alts)))
        fa.close()
        if not before or len(set(before))!=len(before):raise ValueError('Unique nonempty source variant records required')
        config=out/'empty_vep_config.txt';config.write_text('# Explicit empty configuration; no inherited plugins or public database access\n',encoding='utf8');dest=out/'vep_annotated.vcf'
        run([exe,'--config',config,'--offline','--cache','--dir_cache',cache_dir,'--cache_version',str(p['cache_version']),'--assembly',p['assembly'],'--species',p['species'],'--fasta',inputs['reference_fasta'],'--input_file',inputs['variants'],'--format','vcf','--output_file',dest,'--vcf','--allele_number','--fork',str(p['threads']),'--no_stats'])
        after=[];rows=[];n_without=0
        with pysam.VariantFile(str(dest)) as result:
            if 'CSQ' not in result.header.info:raise ValueError('Native annotated VCF lacks the CSQ schema')
            desc=result.header.info['CSQ'].description
            if 'Format: ' not in desc:raise ValueError('Native consequence schema cannot be read explicitly')
            fields=desc.split('Format: ',1)[1].strip().split('|')
            if 'ALLELE_NUM' not in fields:raise ValueError('Exact multi-allele consequence linkage absent')
            for record in result:
                ident=(record.contig,record.pos,record.id,record.ref,tuple(record.alts or []));after.append(ident);csq=record.info.get('CSQ',())
                if not csq:n_without+=1
                for text in csq:
                    values=text.split('|')
                    if len(values)!=len(fields):raise ValueError('Malformed native CSQ record')
                    row=dict(zip(fields,values));idx=int(row['ALLELE_NUM'])-1
                    if not 0<=idx<len(record.alts):raise ValueError('Consequence allele index outside literal source ALT axis')
                    rows.append({'source_contig':record.contig,'source_pos':record.pos,'source_id':record.id,'source_ref':record.ref,'source_alt':record.alts[idx],**row})
        if after!=before:raise ValueError('Native annotation changed, removed, duplicated or reordered source variants')
        if not rows:raise ValueError('No actual consequence annotations; do not interpret as harmless variants')
        table=pd.DataFrame(rows);table.to_csv(out/'vep_consequences.tsv',sep='\t',index=False);outputs.extend([(dest,'annotated_variants'),(out/'vep_consequences.tsv','variant_consequences')]);diag.update(n_variants=len(before),n_consequences=len(rows),n_variants_without_consequence=n_without,source_variant_identity_unchanged=True,cache_version=p['cache_version'],assembly=p['assembly'],interpretation='Offline reference-conditional transcript consequences; absence of annotation is unknown, not benign. Not a ClinVar classification or clinical interpretation')
    elif mode=='ldsc_h2':
        interpreter=Path(p['python_executable']);script=existing_file(p['ldsc_script'],p['ldsc_script_sha256'])
        if not interpreter.is_absolute() or not interpreter.is_file():raise ValueError('Existing LDSC-compatible server interpreter required')
        manifest,members=reference_manifest(inputs['reference_manifest'])
        if manifest.get('assembly')!=p['assembly'] or manifest.get('ancestry')!=p['ancestry'] or not manifest.get('source_citation'):raise ValueError('LD-score reference ancestry, assembly and source must match the reviewed task')
        prefixes=[]
        for key in ['ref_ld_chr_prefix','weight_ld_chr_prefix']:
            value=manifest.get(key)
            if not isinstance(value,str) or ',' in value or '\\' in value or value.startswith('/') or '..' in Path(value).parts:raise ValueError('Single selected project-relative LD-score prefix required')
            prefix=(inputs['reference_manifest'].parent/value).resolve()
            if not prefix.is_relative_to(inputs['reference_manifest'].parent.resolve()):raise ValueError('LD-score prefix escapes selected reference scope')
            for chrom in range(1,23):
                fn=Path(str(prefix)+str(chrom)+'.l2.ldscore.gz')
                if fn.resolve() not in {f.resolve() for f in members.values()}:raise ValueError('All 22 autosomal LD-score reference files must be explicitly bound')
                if key=='ref_ld_chr_prefix' and Path(str(prefix)+str(chrom)+'.l2.M_5_50').resolve() not in {f.resolve() for f in members.values()}:raise ValueError('Default LDSC common-SNP M_5_50 counts must be bound for every autosome')
            prefixes.append(prefix)
        summary=pd.read_csv(inputs['sumstats'],sep=r'\s+',compression='infer',dtype={'SNP':str,'A1':str,'A2':str})
        if not {'SNP','A1','A2','Z','N'}<=set(summary) or summary.SNP.duplicated().any() or summary[['SNP','A1','A2','Z','N']].isna().any().any():raise ValueError('Actual author-munged unique SNP/A1/A2/Z/N summary statistics required')
        values=summary[['Z','N']].to_numpy(float)
        if not np.isfinite(values).all() or (summary.N<=0).any() or not summary.A1.isin(list('ACGT')).all() or not summary.A2.isin(list('ACGT')).all() or (summary.A1==summary.A2).any():raise ValueError('Finite signed statistics, positive effective N and actual distinct nucleotide alleles required')
        run([interpreter,script,'--h2',inputs['sumstats'],'--ref-ld-chr',prefixes[0],'--w-ld-chr',prefixes[1],'--out',out/'ldsc'])
        log=out/'ldsc.log'
        if not log.is_file():raise ValueError('No actual native LDSC log returned')
        text=log.read_text(encoding='utf8',errors='strict');number=r'([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)';metrics={}
        for key,label in [('h2','Total Observed scale h2'),('intercept','Intercept')]:
            found=re.findall(re.escape(label)+r':\s*'+number+r'\s*\(\s*'+number+r'\s*\)',text)
            if len(found)!=1:raise ValueError('Native LDSC summary format differs or is incomplete; review actual log, do not fabricate a point estimate')
            value,se=map(float,found[0]);metrics[key]=value;metrics[key+'_se']=se
            if not np.isfinite([value,se]).all() or se<0:raise ValueError('Invalid native LDSC estimate/uncertainty')
        write(out/'ldsc_estimates.json',metrics);outputs.extend([(log,'native_ldsc_log'),(out/'ldsc_estimates.json','heritability_estimates')]);diag.update(n_input_snps=len(summary),assembly=p['assembly'],ancestry=p['ancestry'],observed_scale_h2=metrics['h2'],h2_se=metrics['h2_se'],interpretation='Native common-SNP observed-scale LDSC h2/intercept under matched LD reference assumptions. Negative/noisy estimates retained; no automatic liability-scale conversion, genetic correlation or causal interpretation')
    else:raise ValueError('Unrecognized fixed native genetics route')
    write(out/'native_diagnostics.json',diag);outputs.append((out/'native_diagnostics.json','diagnostics'));write(out/'native_versions.json',p['software_versions']);outputs.append((out/'native_versions.json','backend_versions'));return outputs
