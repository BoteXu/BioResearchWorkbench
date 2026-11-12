"""Source, planning and evidence-format fixtures only. No molecule/quantum/model calculation."""
from pathlib import Path
import sys,unittest,tempfile,json,copy,ast
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'server')]
from contracts import read,sha,write,digest,validate,prepare,METHODS,sources
from material_contracts import context,material,numerical_QC,checkpoint
from server.runtime import guard
from server.return_binding import proof_issues,preview_issues
from handoff import prepare_link
def fixture(method='score_fixed_pose'):
    r=read(ROOT/'examples'/(method+'.project.example.json'));r['example_only']=False;return r
class Contracts(unittest.TestCase):
    def test_four_actual_call_routes_have_explicit_contracts(self):
        for key in METHODS:validate(fixture(key))
        worker=(ROOT/'server/worker.py').read_text(encoding='utf8')+(ROOT/'server/generation.py').read_text(encoding='utf8')
        for call in ('mp.score_with_esp','pair.align_with_esp','model.generate(','model.generate_composition('):self.assertIn(call,worker)
    def test_every_example_is_disabled(self):
        for f in (ROOT/'examples').glob('*.json'):
            with self.subTest(example=f.name),self.assertRaises(ValueError):validate(read(f))
    def test_public_upload_refused(self):
        r=fixture();r['public_upload']=True
        with self.assertRaises(ValueError):validate(r)
    def test_automatic_weight_download_refused(self):
        r=fixture('shepherd2_generate');r['automatic_download']=True
        with self.assertRaises(ValueError):validate(r)
    def test_unknown_model_arguments_refused(self):
        r=fixture();r['parameters']['additional_shell_command']='UNREVIEWED'
        with self.assertRaises(ValueError):validate(r)
    def test_missing_exact_dependency_version_refused(self):
        r=fixture();r['parameters']['expected_versions'].pop('shepherd-score')
        with self.assertRaises(ValueError):validate(r)
    def test_invalid_binary_identity_refused(self):
        r=fixture();r['parameters']['expected_xtb_sha256']='unknown'
        with self.assertRaises(ValueError):validate(r)
    def test_gpu_requires_actual_declared_allocation(self):
        r=fixture();r['parameters']['device']='cuda'
        with self.assertRaises(ValueError):validate(r)
    def test_duplicate_seed_is_not_a_new_run(self):
        r=fixture();r['sensitivity_variants'][1]['seed']=r['sensitivity_variants'][0]['seed']
        with self.assertRaises(ValueError):validate(r)
    def test_seed_is_not_boolean(self):
        r=fixture();r['parameters']['seed']=True
        with self.assertRaises(ValueError):validate(r)
    def test_bool_valid_fraction_refused(self):
        r=fixture('shepherd2_generate');r['parameters']['min_valid_fraction']=True
        with self.assertRaises(ValueError):validate(r)
    def test_nonfinite_composition_weight_refused(self):
        r=fixture('shepherd2_generate');r['parameters']['profile_weights']=[float('nan')]
        with self.assertRaises(ValueError):validate(r)
    def test_missing_numerical_acceptance_gates_refused(self):
        r=fixture();r['acceptance_rules']=[]
        with self.assertRaises(ValueError):validate(r)
    def test_path_escape_refused(self):
        r=fixture();r['inputs'][0]['path']='../private_file'
        with self.assertRaises(ValueError):validate(r)
    def test_preparation_copies_exact_hash_bound_source(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'prepared';prepare(fixture(),out);r=read(out/'request.private.json');self.assertFalse(r['server_execution_authorized']);self.assertTrue(all(sha(out/k)==v for k,v in r['source_sha256'].items()));self.assertEqual(r['source_sha256'],sources())
    def test_local_runtime_refuses_before_scientific_imports(self):
        with self.assertRaises(RuntimeError):guard({})
        self.assertNotIn('numpy',sys.modules);self.assertNotIn('torch',sys.modules)
    def test_direct_local_worker_cannot_bypass_server_guard(self):
        from server.worker import execute
        with self.assertRaises(RuntimeError):execute({}, {}, ROOT, ROOT, 1)
        self.assertNotIn('rdkit',sys.modules)
    def good_context(self):return {'public_upload':False,'protonation_reviewed':True,'stereochemistry_reviewed':True,'structure_source_reviewed':True,'coordinates_unit':'angstrom','frame_id':'FIXTURE_FRAME','frame_kind':'ligand_reference','preparation_domain_sha256':'a'*64,'pH':7.4,'limitations':['Fictional contract fixture only']}
    def test_docking_frame_needs_receptor_and_site_identity(self):
        c=self.good_context();c['frame_kind']='docking_complex'
        with self.assertRaises(ValueError):context(c)
    def test_molecular_charge_is_not_boolean(self):
        c=self.good_context();row={'id':'CANDIDATE','role':'candidate','parent_id':'P','microstate_id':'STATE','formal_charge':True,'frame_id':c['frame_id'],'preparation_domain_sha256':c['preparation_domain_sha256']}
        with self.assertRaises(ValueError):material(row,c)
    def test_unreviewed_protonation_cannot_be_truthy_text(self):
        c=self.good_context();c['protonation_reviewed']='true'
        with self.assertRaises(ValueError):context(c)
    def test_finite_pH_is_required(self):
        c=self.good_context();c['pH']=float('nan')
        with self.assertRaises(ValueError):context(c)
    def test_exact_preparation_domain_required(self):
        c=self.good_context();c['preparation_domain_sha256']='status passed'
        with self.assertRaises(ValueError):context(c)
    def qc_fixture(self,root):
        # Text fixtures only; this intentionally does not parse or validate a real SDF.
        sdf=root/'fixture.sdf';sdf.write_text('FICTIONAL_EVIDENCE_FORMAT_ONLY',encoding='utf8');measure=root/'measure.json';write(measure,{'fixture_value':.1});receipt=root/'receipt.json';write(receipt,{'state':'COMPLETED','exit_code':0,'inputs':[{'sha256':sha(sdf)}],'outputs':[{'sha256':sha(measure)}]});row={'qc_measurements':{'path':measure.name,'sha256':sha(measure)},'qc_receipt':{'path':receipt.name,'sha256':sha(receipt)},'qc_rules':[{'field':'fixture_value','operator':'le','bound':.2,'observed':.1,'unit':'fixture','definition':'No scientific meaning','threshold_basis':'FORMAT_TEST_ONLY'}]};return sdf,row
    def test_QC_is_bound_to_actual_completed_input_and_measurement(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);sdf,row=self.qc_fixture(root);_,_,audit=numerical_QC(row,root,sdf);self.assertEqual(audit[0]['input_sdf_sha256'],sha(sdf))
    def test_QC_self_report_cannot_replace_actual_measurement(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);sdf,row=self.qc_fixture(root);row['qc_rules'][0]['observed']=0
            with self.assertRaises(ValueError):numerical_QC(row,root,sdf)
    def test_QC_without_scientific_threshold_basis_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);sdf,row=self.qc_fixture(root);row['qc_rules'][0].pop('threshold_basis')
            with self.assertRaises(ValueError):numerical_QC(row,root,sdf)
    def test_untrusted_checkpoint_refused_before_loading(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):checkpoint({'trust_decision':'UNKNOWN'},Path(t))
    def test_native_python_sources_are_pinned(self):
        pins=read(ROOT/'upstream_code.json');self.assertEqual(set(pins),{'shepherd2','shepherd-score'});self.assertTrue(all(len(x['commit'])==40 and len(x['python_blobs'])>10 for x in pins.values()))
    def test_method_source_parses_without_executing_engines(self):
        for f in ROOT.rglob('*.py'):ast.parse(f.read_text(encoding='utf8'),filename=str(f))
