"""Stdlib/AST and fake-subprocess checks only. No local scientific execution."""
from pathlib import Path
import ast,csv,hashlib,json,os,struct,subprocess,sys,tempfile,types,unittest,warnings,zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from contracts import sha
from server.native_evaluation import _archive,_capture_pipeline,_json_safe,_origin_attempts,_priority,_owned_native_work,run_native_evaluation
from server.xtb_audit import XtbAudit

class FakeBackend:
    DEVNULL=subprocess.DEVNULL;STDOUT=subprocess.STDOUT
    CalledProcessError=subprocess.CalledProcessError;TimeoutExpired=subprocess.TimeoutExpired
    def __init__(self,error=None,charge='0.0',change_binary=None):self.error=error;self.charge=charge;self.change_binary=change_binary;self.calls=[]
    def _run(self,argv,kwargs):
        self.calls.append((argv,kwargs));cwd=Path(kwargs['cwd']);(cwd/'charges').write_text(self.charge+'\n');(cwd/'xtbopt.xyz').write_text('1\nenergy: -1.2\nH 0 0 0\n')
        text='TOTAL ENERGY -1.2\nnormal termination of xtb\n'
        if 'stdout' in kwargs and hasattr(kwargs['stdout'],'write'):kwargs['stdout'].write(text.encode())
        if self.change_binary:self.change_binary.write_bytes(b'CHANGED')
        if self.error:raise self.error
        return text
    def check_call(self,argv,**kwargs):self._run(argv,kwargs);return 0
    def check_output(self,argv,**kwargs):return self._run(argv,kwargs)

class NativeEvaluationAudit(unittest.TestCase):
    def test_direct_entry_guards_before_scientific_imports(self):
        with self.assertRaises(RuntimeError):run_native_evaluation({},None,None,None,1)
        self.assertFalse(any(x in sys.modules for x in ('numpy','rdkit','torch','scipy','open3d')))
    def test_scientific_imports_are_function_scoped_and_no_weights(self):
        text=(ROOT/'server/native_evaluation.py').read_text();tree=ast.parse(text)
        self.assertNotIn('load_model',text);self.assertNotIn('load_checkpoint',text)
        for node in tree.body:
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                self.assertFalse(any(x in ast.unparse(node) for x in ('numpy','rdkit','torch','open3d','shepherd_score')))
        loads=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and ast.unparse(n.func)=='np.load']
        self.assertEqual(len(loads),2)
        for node in loads:self.assertIn('allow_pickle=False',ast.unparse(node))
        run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_native_evaluation')
        self.assertEqual([x.arg for x in run.args.args],['request','ids','root','output','seed'])
        self.assertNotIn("origin['eligible']",text)
    def test_callback_uses_both_native_arguments_and_external_sink(self):
        class Base:
            def _process_single_result(self,res,i):self.called=(res,i)
        sink={};obj=_capture_pipeline(Base,sink)();row={'i':2,'error':'original error','is_valid':False,'is_valid_post_opt':False,'is_graph_consistent':False,'sim_surf_target':float('nan')}
        obj._process_single_result(row,2);self.assertIs(obj.called[0],row);self.assertEqual(obj.called[1],2)
        self.assertEqual(sink[2]['error'],'original error');self.assertIsNone(sink[2]['sim_surf_target']);self.assertEqual(set(obj.__dict__),{'called'})
        with self.assertRaises(ValueError):obj._process_single_result(row,2)
        with self.assertRaises(ValueError):obj._process_single_result({**row,'i':7},3)
    def test_json_missing_is_not_zero(self):
        self.assertEqual(_json_safe([float('nan'),float('inf'),False,0]),[None,None,False,0])
    def test_archive_budget_and_duplicate_fields_checked_without_numpy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'raw.npz'
            header=b"{'descr': '|u1', 'fortran_order': False, 'shape': (300,)}\n";payload=b'\x93NUMPY\x01\x00'+struct.pack('<H',len(header))+header+b'x'*300
            with zipfile.ZipFile(path,'w') as z:z.writestr('atoms.npy',payload)
            with self.assertRaises(ValueError):_archive(path,100,{'atoms'})
            _archive(path,1000,{'atoms'})
            with self.assertRaises(ValueError):_archive(path,1000,{'positions'})
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                with zipfile.ZipFile(path,'a') as z:z.writestr('atoms.npy',b'y')
            with self.assertRaises(ValueError):_archive(path,2000,{'atoms'})
    def test_forged_npy_allocation_and_pickle_dtype_refused_without_numpy(self):
        for descr,shape in [('|u8',(10**15,)),('|O8',(1,))]:
            with self.subTest(descr=descr),tempfile.TemporaryDirectory() as tmp:
                header=repr({'descr':descr,'fortran_order':False,'shape':shape}).encode()+b'\n';payload=b'\x93NUMPY\x01\x00'+struct.pack('<H',len(header))+header+b'abcdefgh';path=Path(tmp)/'raw.npz'
                with zipfile.ZipFile(path,'w') as z:z.writestr('atoms.npy',payload)
                with self.assertRaises(ValueError):_archive(path,2000,{'atoms'})
    def test_all_origin_attempts_preserved_despite_zero_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'primary').mkdir();f=root/'primary/candidate_denominator.tsv';f.write_text('candidate_id\tstate\ngenerated_1\tFAILED\ngenerated_0\tFAILED\n')
            origin={'returned':root,'variant':'primary','origin':{'parameters':{'n_samples':2}},'outputs':{'primary/candidate_denominator.tsv':{'sha256':sha(f),'bytes':f.stat().st_size}},'eligible':[],'contract':{'resolved_sample_counts':[{'candidate_id':'generated_0','N_x1':1},{'candidate_id':'generated_1','N_x1':1}]}}
            names,rows,counts,_=_origin_attempts(origin);self.assertEqual(names,['generated_0','generated_1']);self.assertEqual(len(rows),2)
            f.write_text(f.read_text()+'generated_1\tFAILED\n');origin['outputs']['primary/candidate_denominator.tsv']={'sha256':sha(f),'bytes':f.stat().st_size}
            with self.assertRaises(ValueError):_origin_attempts(origin)
    def test_priority_uses_full_reference_axis_and_explicit_absent_complement(self):
        ref=types.SimpleNamespace(pharm_types=[1,2,3]);snap={'resolved_priority_mask_on_full_reference_axis':[1,0,1]}
        self.assertEqual(_priority(snap,ref,'origin_full_profile_mask','all')[0],[0,2])
        self.assertIsNone(_priority({'resolved_priority_mask_on_full_reference_axis':[1,1,1]},ref,'origin_full_profile_mask','all')[0])
        with self.assertRaises(ValueError):_priority({'resolved_priority_mask_on_full_reference_axis':[True,0,1]},ref,'origin_full_profile_mask','all')
    def fixture(self,tmp,backend):
        root=Path(tmp);cwd=root/'temporary_native';cwd.mkdir();(cwd/'input_mol.xyz').write_text('1\nsource\nH 0 0 0\n');exe=root/'xtb';exe.write_bytes(b'FAKE_BINARY_NOT_EXECUTABLE')
        module=types.SimpleNamespace(subprocess=backend);identity={'executable':str(exe.resolve()),'sha256':sha(exe)}
        return root,cwd,exe,module,identity
    def invoke(self,module,cwd,opt=False):
        argv=['xtb','input_mol.xyz','--opt' if opt else '--scc','--parallel','1','--chrg','0']
        if opt:return module.subprocess.check_call(argv,cwd=cwd,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT,timeout=10)
        return module.subprocess.check_output(argv,cwd=cwd,text=True,encoding='utf8',errors='replace',stderr=subprocess.STDOUT,timeout=10)
    def test_proxy_captures_both_calls_before_native_cleanup_and_restores_module(self):
        backend=FakeBackend();real_check=subprocess.check_call
        with tempfile.TemporaryDirectory() as tmp:
            root,cwd,exe,module,identity=self.fixture(tmp,backend)
            with patch('server.xtb_audit.shutil.which',return_value=str(exe)):
                with XtbAudit(module,root/'audit',identity,10,.001,10,root) as audit:
                    with audit.candidate('generated_5',0):
                        self.assertIn('TOTAL ENERGY',self.invoke(module,cwd));(cwd/'charges').unlink();(cwd/'xtbopt.xyz').unlink();self.assertEqual(self.invoke(module,cwd,True),0)
                self.assertIs(module.subprocess,backend);self.assertIs(subprocess.check_call,real_check)
                self.assertEqual(len(audit.records),2)
                for row in audit.records:
                    self.assertEqual(row['returncode'],0);self.assertTrue(row['evidence_complete']);self.assertFalse(row['method_cli_explicit']);self.assertEqual(row['requested_formal_charge'],0)
                    self.assertEqual(row['candidate_id'],'generated_5');self.assertEqual(row['energy_hartree'],-1.2);self.assertEqual(row['partial_charge_count'],1)
                shutil_target=root/'audit/call_000000/charges';self.assertTrue(shutil_target.exists())
    def test_nonzero_and_timeout_exceptions_preserved_not_replaced(self):
        for error,opt in [(subprocess.CalledProcessError(7,['xtb'],output=b'FAILED ORIGINAL'),False),(subprocess.TimeoutExpired(['xtb'],10,output=b'PARTIAL'),True)]:
            with self.subTest(error=type(error).__name__),tempfile.TemporaryDirectory() as tmp:
                backend=FakeBackend(error);root,cwd,exe,module,identity=self.fixture(tmp,backend)
                with patch('server.xtb_audit.shutil.which',return_value=str(exe)):
                    with XtbAudit(module,root/'audit',identity,10,.001,10,root) as audit:
                        with audit.candidate('generated_0',0):
                            with self.assertRaises(type(error)) as caught:self.invoke(module,cwd,opt)
                        self.assertIs(caught.exception,error)
                    row=audit.records[0];self.assertFalse(row['evidence_complete']);self.assertEqual(row['exception_type'],type(error).__name__)
                    if opt:self.assertTrue(row['timed_out']);self.assertIsNone(row['returncode'])
                    else:self.assertEqual(row['returncode'],7);self.assertEqual((root/'audit/call_000000/engine.log').read_bytes(),b'FAILED ORIGINAL')
    def test_charge_mismatch_does_not_rewrite_native_return_but_holds_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend=FakeBackend(charge='.2');root,cwd,exe,module,identity=self.fixture(tmp,backend)
            with patch('server.xtb_audit.shutil.which',return_value=str(exe)):
                with XtbAudit(module,root/'audit',identity,10,.001,10,root) as audit:
                    with audit.candidate('generated_0',0):self.assertIn('TOTAL ENERGY',self.invoke(module,cwd))
                self.assertFalse(audit.records[0]['evidence_complete']);self.assertIn('partial_charge_sum_outside_prespecified_tolerance',audit.records[0]['evidence_issues'])
    def test_unattributed_call_is_recorded_and_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,cwd,exe,module,identity=self.fixture(tmp,FakeBackend())
            with XtbAudit(module,root/'audit',identity,10,.001,10,root) as audit:
                with self.assertRaises(RuntimeError):self.invoke(module,cwd)
            self.assertEqual(audit.records,[]);self.assertTrue(audit.capture_errors[0]['invocation_rejected_before_engine_start'])
    def test_owned_work_restores_cwd_environment_and_module_constants_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            original=Path.cwd();env={k:os.environ.get(k) for k in ('TMPDIR','TEMP','TMP')};a=types.SimpleNamespace(TMPDIR='ORIGINAL');b=types.SimpleNamespace()
            with self.assertRaisesRegex(ValueError,'expected'):
                with _owned_native_work(Path(tmp),[a,b]) as work:
                    self.assertEqual(Path.cwd(),work);self.assertEqual(a.TMPDIR,work);self.assertEqual(b.TMPDIR,work);self.assertEqual(os.environ['TMPDIR'],str(work));raise ValueError('expected')
            self.assertEqual(Path.cwd(),original);self.assertEqual(a.TMPDIR,'ORIGINAL');self.assertFalse(hasattr(b,'TMPDIR'));self.assertEqual({k:os.environ.get(k) for k in env},env)
    def test_outside_cwd_and_restart_artifacts_are_refused_before_engine(self):
        for outside in (True,False):
            with self.subTest(outside=outside),tempfile.TemporaryDirectory() as tmp:
                backend=FakeBackend();root,cwd,exe,module,identity=self.fixture(tmp,backend);owned=root/'owned';owned.mkdir()
                if not outside:
                    cwd=owned/'fresh';cwd.mkdir();(cwd/'input_mol.xyz').write_text('1\nsource\nH 0 0 0\n');(cwd/'xtbrestart').write_text('OLD')
                with patch('server.xtb_audit.shutil.which',return_value=str(exe)):
                    with XtbAudit(module,root/'audit',identity,10,.001,10,owned) as audit:
                        with audit.candidate('generated_0',0):
                            with self.assertRaises(ValueError):self.invoke(module,cwd)
                    self.assertEqual(backend.calls,[]);self.assertTrue(audit.capture_errors)

if __name__=='__main__':unittest.main()
