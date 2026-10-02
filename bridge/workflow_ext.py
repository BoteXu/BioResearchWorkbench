"""Local orchestration and result checks, without moving server computation locally."""
import hashlib
import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path, PurePosixPath
import numpy as np
import pandas as pd
from evidence import atomic_json

HERE = Path(__file__).resolve().parent


def _hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _folder(name):
    p = HERE / 'outputs' / (name + '_' + uuid.uuid4().hex)
    p.mkdir(parents=True)
    return p


def _relative(path):
    if not isinstance(path, str) or not path or '\\' in path or PurePosixPath(path).is_absolute() or any(x in {'.', '..'} for x in path.split('/')) or any(ord(c) < 32 for c in path):
        raise ValueError('Use a nonempty relative POSIX path without traversal')
    return path


def _table(path, max_bytes=100000000):
    p = Path(path).resolve(strict=True)
    if p.stat().st_size > max_bytes:
        raise ValueError('Result exceeds 100 MB; export a smaller server summary')
    return pd.read_csv(p, sep='\t' if p.suffix.lower() == '.tsv' else ',', dtype=str, keep_default_na=False)


def inspect_ssh_route(alias: str = 'server') -> dict:
    """Read effective local SSH configuration without connecting or collecting credentials."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', alias):
        raise ValueError('Use a configured SSH alias')
    p = subprocess.run(['ssh', '-G', alias], capture_output=True, text=True, timeout=15, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if p.returncode:
        raise RuntimeError('SSH configuration inspection failed')
    fields = dict(line.split(' ', 1) for line in p.stdout.splitlines() if ' ' in line)
    return {'alias': alias, 'host': fields.get('hostname'), 'user': fields.get('user'), 'port': fields.get('port'), 'authenticated': False, 'limitations': ['Local SSH configuration only; this does not verify login or the current compute worker.', 'Use the existing shared visible terminal for authentication and command dispatch.']}


def prepare_remote_task(argv: list, remote_workdir: str, expected_host: str, expected_outputs: list, context: dict, inputs: list = None) -> dict:
    """Prepare a portable server task bundle, with exact argv, hostname gate and output checksums; no submission."""
    if not argv or any(not isinstance(x, str) or not x or '\x00' in x for x in argv):
        raise ValueError('argv must contain nonempty command argument strings')
    if not PurePosixPath(remote_workdir).is_absolute() or '..' in PurePosixPath(remote_workdir).parts or any(ord(c) < 32 for c in remote_workdir):
        raise ValueError('Specify the current absolute server working directory')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,252}', expected_host):
        raise ValueError('Provide a verified current server hostname')
    if not expected_outputs or len(set(expected_outputs)) != len(expected_outputs):
        raise ValueError('Specify distinct expected output paths')
    for path in expected_outputs:
        _relative(path)
    required = {'species', 'model', 'assay', 'biological_unit', 'contrast', 'limitations'}
    if not isinstance(context, dict) or not required.issubset(context) or any(not context[k] for k in required):
        raise ValueError('Provide species/model/assay/biological_unit/contrast/limitations')
    for item in inputs or []:
        _relative(item['path'])
        if not re.fullmatch(r'[a-fA-F0-9]{64}', item['sha256']):
            raise ValueError('Input SHA256 must have 64 hexadecimal characters')
    folder = _folder('remote_task')
    task = {'schema': 1, 'task_id': folder.name, 'argv': argv, 'remote_workdir': remote_workdir, 'expected_host': expected_host, 'expected_outputs': expected_outputs, 'inputs': inputs or [], 'context': context}
    atomic_json(folder / 'task.json', task)
    shutil.copyfile(HERE / 'remote_runner.py', folder / 'remote_runner.py')
    # The bundle must be copied to the server before this command is executed there.
    (folder / 'run.sh').write_text('#!/bin/sh\nset -eu\ncd -- "$(dirname -- "$0")"\nexec python3 remote_runner.py task.json\n', encoding='utf8', newline='\n')
    return {'state': 'prepared_not_submitted', 'bundle': str(folder), 'task_file': str(folder / 'task.json'), 'request_sha256': _hash(folder / 'task.json'), 'server_command': 'sh run.sh', 'limitations': ['Copy this bundle to the explicitly verified server and run through the shared terminal or its scheduler.', 'Large computation runs entirely on the server.', 'A successful process and checksums do not establish scientific validity.']}


def verify_remote_results(task_file: str, remote_receipt_path: str, downloaded_root: str) -> dict:
    """Check a downloaded remote receipt and expected output bytes/SHA256 against the exact task."""
    task = json.loads(Path(task_file).read_text(encoding='utf8'))
    receipt = json.loads(Path(remote_receipt_path).read_text(encoding='utf8'))
    root = Path(downloaded_root).resolve(strict=True)
    issues = []
    if receipt.get('task_id') != task['task_id'] or receipt.get('request_sha256') != _hash(task_file):
        issues.append('Task identity or request hash mismatch')
    if receipt.get('host') != task['expected_host']:
        issues.append('Server hostname mismatch')
    if receipt.get('state') != 'succeeded' or receipt.get('exit_code') != 0 or not receipt.get('finished_at_unix'):
        issues.append('Remote task has not successfully completed')
    records = receipt.get('outputs', [])
    names = [x.get('path') for x in records]
    if len(names) != len(set(names)) or set(names) != set(task['expected_outputs']):
        issues.append('Expected output manifest mismatch')
    verified = []
    for item in records:
        name = _relative(item['path'])
        p = (root / name).resolve()
        p.relative_to(root)
        ok = p.is_file() and item.get('exists') is True and p.stat().st_size == item.get('bytes') and p.stat().st_size > 0 and _hash(p) == item.get('sha256')
        verified.append({'path': name, 'verified': ok})
        if not ok:
            issues.append('Missing, empty, altered or incomplete file: ' + name)
    return {'integrity_pass': not issues, 'issues': issues, 'files': verified, 'context': task['context'], 'limitations': ['Receipt contents are not cryptographically signed server identity attestations.', 'This validates transfer integrity and recorded execution; substantive scientific review remains required.']}


def prepare_server_inventory(remote_workdir: str, expected_host: str) -> dict:
    """Prepare a read-only server software inventory task; does not connect, submit or install."""
    return prepare_remote_task(['python3', '-c', (HERE / 'server_probe.py').read_text(encoding='utf8')], remote_workdir, expected_host, ['remote_environment.json'], {'species': 'not applicable', 'model': 'software environment', 'assay': 'read-only inventory', 'biological_unit': 'not applicable', 'contrast': 'not applicable', 'limitations': ['Current environment only; no scientific analysis or package installation.']})


def inspect_remote_task(task_file: str, remote_receipt_path: str) -> dict:
    """Read a returned remote lifecycle receipt and check task identity; does not poll a server."""
    task = json.loads(Path(task_file).read_text(encoding='utf8'))
    receipt = json.loads(Path(remote_receipt_path).read_text(encoding='utf8'))
    issues = []
    if receipt.get('task_id') != task['task_id'] or receipt.get('request_sha256') != _hash(task_file) or receipt.get('host') != task['expected_host']:
        issues.append('Task request or host mismatch')
    state = receipt.get('state')
    if state not in {'running', 'succeeded', 'failed'}:
        issues.append('Unknown lifecycle state')
    if state in {'succeeded', 'failed'} and not receipt.get('finished_at_unix'):
        issues.append('Final state lacks completion time')
    if state == 'succeeded' and receipt.get('exit_code') != 0:
        issues.append('Success state disagrees with exit code')
    return {'receipt_consistent': not issues, 'state': state, 'issues': issues, 'recorded_host': receipt.get('host'), 'pid': receipt.get('child_pid'), 'exit_code': receipt.get('exit_code'), 'remote_error': receipt.get('error'), 'limitations': ['This is the returned receipt snapshot, not a live server process check.', 'For interrupted sessions inspect the current server process and logs before restarting; do not infer failure solely from an old running receipt.']}


def audit_sample_metadata(path: str, sample_key: str, unit_key: str, condition_key: str, case: str, control: str, paired: bool = False, min_units_per_group: int = 3) -> dict:
    """Check sample IDs and independent-unit counts; detect repeated units and incomplete pairing."""
    frame = _table(path)
    columns = [sample_key, unit_key, condition_key]
    if not set(columns).issubset(frame.columns) or case == control or min_units_per_group < 2:
        raise ValueError('Provide valid metadata columns, distinct groups, and minimum independent units >=2')
    data = frame[frame[condition_key].isin([case, control])]
    issues = []
    if (data[columns] == '').any().any() or data[sample_key].duplicated().any():
        issues.append('Empty identifiers or duplicate sample IDs')
    counts = {group: int(data.loc[data[condition_key] == group, unit_key].nunique()) for group in (case, control)}
    if any(n < min_units_per_group for n in counts.values()):
        issues.append('Insufficient independent units for the specified gate')
    if data.duplicated([unit_key, condition_key]).any():
        issues.append('Repeated observations per biological unit/condition require aggregation or an explicit repeated-measures model')
    case_units = set(data.loc[data[condition_key] == case, unit_key])
    control_units = set(data.loc[data[condition_key] == control, unit_key])
    if paired and case_units != control_units:
        issues.append('Incomplete or mismatched pairs')
    if not paired and case_units & control_units:
        issues.append('Shared biological units across groups require a paired/repeated-measures design')
    return {'input_gate_pass': not issues, 'issues': issues, 'independent_units': counts, 'selected_rows': len(data), 'excluded_other_conditions': len(frame) - len(data), 'paired': paired, 'limitations': ['Declared unit IDs must be checked against source metadata.', 'This does not validate confounder adjustment, count scale or the fitted model.']}


def audit_result_table(path: str, analysis: str, columns: dict, context: dict) -> dict:
    """Validate small server result tables for differential/MR/coloc/meta/image analysis; no local fitting."""
    requirements = {'differential': ['feature', 'effect', 'p', 'q'], 'mr': ['feature', 'effect', 'se', 'p'], 'coloc': ['feature', 'pp_h4'], 'meta': ['feature', 'effect', 'se', 'p', 'studies', 'i2'], 'image': ['feature', 'measurement']}
    if analysis not in requirements or not set(requirements[analysis]).issubset(columns):
        raise ValueError('Provide a supported analysis and its column mapping')
    frame = _table(path)
    if not set(columns.values()).issubset(frame.columns):
        raise ValueError('Mapped columns missing from result table')
    issues, warnings = [], []
    if frame.empty:
        issues.append('Empty results')
    ids = frame[columns['feature']]
    if (ids == '').any() or ids.duplicated().any():
        issues.append('Missing or duplicate result identifiers; use an explicit composite feature ID for strata')
    for role in requirements[analysis]:
        if role == 'feature':
            continue
        raw = frame[columns[role]]
        missing = raw.isin(['', 'NA', 'NaN', 'nan'])
        value = pd.to_numeric(raw, errors='coerce')
        invalid = ~missing & ~np.isfinite(value)
        if invalid.any():
            issues.append(f'Non-numeric or nonfinite {role}: {int(invalid.sum())} rows')
        if missing.any():
            warnings.append(f'Missing {role}: {int(missing.sum())} rows; retain filtered/failed results in the audit')
        bounds = (0, 1) if role in {'p', 'q', 'pp_h4'} else (0, 100) if role == 'i2' else None
        if bounds and ((value < bounds[0]) | (value > bounds[1])).any():
            issues.append(f'{role} outside valid bounds')
        if role == 'se' and (value <= 0).any():
            issues.append('Nonpositive standard error')
        if role == 'studies' and ((value < 2) | (value % 1 != 0)).any():
            issues.append('Meta-analysis requires integer study count >=2')
    for name in ('species', 'model', 'assay', 'biological_unit', 'contrast', 'limitations'):
        if not context.get(name) or str(context[name]).lower() == 'unknown':
            warnings.append('Unresolved interpretation context: ' + name)
    gates = {'differential': ['matrix_scale', 'replicate_design', 'multiple_testing'], 'mr': ['genome_build', 'allele_harmonization', 'ld_reference', 'sample_overlap', 'instrument_strength'], 'coloc': ['genome_build', 'dense_region_coverage', 'causal_variant_assumption', 'prior_sensitivity'], 'meta': ['effect_scale', 'contrast_alignment', 'cohort_overlap', 'heterogeneity_sensitivity'], 'image': ['pixel_spacing', 'segmentation_validation', 'independent_patient_or_sample']}
    for gate in gates[analysis]:
        if not context.get(gate) or str(context[gate]).lower() == 'unknown':
            warnings.append('Scientific gate not documented: ' + gate)
    return {'table_format_pass': not issues, 'review_context_complete': not issues and not warnings, 'scientific_validity': 'not_established', 'issues': issues, 'warnings': warnings, 'rows': len(frame), 'analysis': analysis, 'context': context, 'limitations': ['Column validity and self-reported context do not verify a model or scientific conclusion.', 'No local differential analysis, MR, coloc, meta-analysis or image computation was run.']}


def build_server_download_manifest(ena_result_path: str) -> dict:
    """Convert saved ENA runs into a server download manifest; no local FASTQ download."""
    result = json.loads(Path(ena_result_path).read_text(encoding='utf8'))
    files = []
    seen = set()
    for run in result['runs']:
        urls, md5s, sizes = [str(run.get(k, '')).split(';') for k in ('fastq_ftp', 'fastq_md5', 'fastq_bytes')]
        if not urls[0]:
            continue
        if len(urls) != len(md5s) or len(urls) != len(sizes):
            raise ValueError('ENA file URLs/checksums/sizes are not aligned')
        for url, md5, size in zip(urls, md5s, sizes):
            url = 'https://' + url if '://' not in url else url
            if not url.startswith('https://ftp.sra.ebi.ac.uk/') or not re.fullmatch(r'[a-fA-F0-9]{32}', md5) or int(size) <= 0:
                raise ValueError('Unexpected ENA FASTQ host, checksum or size')
            name = url.rsplit('/', 1)[-1]
            _relative(name)
            if name in seen:
                raise ValueError('Duplicate destination filename')
            seen.add(name)
            files.append({'run': run['run_accession'], 'sample': run.get('sample_accession'), 'url': url, 'filename': name, 'md5': md5, 'bytes': int(size)})
    folder = _folder('server_download_manifest')
    manifest = {'source_result': str(Path(ena_result_path).resolve()), 'source_result_sha256': _hash(ena_result_path), 'files': files, 'total_bytes': sum(x['bytes'] for x in files), 'possibly_truncated': result.get('possibly_truncated', True)}
    atomic_json(folder / 'manifest.json', manifest)
    return {'state': 'prepared_not_downloaded', 'manifest_path': str(folder / 'manifest.json'), **manifest, 'limitations': ['Check active remote writers before resuming downloads.', 'Use server-side resumable transfer and verify expected bytes and MD5.', 'Do not treat technical sequencing runs as independent biological replicates.']}
