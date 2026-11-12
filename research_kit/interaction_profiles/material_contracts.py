"""Private source/chemistry review contracts. Reads selected files; imports no chemistry engine."""
import math,re
from contracts import selected,read,sha
def context(ctx):
    for k in ('protonation_reviewed','stereochemistry_reviewed','structure_source_reviewed'):
        if ctx.get(k) is not True:raise ValueError('Explicit source-bound molecular review required: '+k)
    if ctx.get('public_upload') is not False or ctx.get('coordinates_unit')!='angstrom' or not isinstance(ctx.get('frame_id'),str) or not ctx['frame_id'].strip() or not ctx.get('limitations'):raise ValueError('Private scientific frame, units and interpretation limits required')
    if not re.fullmatch('[a-f0-9]{64}',str(ctx.get('preparation_domain_sha256',''))):raise ValueError('Exact reviewed preparation-domain hash required')
    if type(ctx.get('pH')) not in (int,float) or not math.isfinite(ctx['pH']):raise ValueError('Finite reviewed protonation pH required')
    if ctx.get('frame_kind') not in ('ligand_reference','docking_complex'):raise ValueError('Declare the actual ligand-reference or docking-complex frame')
    if ctx['frame_kind']=='docking_complex' and any(not re.fullmatch('[a-f0-9]{64}',str(ctx.get(k,''))) for k in ('receptor_sha256','site_sha256')):raise ValueError('Docking-complex frame needs exact receptor and site provenance')
def material(row,ctx):
    if not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,60}',str(row.get('id',''))) or row.get('role') not in ('reference','candidate','negative_control'):raise ValueError('Safe molecular identity and explicit role required')
    if type(row.get('formal_charge')) is not int or any(not isinstance(row.get(k),str) or not row[k].strip() for k in ('parent_id','microstate_id')):raise ValueError('Explicit integer charge and string parent/state identities required')
    if row.get('preparation_domain_sha256')!=ctx['preparation_domain_sha256'] or row.get('frame_id')!=ctx['frame_id']:raise ValueError('Selected structures use a different chemical preparation or frame')
def numerical_QC(row,root,sdf):
    measurement=selected(root,row['qc_measurements']['path']);receipt=selected(root,row['qc_receipt']['path']);up=read(receipt)
    if sha(measurement)!=row['qc_measurements']['sha256'] or sha(receipt)!=row['qc_receipt']['sha256'] or up.get('state')!='COMPLETED' or type(up.get('exit_code')) is not int or up['exit_code']!=0 or not any(x.get('sha256')==sha(measurement) for x in up.get('outputs',[])) or not any(x.get('sha256')==sha(sdf) for x in up.get('inputs',[])):raise ValueError('Molecular QC is not bound to actual completed input measurements')
    observations=read(measurement);audit=[]
    if not row.get('qc_rules'):raise ValueError('Prespecified substantive input QC required for every molecule')
    for g in row['qc_rules']:
        if any(not g.get(k) for k in ('field','definition','unit','threshold_basis')):raise ValueError('QC field, definition, unit and scientific threshold basis required')
        value=observations
        for part in g['field'].split('.'):value=value[int(part)] if isinstance(value,list) else value[part]
        bound=g['bound'];observed=g['observed'];op=g['operator']
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (value,bound,observed)) or value!=observed or op not in ('ge','le','eq') or not {'ge':value>=bound,'le':value<=bound,'eq':value==bound}[op]:raise ValueError('Actual molecular QC fails its reviewed numerical criterion')
        audit.append({**g,'measurement_sha256':sha(measurement),'source_receipt_sha256':sha(receipt),'input_sdf_sha256':sha(sdf)})
    return measurement,receipt,audit
def checkpoint(assets,root):
    if assets.get('trust_decision')!='REVIEWED_TRUSTED_CHECKPOINT' or not assets.get('origin') or not assets.get('license_review') or assets.get('public_upload') is not False:raise ValueError('Native checkpoint deserialization requires explicitly reviewed trusted weights and license')
    weight=selected(root,assets['path']);license_file=selected(root,assets['license_document']['path'])
    if sha(weight)!=assets['sha256'] or sha(license_file)!=assets['license_document']['sha256']:raise ValueError('Checkpoint or exact license document changed')
    return weight,license_file
