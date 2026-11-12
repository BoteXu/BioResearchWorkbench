"""FigureHandoff v1: bounded frozen-file provenance, without a plotting or analysis dependency.

This original module is shared byte-for-byte by BioResearchWorkbench and the
Scientific Figure Workbench. It is a handoff format, not RO-Crate compliance.
"""
import copy
import csv
import hashlib
import json
from pathlib import Path
import re

CONTEXT_FIELDS = {'independent_unit', 'contrast', 'method_version', 'reference_version',
                  'units', 'selected_scope', 'limitations'}
FIELDS = {'schema_version', 'contract', 'figure_spec', 'context', 'qc', 'execution',
          'sources', 'table', 'analysis_performed', 'scientific_validity_established', 'binding_sha256'}
HEX = re.compile(r'[0-9a-f]{64}')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf8')


def hash_value(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''): result.update(block)
    return result.hexdigest()


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value)<=2000


def _selected(path):
    if not isinstance(path, (str, Path)) or re.match(r'^[a-zA-Z][\w+.-]*://', str(path)):
        raise ValueError('Select an explicit local result file')
    value = Path(path)
    if value.is_symlink() or not value.is_file(): raise ValueError('Selected result is missing or linked')
    return value.resolve()


def table_info(path):
    path = _selected(path)
    if path.stat().st_size>5*1024**2: raise ValueError('Selected display table exceeds 5 MiB')
    before = digest(path); count = 0
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream, delimiter='\t'); header = next(reader, [])
        if not header or len(header)>250 or len(set(header))!=len(header) or any(not c.strip() for c in header):
            raise ValueError('A frozen TSV with unique nonempty columns is required')
        for row in reader:
            count += 1
            if len(row)!=len(header) or count>20000: raise ValueError('Ragged or overlong display table')
    if not count or digest(path)!=before: raise ValueError('Empty or changing display table')
    return {'sha256':before, 'rows':count, 'columns':header}


def validate_handoff(value, base):
    """Validate bytes and consistency. Caller declarations never become scientific acceptance."""
    if len(canonical(value))>2*1024**2: raise ValueError('Narrow handoff metadata to 2 MiB')
    if not isinstance(value, dict) or set(value)!=FIELDS or value['schema_version']!=1 or value['contract']!='figure-handoff':
        raise ValueError('Unsupported FigureHandoff fields or version')
    if value['analysis_performed'] is not False or value['scientific_validity_established'] is not False:
        raise ValueError('Handoff cannot assert analysis execution or scientific validity')
    payload = {k:v for k,v in value.items() if k!='binding_sha256'}
    if value['binding_sha256']!=hash_value(payload): raise ValueError('Handoff metadata binding changed')
    context = value['context']
    if not isinstance(context, dict) or set(context)!=CONTEXT_FIELDS or any(not _text(context[k]) for k in CONTEXT_FIELDS):
        raise ValueError('Complete explicit unit, contrast, methods, references, scope and limitations are required')
    table = value['table']; spec = value['figure_spec']
    if not isinstance(table, dict) or set(table)!={'path','sha256','rows','columns'} or not _text(table['path']):
        raise ValueError('An exact selected table is required')
    path = Path(table['path'])
    path = path if path.is_absolute() else Path(base)/path
    actual = table_info(path)
    if any(table[k]!=actual[k] for k in actual): raise ValueError('Frozen table bytes or shape changed')
    if (not isinstance(spec, dict) or spec.get('schema_version')!=1 or not isinstance(spec.get('input'), dict)
            or spec['input'].get('path')!=table['path'] or spec['input'].get('sha256')!=actual['sha256']):
        raise ValueError('FigureSpec and table binding disagree')
    meta = spec.get('provenance', {})
    if (meta.get('experimental_unit')!=context['independent_unit'] or meta.get('contrast')!=context['contrast']
            or type(meta.get('synthetic')) is not bool):
        raise ValueError('Figure provenance must preserve the independent unit, contrast and synthetic declaration')
    qc = value['qc']
    if (not isinstance(qc, dict) or set(qc)!={'state','input_sha256','context_sha256','review_reference'}
            or qc['state']!='passed' or qc['input_sha256']!=actual['sha256']
            or qc['context_sha256']!=hash_value(context) or not _text(qc['review_reference'])):
        raise ValueError('QC must pass for the exact input and context; a historical pass is insufficient')
    execution = value['execution']
    if not isinstance(execution, dict) or not _text(execution.get('source_reference')):
        raise ValueError('Document the actual frozen-result origin')
    if execution.get('state')=='frozen_results_supplied':
        if set(execution)!={'state','source_reference'}: raise ValueError('Supplied frozen results cannot imply a completed job')
    elif execution.get('state')=='completed':
        if (set(execution)!={'state','source_reference','receipt_sha256','receipt'}
                or not HEX.fullmatch(str(execution['receipt_sha256']))
                or execution['receipt_sha256']!=hash_value(execution['receipt'])):
            raise ValueError('A completed execution needs its exact embedded receipt binding')
        receipt = execution['receipt']
        if (not isinstance(receipt, dict) or receipt.get('state')!='completed'
                or type(receipt.get('exit_code')) is not int or receipt['exit_code']!=0
                or receipt.get('input_sha256')!=actual['sha256'] or receipt.get('context_sha256')!=hash_value(context)):
            raise ValueError('Submission, unknown state or a mismatched receipt is not completion')
    else: raise ValueError('Use supplied frozen results or a documented completed execution')
    sources = value['sources']
    if not isinstance(sources, list) or not 1<=len(sources)<=50: raise ValueError('Select one to 50 located source records')
    ids = set()
    for source in sources:
        if (not isinstance(source, dict) or set(source)-{'id','reference','version','locator','sha256'}
                or any(not _text(source.get(k)) for k in ['id','reference','version','locator'])
                or source['id'] in ids or ('sha256' in source and not HEX.fullmatch(str(source['sha256'])))):
            raise ValueError('Sources need unique IDs, references, versions and locations; hashes must be exact')
        ids.add(source['id'])
    return {'state':'FROZEN_HANDOFF_CHECKED', 'input_sha256':actual['sha256'], 'rows':actual['rows'],
            'context_sha256':hash_value(context), 'binding_sha256':value['binding_sha256'],
            'analysis_performed':False, 'scientific_validity_established':False,
            'caller_assertions_independently_verified':False, 'renderer_contract_verified':False}


def prepare_handoff(input_path, figure_spec, context, qc, execution, sources, output_dir=''):
    path = _selected(input_path); table = table_info(path)
    spec = copy.deepcopy(figure_spec)
    if not isinstance(spec, dict) or not isinstance(spec.get('input'), dict) or spec['input'].get('sha256')!=table['sha256']:
        raise ValueError('Provide an exact FigureSpec with the selected input SHA256')
    relative = 'frozen.tsv' if output_dir else str(path)
    spec['input']['path'] = relative
    value = {'schema_version':1, 'contract':'figure-handoff', 'figure_spec':spec, 'context':context,
             'qc':qc, 'execution':execution, 'sources':sources, 'table':{'path':relative, **table},
             'analysis_performed':False, 'scientific_validity_established':False}
    value['binding_sha256'] = hash_value(value)
    # Validate against the selected original file before any output is created.
    local = copy.deepcopy(value); local['table']['path'] = str(path); local['figure_spec']['input']['path'] = str(path)
    local['binding_sha256'] = hash_value({k:v for k,v in local.items() if k!='binding_sha256'})
    check = validate_handoff(local, path.parent)
    if output_dir:
        destination = Path(output_dir)
        if destination.exists(): raise ValueError('Choose a fresh handoff directory; existing results are preserved')
        destination.mkdir(parents=True, exist_ok=False)
        # Copy exactly the checked display bytes, never a directory or a private environment.
        with path.open('rb') as incoming, (destination/'frozen.tsv').open('xb') as outgoing:
            for block in iter(lambda: incoming.read(65536), b''): outgoing.write(block)
        validate_handoff(value, destination)
        with (destination/'figure-handoff.json').open('x', encoding='utf8') as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    return {'handoff':value, 'check':{**check, 'binding_sha256':value['binding_sha256']},
            'portable_bundle_written':bool(output_dir), 'renderer_validation_required':True,
            'limitations':['Receipt integrity and declared QC do not establish scientific validity or scheduler authenticity.',
                           'No engine ran, no values were refitted, and no scientific method was validated by this handoff.']}
