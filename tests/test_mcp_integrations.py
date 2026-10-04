"""Bounded query, provenance, scheduler and mutation-plan acceptance/refusal checks."""
import importlib.util
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'bridge'))
import academic_common as common
import configure_mcp
import integration_ext as integ
import interface_ext as interface
import semantic_index_ext as semantic
import slurm_monitor as monitor
import table_query_ext as query
import prepare_docker_gateway


class IntegrationChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.p=patch.object(common,'HERE',self.root);self.p.start()
    def tearDown(self):self.p.stop();self.tmp.cleanup()
    def test_manifest_is_not_runtime(self):
        data=integ.inspect_mcp_components();self.assertEqual(len(data['components']),8);self.assertEqual(data['runtime_state'],'not_probed')
    def test_slurm_ids_deny_shell_and_foreign_step_scope(self):
        for job in ['12;touch x','--help','0','12.batch']:
            with self.assertRaises(ValueError):monitor.validate({'schema':1,'job_ids':[job],'submission_host':'compute-test'})
        raw='12|COMPLETED|0:0|9|1M|1|n|0:03|1G|owner\n12.batch|COMPLETED|0:0|9|1M|1|n|0:03|1G|owner\n13|RUNNING|0:0|1||1|n||1G|other\n'
        self.assertEqual(len(monitor.parse_accounting(raw,['12'],'owner')),2)
    def test_scheduler_actual_argv_has_owner_and_no_mutation(self):
        request={'schema':1,'job_ids':['12'],'submission_host':'compute-test'};calls=[]
        def run(argv):
            calls.append(argv);return '12|COMPLETED|0:0|9|1M|1|n|0:03|1G|owner\n' if argv[0]=='sacct' else ''
        with patch.object(monitor.socket,'gethostname',return_value='compute-test'),patch.object(monitor.getpass,'getuser',return_value='owner'),patch.object(monitor,'command',side_effect=run):receipt=monitor.monitor(request)
        self.assertTrue(receipt['jobs'][0]['scheduler_completed']);self.assertFalse(receipt['scientific_completion_verified'])
        self.assertEqual([a[0] for a in calls],['squeue','sacct']);self.assertTrue(all('--user' in a for a in calls))
    def test_unavailable_queue_never_means_completion(self):
        with patch.object(monitor.socket,'gethostname',return_value='compute-test'),patch.object(monitor,'command',side_effect=OSError):r=monitor.monitor({'schema':1,'job_ids':['12'],'submission_host':'compute-test'})
        self.assertEqual(r['state'],'partial_or_unavailable');self.assertFalse(r['jobs'][0]['scheduler_completed'])
    def test_log_traversal_rejected(self):
        with self.assertRaises(ValueError):monitor.validate({'schema':1,'job_ids':['12'],'submission_host':'compute-test','log_files':['../private'],'log_root':'/owned'})
    def test_receipt_bindings_and_staleness(self):
        req={'schema':1,'job_ids':['12'],'submission_host':'compute-test','log_root':'','log_files':[]};rp=self.root/'req.json';rp.write_text(json.dumps(req))
        receipt={'schema':1,'request_sha256':'wrong','observed_host':'compute-test','observed_at_unix':time.time()-1000,'jobs':[{'job_id':'13'}],'state':'observed'};cp=self.root/'receipt.json';cp.write_text(json.dumps(receipt))
        r=integ.inspect_slurm_monitor(str(rp),str(cp));self.assertFalse(r['receipt_consistent']);self.assertIn('stale_or_invalid_timestamp',r['issues']);self.assertIn('job_scope_mismatch',r['issues'])
    def test_semantic_index_requires_selected_authorization(self):
        records=[{'id':'paper-a','text':'Synthetic document','source_version':'1','source_location':'page:1'}]
        with self.assertRaises(ValueError):semantic.prepare_semantic_index(records,'selected',str(self.root/'index'))
        r=semantic.prepare_semantic_index(records,'selected',str(self.root/'index'),True)
        self.assertEqual(r['state'],'prepared');self.assertFalse((self.root/'index').exists())
    def test_semantic_mismatched_version_and_hash(self):
        r=semantic.audit_semantic_results([{'metadata':{'id':'a','text_sha256':'x','source_version':'2'}}],[{'id':'a','text':'test','source_version':'1'}]);self.assertFalse(r['all_source_bindings_consistent'])
    def test_cytoscape_stale_plan_and_unknown_retry_blocked(self):
        plan={'schema':1,'network_id':12,'layout':'grid','port':1234,'network_sha256':common.digest(b'{}'),'version_sha256':common.digest(b'{}')}
        raw=json.dumps(plan).encode();p=self.root/'plan.json';p.write_bytes(raw);sha=common.digest(raw)
        with patch.object(interface,'_get',return_value=b'changed'),self.assertRaises(ValueError):interface.apply_cytoscape_revision(str(p),sha)
        self.assertFalse(p.with_name('dispatch_receipt.json').exists())
        with patch.object(interface,'_get',side_effect=[b'{}',b'{}',TimeoutError]),self.assertRaises(TimeoutError):interface.apply_cytoscape_revision(str(p),sha)
        self.assertEqual(json.loads(p.with_name('dispatch_receipt.json').read_text())['state'],'dispatch_outcome_unknown')
        with patch.object(interface,'_get',return_value=b'{}'),self.assertRaises(FileExistsError):interface.apply_cytoscape_revision(str(p),sha)
    def test_profile_disables_dynamic_code_and_memory_tools(self):
        self.assertIn('fixed_tools:',configure_mcp.SERENA_CONTEXT);self.assertNotIn('execute_shell_command',configure_mcp.SERENA_CONTEXT);self.assertNotIn('write_memory',configure_mcp.SERENA_CONTEXT)
        self.assertIn('enable_external_access=false',configure_mcp.DUCKDB_INIT);self.assertIn('lock_configuration=true',configure_mcp.DUCKDB_INIT)
    def test_gateway_static_digest_without_host_mounts_or_secrets(self):
        r=prepare_docker_gateway.prepare(self.root/'gateway',self.root/'catalogs')
        e=r['mcpServers']['brw-docker-gateway'];self.assertIn('@sha256:',r['image']);self.assertIn('--static',e['args']);self.assertNotIn('--enable-all-servers',e['args'])
        p=Path(e['args'][e['args'].index('--catalog')+1]);catalog=json.loads(p.read_text());spec=catalog['registry']['fetch']
        self.assertEqual(spec['volumes'],[]);self.assertEqual(spec['secrets'],[]);self.assertEqual(r['runtime_acceptance'],'required')
if __name__=='__main__':unittest.main()
