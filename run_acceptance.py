"""Run fixed engineering checks and optional small public identity probes."""
import argparse
import hashlib
import io
import json
import re
import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path


def finalize_report(report, allow_unavailable_public_services=False):
    """Keep strict acceptance separate from an explicitly scoped CI installation gate."""
    offline=report['offline']
    engineering=not any(offline[k] for k in ['failures','errors','skipped'])
    for row in report['network']:
        unavailable=(row.get('invocation_success') is False and row.get('receipt_integrity_verified') is True and
                     (row.get('http_status') in {429,500,502,503,504} or row.get('error_type') in {'ConnectTimeout','ReadTimeout','Timeout'}))
        row['availability_state']='passed' if row['pass'] else 'external_unavailable' if unavailable else 'check_failed'
    network=all(r['pass'] for r in report['network'])
    outages=[r['case'] for r in report['network'] if r['availability_state']=='external_unavailable']
    hard_failures=[r['case'] for r in report['network'] if r['availability_state']=='check_failed']
    strict=engineering and network
    return {**report,'engineering_pass':engineering,'network_pass':network if report['network_state']!='not_requested' else None,
            'public_service_outages':outages,'network_check_failures':hard_failures,'pass':strict,
            'ci_gate_pass':strict or bool(engineering and allow_unavailable_public_services and outages and not hard_failures),
            'ci_gate_policy':'known_public_service_outages_reported_separately' if allow_unavailable_public_services else 'strict_all_requested_checks'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--network',action='store_true')
    parser.add_argument('--allow-unavailable-public-services',action='store_true',help='Explicit CI-only installation gate; strict pass and failed network states remain false')
    parser.add_argument('--output-file',help='Private JSON report; do not publish runtime reports')
    args = parser.parse_args()
    if args.allow_unavailable_public_services and not args.network:parser.error('The separate service gate requires --network')
    root = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(str(root/'tests'))
    with redirect_stdout(io.StringIO()):
        result = unittest.TextTestRunner(stream=io.StringIO(),verbosity=0).run(suite)
    report = {'suite_version':'2','created_at':datetime.now(timezone.utc).isoformat(),
              'offline':{'run':result.testsRun,'failures':[t.id() for t,_ in result.failures],
                         'errors':[t.id() for t,_ in result.errors],'skipped':[t.id() for t,_ in result.skipped]},
              'network':[], 'network_state':'not_requested',
              'limitations':['Engineering regression tests do not measure general biomedical reasoning quality.',
                             'Fixtures test expected refusal as well as acceptance; live queries check only fixed public identities.',
                             'Optional-profile and client GUI integration are outside this suite.']}
    if args.network:
        sys.path.insert(0,str(root/'bridge'))
        import bridge
        cases = [
            ('human_insulin_gene',{'namespace':'gene_symbol','identifier':'INS','species':'homo_sapiens','assembly':'GRCh38'},'ENSG00000254647'),
            ('human_insulin_protein',{'namespace':'uniprot','identifier':'P01308','species':'homo_sapiens'},'ENSG00000254647'),
            ('variant_build',{'namespace':'rsid','identifier':'rs699','species':'homo_sapiens','assembly':'GRCh38'},None),
            ('pdb_identity',{'namespace':'pdb','identifier':'4HHB'},'4HHB'),
            ('compound_identity',{'namespace':'pubchem_cid','identifier':'2244'},'BSYNRYMUTXBXSQ-UHFFFAOYSA-N'),
            ('chembl_identity',{'namespace':'chembl','identifier':'CHEMBL25'},'BSYNRYMUTXBXSQ-UHFFFAOYSA-N'),
        ]
        for name, parameters, expected in cases:
            try:
                receipt = bridge.run_tool('research','resolve_identifier',parameters)
                raw = Path(receipt['result_file']).read_bytes()
                data = json.loads(raw)
                # Fixed public probes expose only the status, never response text or local paths.
                status_match = re.search(r'\bHTTP ([45][0-9]{2}):', str(data.get('error', '')))
                check = bool(receipt['success'] and data['identity_check_pass'] and
                             (expected is None or any(c['identifier'].split('.')[0] == expected for c in data['candidates'])) and
                             hashlib.sha256(raw).hexdigest() == receipt['sha256'])
                report['network'].append({'case':name,'pass':check,'receipt_file':receipt['receipt_file'],
                                          'invocation_success':bool(receipt['success']),
                                          'receipt_integrity_verified':hashlib.sha256(raw).hexdigest()==receipt['sha256'],
                                          'resolution_status':data.get('status'),
                                          'candidate_coverage_complete':data.get('candidate_coverage_complete'),
                                          'http_status':int(status_match.group(1)) if status_match else None,
                                          'error_type':data.get('error_type') or (str(data.get('error','')).split(':',1)[0] if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',str(data.get('error','')).split(':',1)[0]) else None)})
            except Exception as exc:
                report['network'].append({'case':name,'pass':False,'error_type':type(exc).__name__})
        report['network_state'] = 'completed'
        try:
            receipt = bridge.run_tool('biomedical','map_disease_terms',{'terms':['heart failure'],'ontology':'mondo'})
            raw = Path(receipt['result_file']).read_bytes()
            data = json.loads(raw)
            candidates = data['terms'][0]['candidates'] if receipt['success'] else []
            check = bool(receipt['success'] and candidates and any(str(c.get('id','')).startswith('MONDO:') for c in candidates)
                         and not data['terms'][0]['automatic_merge_allowed'] and hashlib.sha256(raw).hexdigest()==receipt['sha256'])
            report['network'].append({'case':'ontology_candidates','pass':check,'receipt_file':receipt['receipt_file']})
        except Exception as exc:
            report['network'].append({'case':'ontology_candidates','pass':False,'error_type':type(exc).__name__})
    report=finalize_report(report,args.allow_unavailable_public_services)
    if args.output_file:
        path = Path(args.output_file)
        if path.exists():
            raise ValueError('Choose a fresh report path')
        path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,indent=2))
    return 0 if report['ci_gate_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
