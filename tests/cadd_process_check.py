"""Actual installed bridge calls on synthetic CADD summaries; no engines or network."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cadd import CONTEXT, H, J, CaddTests, afrecord, domain, energy, protocol


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--installation')
    args=parser.parse_args()
    host=Path(args.installation) if args.installation else Path(os.environ['RUNNER_TEMP'])/'BiomniCore'
    source_dir=Path(__file__).resolve().parents[1]/'bridge'
    for name,module in list(sys.modules.items()):
        filename=getattr(module,'__file__',None)
        if filename and Path(filename).resolve().is_relative_to(source_dir):del sys.modules[name]
    sys.path[:]=[p for p in sys.path if Path(p or '.').resolve()!=source_dir]
    sys.path.insert(0, str(host/'.local'))
    import bridge
    assert Path(bridge.__file__).resolve().parent==(host/'.local').resolve()
    from extensions import registry
    assert bridge.readiness()['bridge_version']=='2.13'
    assert len([k for k in registry() if k[0]=='cadd'])==8
    fixtures=CaddTests(); expected, results=fixtures.campaign(); mapping, restraints=fixtures.restraint()
    cases=[
        ('guide_cadd_workflow',dict(task='md',context=CONTEXT),True),
        ('audit_simulation_protocol',dict(protocol=protocol(),context=CONTEXT),True),
        ('audit_restart_manifest',dict(segments=fixtures.segments(),context=CONTEXT),True),
        ('audit_replica_exchange',dict(ladder=[300,350],exchanges=[{'state_a':0,'state_b':1,'attempted':10,'accepted':4}],visits=[{'step':0,'walker_states':[0,1]},{'step':100,'walker_states':[1,0]},{'step':200,'walker_states':[0,1]}],context=CONTEXT),True),
        ('audit_docking_campaign',dict(expected=expected,results=results,score_domain=domain(),context=CONTEXT),True),
        ('audit_restraint_mapping',dict(mapping=mapping,restraints=restraints,context=CONTEXT),True),
        ('audit_af3_records',dict(records=[afrecord()],selected_pair=['A','B'],context=CONTEXT),True),
        ('audit_mmgbsa_summary',dict(runs=[energy(),energy('two',-24,J)],context=CONTEXT),True),
        ('audit_docking_campaign',dict(expected=expected,results=[],score_domain=domain(),context=CONTEXT),False),
    ]
    for name, parameters, gate in cases:
        receipt=bridge.run_tool('cadd',name,parameters)
        assert receipt['success'], name
        raw=Path(receipt['result_file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==receipt['sha256']
        report=json.loads(raw)
        assert report['qc_gate_pass'] is gate
        assert report['scientific_validity']=='not_established'
        assert report['execution_state']=='summary_audit_only'
        manifest=Path(report['manifest_file'])
        for item in json.loads(manifest.read_text(encoding='utf8'))['files']:
            source=manifest.parent/item['name']
            assert source.stat().st_size==item['bytes']
            assert hashlib.sha256(source.read_bytes()).hexdigest()==item['sha256']
        assert any(p.suffix=='.html' for p in manifest.parent.iterdir())
    print('INSTALLED_CADD_CALLS_PASSED',len(cases),'engines_not_executed')


if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('CADD_INSTALLED_ACCEPTANCE_FAILED',type(exc).__name__)
        raise SystemExit(1)
