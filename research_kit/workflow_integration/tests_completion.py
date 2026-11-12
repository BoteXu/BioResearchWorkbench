"""Adversarial source/receipt contracts only. No scientific engine is executed."""
from pathlib import Path
import ast,csv,hashlib,json,sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'server'))
from server.completion_contracts import ROUTES,SOURCES,PACKAGES,COMMON_ROLES,validate
from completion_acceptance import inspect_completion

def parameters(mode):
    r=ROUTES[mode];p={k:1 for k in r['params']}
    p.update(seed=42,software_versions={k:'contract-only-not-installed' for k in PACKAGES[mode]},maximum_output_entries=10000)
    for key in ['accelerator']: 
        if key in p:p[key]='cpu'
    for key in ['gaussian_sampling','clip_denoised']:
        if key in p:p[key]=True
    if 'source' in r:p['repository']='/owned/reviewed/source'
    if 'executable' in p:p.update(executable='/owned/reviewed/engine',executable_sha256='a'*64,native_version='DIA-NN 2.7.0 Academia' if mode=='diann_quantify' else 'DOCK 3.7' if mode=='dockovalent' else 'SIRIUS 6.3')
    if mode=='scdiffusion_generate':p.update(guidance=[],diffusion_config={'diffusion_steps':1000},sampling_method='ddpm')
    if mode=='sirius_formulas':p['instrument']='orbitrap'
    if mode=='diann_quantify':p.update(raw_input_ids=['raw1'],qvalue=.01)
    if mode=='dockovalent':p.update(prepared_input_ids=['grid'],pose_glob='*.mol2.gz',score_file='OUTDOCK',bond_distance_angstrom=[1,2],native_score_columns=['mol_number','ligand_id','total'])
    if mode.startswith('morphdiff'):p.update(image_width=128,image_height=128,accelerator='gpu')
    if mode=='gnps_offline_network':p['cosine_cutoff']=.7
    for key in ['mask_rate','prompt_ratio','context_ratio']:
        if key in p:p[key]=.25
    return p

class CompletionContracts(unittest.TestCase):
    def test_exact_thirteen_fixed_routes(self):self.assertEqual(len(ROUTES),13)
    def test_every_route_declares_real_scientific_artifacts(self):
        for key,r in ROUTES.items():
            with self.subTest(route=key):
                c=validate(key,parameters(key));self.assertGreater(len(c['required_roles']),len(COMMON_ROLES));self.assertTrue(r['kind'])
    def test_dependencies_cannot_be_replaced_with_one_status_package(self):
        for key in ROUTES:
            p=parameters(key);p['software_versions']={'fake':'1'}
            with self.subTest(route=key),self.assertRaises(ValueError):validate(key,p)
    def test_unconsumed_sampler_parameter_rejected_for_every_route(self):
        for key in ROUTES:
            p=parameters(key);p['ignored_sampler_choice']='anything'
            with self.subTest(route=key),self.assertRaises(ValueError):validate(key,p)
    def test_actual_native_input_roles_required(self):
        for key in ROUTES:
            with self.subTest(route=key),self.assertRaises(ValueError):validate(key,parameters(key),{})
    def test_nonfinite_cutoff_is_not_admitted(self):
        p=parameters('gnps_offline_network');p['cosine_cutoff']=float('nan')
        with self.assertRaises(ValueError):validate('gnps_offline_network',p)
    def test_boolean_is_not_native_numeric_budget(self):
        p=parameters('prnet_predict');p['batch_size']=True
        with self.assertRaises(ValueError):validate('prnet_predict',p)
    def test_commercial_diann_edition_excluded(self):
        p=parameters('diann_quantify');p['native_version']='DIA-NN Enterprise 2.7.0'
        with self.assertRaises(ValueError):validate('diann_quantify',p)
    def test_dock38_not_substituted_for_covalent37(self):
        p=parameters('dockovalent');p['native_version']='DOCK 3.8'
        with self.assertRaises(ValueError):validate('dockovalent',p)
    def test_native_output_cannot_escape_stage(self):
        p=parameters('dockovalent');p['score_file']='../OUTDOCK'
        with self.assertRaises(ValueError):validate('dockovalent',p)
    def test_morphdiff_actual_factor_four_grid(self):
        p=parameters('morphdiff_gene2image');p['image_width']=129
        with self.assertRaises(ValueError):validate('morphdiff_gene2image',p)
    def test_morphdiff_native_cuda_requirement_is_not_hidden(self):
        for mode in ['morphdiff_gene2image','morphdiff_image2image']:
            p=parameters(mode);p['accelerator']='cpu'
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'forces CUDA'):validate(mode,p)
    def test_same_named_source_is_not_interchangeable(self):
        self.assertEqual(SOURCES['morphdiff'][0],'biomap-research/MorphDiff');self.assertEqual(SOURCES['scdiffusion'][0],'EperLuo/scDiffusion')
    def test_classifier_guidance_needs_actual_input(self):
        p=parameters('scdiffusion_generate');p.update(guidance=[{'input_id':'classifier1','config':{},'target_class':0,'class_label':'actual_class','scale':1}],guidance_start_step=500)
        with self.assertRaises(ValueError):validate('scdiffusion_generate',p,dict.fromkeys(ROUTES['scdiffusion_generate']['inputs']))
    def test_more_than_two_guidance_models_not_claimed(self):
        p=parameters('scdiffusion_generate');p['guidance']=[{}]*3
        with self.assertRaises(ValueError):validate('scdiffusion_generate',p)
    def test_unused_guidance_setting_cannot_be_ignored(self):
        p=parameters('scdiffusion_generate');p['guidance_start_step']=500
        with self.assertRaises(ValueError):validate('scdiffusion_generate',p)
    def test_no_current_server_status_invented(self):
        d=json.loads((ROOT/'CURRENT.json').read_text(encoding='utf8'));self.assertEqual(d['server_live_status'],'NOT_PROBED_THIS_UPGRADE');self.assertEqual(d['scientific_runtime'],'NOT_RUN_THIS_UPGRADE')
    def test_71_historical_registry_preserved_exactly(self):self.assertEqual(hashlib.sha256((ROOT/'server/branches71.json').read_bytes()).hexdigest(),'bf773dbd22a5b6b3059c753dd39da7886d34492ee5eec958025ac13c513d9116')
    def test_71_fresh_reviews_bind_current_producers(self):
        rows=json.loads((ROOT/'method_review71.json').read_text(encoding='utf8'));self.assertEqual(len(rows),71)
        for row in rows:
            with self.subTest(method=row['analysis_id']):self.assertEqual(row['source_sha256'],hashlib.sha256((ROOT/row['source']).read_bytes()).hexdigest());self.assertEqual(row['server_runtime'],'NOT_RUN_THIS_UPGRADE');self.assertTrue(row['method_specific_result_gate'])
    def test_local_execution_rejected_before_native_child_launch(self):
        from completion_runtime import analyze
        with patch('completion_runtime.sys.platform','win32'),patch('completion_runtime.native_command') as launch:
            with self.assertRaises(RuntimeError):analyze({},parameters('prnet_predict'),ROOT,'prnet_predict')
            launch.assert_not_called()
    def test_direct_child_function_cannot_bypass_local_guard(self):
        from completion_runtime import execute_isolated
        with patch('completion_runtime.sys.platform','win32'):
            with self.assertRaises(RuntimeError):execute_isolated({},parameters('prnet_predict'),ROOT,'prnet_predict')
    def test_no_unreachable_statement_after_raise(self):
        for filename in ['native71.py','cli71.py','cell71.py','completion_common.py','completion_models.py','completion_engines.py','completion_spectra.py']:
            tree=ast.parse((ROOT/'server'/filename).read_text(encoding='utf8'))
            for node in ast.walk(tree):
                for field in ['body','orelse','finalbody']:
                    body=getattr(node,field,[])
                    if not isinstance(body,list):continue # lambda/IfExp bodies are expressions, not suites.
                    for i,statement in enumerate(body[:-1]):
                        with self.subTest(file=filename,line=getattr(statement,'lineno',None)):self.assertNotIsInstance(statement,ast.Raise)
    def test_real_weight_loading_never_falls_back_to_pickle_objects(self):
        t=ast.parse((ROOT/'server/completion_common.py').read_text(encoding='utf8'))
        calls=[n for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='load' and isinstance(n.func.value,ast.Name) and n.func.value.id=='torch']
        self.assertTrue(calls);self.assertTrue(all(any(k.arg=='weights_only' and isinstance(k.value,ast.Constant) and k.value.value is True for k in call.keywords) for call in calls))
    def test_actual_protocol_APIs_present_not_scaffold_only(self):
        source=(ROOT/'server/completion_models.py').read_text(encoding='utf8')
        for symbol in ['PGM(**cfg)','create_model_and_diffusion(**cfg)','get_incontext_prediction(','FinetuneModel()','sampler.stochastic_encode(','torch.autograd.grad(']:self.assertIn(symbol,source)
    def test_csi_import_has_no_live_fingerprint_entry(self):
        source=(ROOT/'server/completion_spectra.py').read_text(encoding='utf8');tree=ast.parse(source);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='csi_import');calls=[ast.unparse(n.func) for n in ast.walk(fn) if isinstance(n,ast.Call)];self.assertNotIn('native_command',calls)
    def test_empty_proof_is_not_result_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=root/'d.json';proof=root/'p.json';d.write_text(json.dumps({'mode':'prnet_predict','software_versions':parameters('prnet_predict')['software_versions'],'data_kind':ROUTES['prnet_predict']['kind'],'metrics':{'queries':2}}));proof.write_text(json.dumps({'schema':'native-completion-proof/1','mode':'prnet_predict','input_semantics':ROUTES['prnet_predict']['kind'],'outputs':[]}))
            local={k:d for k in COMMON_ROLES};local['result_channel_proof']=proof
            issues=inspect_completion({'backend':'prnet_predict','parameters':parameters('prnet_predict')},{'outputs':[]},local,lambda x:json.loads(x.read_text()),lambda x:([],[]));self.assertIn('actual_native_scientific_channel_missing:prediction_matrix',issues)
    def test_context_does_not_authorize_public_upload(self):
        from completion_common import context
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'context.json';path.write_text(json.dumps(dict.fromkeys(['species','independent_unit','assay','reference_version','contrast','limitations'],'actual')|{'public_upload':True}))
            with self.assertRaises(ValueError):context({'context':path})

if __name__=='__main__':unittest.main()
