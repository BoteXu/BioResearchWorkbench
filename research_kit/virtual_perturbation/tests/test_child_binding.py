"""Child invocation metadata binding only. The real scientific guard is never bypassed in production."""
from pathlib import Path
import tempfile,unittest,sys,json,copy
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'server')]
import child_guard
from contracts import sha,catalog
class ChildBinding(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);context={'species':'FIXTURE_NOT_SCIENCE'};(self.root/'context.json').write_text(json.dumps(context),encoding='utf8');spec=catalog()['methods']['cpa']
        self.request={'method':'cpa','parameters':{'seed':1},'sensitivity_variants':[],'resource_budget':{'cpus':1,'gpus':0},'inputs':[{'id':'context','path':'context.json','sha256':sha(self.root/'context.json')}]};(self.root/'request.json').write_text(json.dumps(self.request),encoding='utf8')
        self.job={'request_path':str(self.root/'request.json'),'method':'cpa','parameters':{'seed':1,'implementation':spec['implementation']},'variant':'primary','resource_budget':self.request['resource_budget'].copy(),'required_roles':spec['roles'][:],'implementation':spec['implementation'],'project_root':str(self.root),'python_executable':sys.executable,'inputs':{'context':str((self.root/'context.json').resolve())},'context':context.copy()}
    def tearDown(self):self.temp.cleanup()
    def check(self):
        with patch.object(child_guard,'guard',return_value='FIXTURE_BINDING_TEST_ONLY'):return child_guard.verify(self.job)
    def test_matching_metadata_binds(self):self.check()
    def test_child_context_is_bound_to_actual_input(self):
        self.job['context']['species']='CHANGED'
        with self.assertRaises(ValueError):self.check()
    def test_child_resource_type_cannot_alias_boolean(self):
        self.job['resource_budget']['cpus']=True
        with self.assertRaises(ValueError):self.check()
    def test_child_parameters_type_cannot_alias_boolean(self):
        self.job['parameters']['seed']=True
        with self.assertRaises(ValueError):self.check()
    def test_unregistered_child_input_refused(self):
        self.job['inputs']['UNREVIEWED']='other'
        with self.assertRaises(ValueError):self.check()
    def test_child_output_roles_cannot_be_relabelled(self):
        self.job['required_roles']=['observed_KO']
        with self.assertRaises(ValueError):self.check()
    def test_child_interpreter_cannot_be_redirected(self):
        self.job['python_executable']=str(self.root/'unowned_python')
        with self.assertRaises(ValueError):self.check()
    def test_child_implementation_cannot_be_relabelled(self):
        self.job['implementation']='WRONG_NATIVE_METHOD'
        with self.assertRaises(ValueError):self.check()
