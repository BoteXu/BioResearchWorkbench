"""Native SMR/HEIDI with selected offline GWAS/QTL/LD sources and exact alleles."""
from pathlib import Path
import subprocess,os,math
from runtime import read,write,sha

def analyze(inputs,p,out,mode):
    from native_teaching_contracts import validate
    from native_genetics import existing_file,reference_manifest
    validate(mode,p,verify_versions=True)
    import pandas as pd,numpy as np
    exe=existing_file(p['smr_executable'],p['smr_executable_sha256']);manifest,members=reference_manifest(inputs['reference_manifest']);scope=inputs['reference_manifest'].parent.resolve()
    for k in ['assembly','ancestry']:
        if manifest.get(k)!=p[k]:raise ValueError('Actual QTL/LD ancestry or reference assembly differs')
    if not manifest.get('qtl_source') or not manifest.get('ld_source') or not manifest.get('sample_overlap_assessment'):raise ValueError('Actual QTL/LD provenance and GWAS-QTL sample-overlap assessment required')
    def prefix(key,suffixes):
        name=manifest.get(key)
        if not isinstance(name,str) or not name or '\\' in name or name.startswith('/') or '..' in Path(name).parts:raise ValueError('Selected relative native resource prefix required')
        path=(scope/name).resolve()
        if not path.is_relative_to(scope):raise ValueError('Reference prefix escapes selected scope')
        paths=[Path(str(path)+suffix) for suffix in suffixes]
        if any(q.resolve() not in {v.resolve() for v in members.values()} for q in paths):raise ValueError('Every actual native reference component must be hash-bound')
        return path,paths
    ld,ldfiles=prefix('plink_prefix',['.bed','.bim','.fam']);qtl,qtlfiles=prefix('qtl_prefix',['.besd','.esi','.epi'])
    with ldfiles[0].open('rb') as bed:
        if bed.read(3)!=b'\x6c\x1b\x01':raise ValueError('Actual SNP-major PLINK binary LD reference required')
    bim=pd.read_csv(ldfiles[1],sep=r'\s+',header=None,dtype=str,keep_default_na=False);fam=pd.read_csv(ldfiles[2],sep=r'\s+',header=None,dtype=str,keep_default_na=False);esi=pd.read_csv(qtlfiles[1],sep=r'\s+',header=None,dtype=str,keep_default_na=False);epi=pd.read_csv(qtlfiles[2],sep=r'\s+',header=None,dtype=str,keep_default_na=False)
    if bim.shape[1]!=6 or esi.shape[1]!=7 or epi.shape[1]!=6 or fam.shape[1]!=6 or any(z.iloc[:,1].duplicated().any() for z in [bim,esi,epi]) or fam.duplicated([0,1]).any():raise ValueError('Actual unique native BIM/FAM/ESI/EPI schemas required')
    if len(fam)<p['minimum_ld_reference_units']:raise ValueError('LD reference lacks the prespecified actual independent-unit support')
    if ldfiles[0].stat().st_size!=3+len(bim)*((len(fam)+3)//4):raise ValueError('Actual PLINK genotype dimensions do not match the selected variant/sample dictionaries')
    g=pd.read_csv(inputs['gwas'],sep=r'\s+',dtype={'SNP':str,'A1':str,'A2':str},keep_default_na=False)
    cols=['SNP','A1','A2','freq','b','se','p','n']
    if not set(cols)<=set(g) or not len(g) or len(g)>p['maximum_variants'] or g.SNP.duplicated().any() or (g.SNP=='').any():raise ValueError('Actual bounded unique SMR GWAS summary required')
    num=g[cols[3:]].to_numpy(float)
    if not np.isfinite(num).all() or not g.A1.isin(list('ACGT')).all() or not g.A2.isin(list('ACGT')).all() or (g.A1==g.A2).any() or (g.se.astype(float)<=0).any() or (g.n.astype(float)<=0).any() or ((g.freq.astype(float)<0)|(g.freq.astype(float)>1)).any() or ((g.p.astype(float)<0)|(g.p.astype(float)>1)).any():raise ValueError('Finite effects, SE/N, probabilities and actual nucleotide alleles required')
    # Do not rewrite aliases, strand complements, allele signs or frequencies.
    # Native SMR harmonizes its native resources; first audit literal intersecting
    # variant/position/allele sets and retain incompatible/palindromic states.
    intersect=sorted(set(g.SNP)&set(bim.iloc[:,1])&set(esi.iloc[:,1]));ledger=[]
    bi=bim.set_index(1);ei=esi.set_index(1);gi=g.set_index('SNP')
    for sid in intersect:
        br=bi.loc[sid];er=ei.loc[sid];gr=gi.loc[sid];same_location=br[0]==er[0] and br[3]==er[3];alleles=[set([br[4],br[5]]),set([er[4],er[5]]),set([gr.A1,gr.A2])];same=alleles[0]==alleles[1]==alleles[2];pal=alleles[2] in ({'A','T'},{'C','G'})
        ledger.append({'SNP':sid,'same_literal_location':same_location,'same_literal_allele_set':same,'palindromic':pal,'state':'NATIVE_FREQUENCY_QC_REQUIRED' if same_location and same else 'HOLD_LITERAL_MISMATCH'})
    audit=pd.DataFrame(ledger);audit.to_csv(out/'smr_preflight_variants.tsv',sep='\t',index=False)
    if not len(audit) or audit.state.eq('HOLD_LITERAL_MISMATCH').any():raise ValueError('No usable literal overlap or incompatible variant location/alleles; resolve upstream, never silently recode')
    argv=[str(exe),'--bfile',str(ld),'--gwas-summary',str(inputs['gwas']),'--beqtl-summary',str(qtl),'--heidi-mtd',str(p['heidi_method']),'--maf',str(p['maf']),'--diff-freq',str(p['frequency_difference']),'--diff-freq-prop',str(p['maximum_frequency_exclusion_fraction']),'--peqtl-smr',str(p['instrument_pvalue']),'--peqtl-heidi',str(p['heidi_instrument_pvalue']),'--heidi-min-m',str(p['heidi_minimum_snps']),'--heidi-max-m',str(p['heidi_maximum_snps']),'--ld-upper-limit',str(p['ld_upper']),'--ld-lower-limit',str(p['ld_lower']),'--cis-wind',str(p['cis_window_kb']),'--thread-num',str(p['threads']),'--out',str(out/'smr')]
    write(out/'smr_command.private.json',{'argv':argv,'reference_manifest_sha256':sha(inputs['reference_manifest']),'automatic_retry':False,'automatic_allele_rewrite':False})
    with (out/'smr.stdout.log').open('xb') as so,(out/'smr.stderr.log').open('xb') as se:proc=subprocess.run(argv,stdout=so,stderr=se,check=False)
    if proc.returncode:raise RuntimeError('Native SMR failed; preserve mismatch/frequency QC logs and do not retry automatically')
    result=pd.read_csv(out/'smr.smr',sep=r'\s+',dtype={'ProbeID':str,'topSNP':str},na_values=['NA','nan','-9']);required=['ProbeID','topSNP','b_SMR','se_SMR','p_SMR','p_HEIDI','nsnp_HEIDI']
    if not set(required)<=set(result) or not len(result) or result.ProbeID.duplicated().any() or not set(result.ProbeID)<=set(epi.iloc[:,1]) or not set(result.topSNP)<=set(intersect):raise ValueError('Native SMR probe/instrument identity differs or no tested result; not negative biological evidence')
    for col in ['p_SMR','p_HEIDI']:
        x=result[col].dropna().to_numpy(float)
        if not np.isfinite(x).all() or ((x<0)|(x>1)).any():raise ValueError('Invalid native SMR/HEIDI probability')
    result['SMR_p_threshold']=p['smr_result_pvalue'];result['HEIDI_p_reference']=p['heidi_result_pvalue'];result['prespecified_screen_pass']=(result.p_SMR<p['smr_result_pvalue'])&(result.p_HEIDI>p['heidi_result_pvalue']);result['HEIDI_assessed']=result.p_HEIDI.notna();result.to_csv(out/'smr_heidi_review.tsv',sep='\t',index=False,na_rep='NA')
    write(out/'diagnostics.json',{'mode':mode,'software_versions':p['software_versions'],'n_probes':len(result),'n_unassessed_heidi':int(result.p_HEIDI.isna().sum()),'n_preflight_variants':len(audit),'heidi_method':p['heidi_method'],'scientific_acceptance':'NOT_ESTABLISHED','interpretation':'Actual native cis-SMR and HEIDI. HEIDI non-rejection is not proof of colocalization, exclusion restriction or causal mediation. Missing/under-supported HEIDI remains unassessed. Result thresholds are prespecified configurable screening criteria; multiplicity and independent evidence remain separate gates.'})
    outputs=[(out/'smr.smr','native_smr_results'),(out/'smr_heidi_review.tsv','genetic_evidence'),(out/'smr_preflight_variants.tsv','allele_qc'),(out/'smr_command.private.json','native_command'),(out/'diagnostics.json','diagnostics')]
    for fn in out.glob('smr*log'):
        if fn.stat().st_size:outputs.append((fn,'native_smr_log'))
    write(out/'versions.json',p['software_versions']);outputs.append((out/'versions.json','backend_versions'));return outputs
