"""Engineering/semantic adversarial fixtures, not real scientific-run examples."""
from pathlib import Path
import os,sys,json,copy,tempfile,unittest,importlib.util
os.environ['MPLBACKEND']='Agg';sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];SKILL=ROOT/'scientific-visualization';SCRIPTS=SKILL/'scripts'
sys.path.insert(0,str(SCRIPTS))
import numpy as np,matplotlib.pyplot as plt
from renderers import render_template
from shap_channels import prepare_shap_display
from native_figures import digest,plan_native_figures,_one,native_shap_data,render_native_matrix,render_batchie_intervals

def dump(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def shap_case(unit='probability'):
 return {'features':['literal_A','literal_B'],'positive_class':'Actual event','explanation':{'shap':[[.02,-.01],[.03,.01]],'feature_values':[[10,1000],[20,4000]],'unit':unit,'output':'probability' if unit=='probability' else 'decision_function','link':'identity','scope':'CONTRACT_FIXTURE_ONLY'}}

class NativeFixture:
 def __init__(self,folder,backend='ml',files=None):
  self.root=Path(folder);self.request=self.root/'request.json';self.receipt=self.root/'receipt.json';self.acceptance=self.root/'qc.json';self.source={'fixture_source.py':'a'*64};self.selection={};outputs=[]
  for name,(role,content) in (files or {'a.tsv':('shap_summary','feature_id\tmean_abs_shap\nliteral_A\t1\n')}).items():
   p=self.root/name;p.write_text(content,encoding='utf8');self.selection.setdefault(role,[]).append(name);outputs.append({'path':name,'role':role,'sha256':digest(p),'bytes':p.stat().st_size})
  request={'test_fixture':'NOT_A_SERVER_RUN','backend':backend,'source_sha256':self.source,'plan_sha256':'b'*64,'required_roles':list(self.selection),'parameters':{}}
  dump(self.request,request);dump(self.receipt,{'test_fixture':'NOT_A_SERVER_RUN','state':'COMPLETED','exit_code':0,'request_sha256':digest(self.request),'source_sha256':self.source,'outputs':outputs})
  dump(self.acceptance,{'test_fixture':'NOT_A_SCIENTIFIC_ACCEPTANCE','state':'RETURN_CHECKS_PASS','issues':[],'request_sha256':digest(self.request),'receipt_sha256':digest(self.receipt),'plan_sha256':'b'*64})
 def plan(self):return plan_native_figures(self.request,self.receipt,self.root,self.acceptance,self.selection,self.source)

class ReviewChecks(unittest.TestCase):
 def tearDown(self):plt.close('all')
 def test_catalog_identity_and_counts_preserved(self):
  old=json.loads((ROOT/'tests/catalog_identity_baseline.json').read_text())
  new=json.loads((SKILL/'assets/figure_catalog.json').read_text())
  self.assertEqual({x['id'] for x in old['figures']},{x['id'] for x in new['figures']});self.assertEqual(new['counts'],{'figures':140,'modules':22,'composites':7})
 def test_all_49_actual_routes_mapped(self):
  d=json.loads((SKILL/'assets/workflow_channels.json').read_text());self.assertEqual(len(d['routes']),63)
  self.assertIn('reference reconstruction',d['routes']['causcell_counterfactual_fit']['interpretation_boundary'])
 def test_missing_shap_unit_rejected(self):
  d=shap_case();del d['explanation']['unit']
  with self.assertRaises(ValueError):prepare_shap_display(d)
 def test_probability_cannot_be_relabelled_logodds(self):
  d=shap_case();d['explanation']['unit']='log-odds'
  with self.assertRaises(ValueError):prepare_shap_display(d)
 def test_raw_feature_colors_are_not_fake_standardized_values(self):
  d=shap_case();before=copy.deepcopy(d);display,m=prepare_shap_display(d)
  np.testing.assert_array_equal(display['explanation']['feature_values'],[[0,0],[1,1]]);self.assertEqual(d,before);self.assertEqual(m['feature_value_mode'],'within_feature_range')
 def test_constant_feature_color_is_midpoint(self):
  d=shap_case();d['explanation']['feature_values']=[[1,0],[1,10]];v,m=prepare_shap_display(d)
  np.testing.assert_array_equal(v['explanation']['feature_values'][:,0],[.5,.5]);self.assertEqual(m['color_bounds_per_output'][0]['constant_features'],['literal_A'])
 def test_full_share_denominator_and_remainder(self):
  d=shap_case();v,m=prepare_shap_display(d);self.assertAlmostEqual(sum(m['full_feature_shares'][0]),1)
  fig,meta=render_template('shap_summary',d,max_features=1);self.assertEqual(meta['layout'],'small_rose_inset');self.assertEqual(meta['source_feature_count'],2);self.assertIn('Other 1 features',meta['share_features'])
 def test_mismatched_share_table_rejected(self):
  d=shap_case();d['share_table']=[[1,0]]
  with self.assertRaises(ValueError):prepare_shap_display(d)
 def test_zero_contributions_not_empty_rose(self):
  d=shap_case();d['explanation']['shap']=[[0,0],[0,0]]
  with self.assertRaises(ValueError):prepare_shap_display(d)
 def test_native_shape_shap_without_roc_models_is_callable(self):
  fig,m=render_template('shap_summary',shap_case(),width='single');self.assertEqual(m['unit'],'probability');self.assertEqual(m['layout'],'small_rose_inset')
  self.assertTrue(any('probability' in a.get_xlabel() for a in fig.axes));self.assertFalse(any('log-odds' in a.get_xlabel() for a in fig.axes))
 def test_optional_shap_forms_keep_actual_unit(self):
  for variant in ['swarm','rose','beeswarm_rose']:
   fig,m=render_template('shap_summary',shap_case(),variant=variant);self.assertEqual(m['unit'],'probability');plt.close(fig)
 def test_preserved_multiclass_entry_does_not_require_dummy_model_data(self):
  d={'features':['A','B'],'unit':'probability','class_contributions':[{'label':'output1','shap':[[.1,.2],[.2,.1]],'feature_values':[[1,2],[3,4]]},{'label':'output2','shap':[[-.1,-.2],[-.2,-.1]],'feature_values':[[1,2],[3,4]]}]}
  fig,m=render_template('shap_summary',d);self.assertEqual(m['source_class_order'],['output1','output2']);self.assertEqual(m['unit'],'probability')
 def test_single_feature_dependence_is_supported(self):
  d=shap_case();d['features']=['literal_A'];d['explanation']['shap']=[[.1],[.2]];d['explanation']['feature_values']=[[1],[2]]
  fig,m=render_template('shap_dependence',d);self.assertIn('probability',fig.axes[0].get_ylabel())
 def test_confusion_uses_actual_order_and_unknown_evaluation(self):
  d={'models':{'model':{'confusion':[[0,0],[1,3]]}},'positive_class':'Actual event','class_labels':['Actual reference','Actual event']}
  fig,m=render_template('confusion',d);self.assertEqual(m['class_labels'],d['class_labels']);self.assertEqual(m['predictions'],'UNSPECIFIED_NOT_VALIDATED');self.assertIsNone(m['threshold'])
  texts=[t.get_text() for a in fig.axes for t in a.texts];self.assertTrue(any('NA' in t for t in texts))
 def test_roc_does_not_invent_fold_number(self):
  d={'models':{'model':{'roc':{'x':[0,.2,1],'y':[0,.8,1]}}},'positive_class':'Actual event'}
  fig,m=render_template('roc_multi',d);self.assertEqual(m['predictions'],'UNSPECIFIED_NOT_VALIDATED');self.assertNotIn('OOF',str(m))
 def test_bad_roc_axes_are_not_rescaled(self):
  d={'models':{'model':{'roc':{'x':[0,2],'y':[0,1]}}}}
  with self.assertRaises(ValueError):render_template('roc_multi',d)
 def test_pca_group_order_cannot_drop_condition(self):
  with self.assertRaises(ValueError):render_template('pca_samples',{'pca':[[1,0],[2,1]],'groups':['A','B'],'group_order':['A']})
 def test_pca_variance_percent_is_not_silently_converted(self):
  with self.assertRaises(ValueError):render_template('pca_samples',{'pca':[[1,0],[2,1]],'groups':['A','A'],'pca_variance':[60,20]})
 def test_pca_outlier_score_zip_cannot_truncate(self):
  with self.assertRaises(ValueError):render_template('pca_outlier',{'pca':[[1,0],[2,1]],'groups':['A','A'],'sample_ids':['s1','s2'],'outlier_scores':[0]})
 def test_heatmap_group_blocks_cannot_drop_columns(self):
  d={'matrix':{'values':[[1,2],[3,4]],'rows':['a','b'],'columns':['s1','s2']},'groups':['A','B'],'group_order':['A']}
  with self.assertRaises(ValueError):render_template('deg_heatmap',d,cluster_mode='condition_blocks')
 def test_source_hierarchy_is_used_without_reclustering(self):
  d={'matrix':{'values':[[1,2],[2,3],[5,6]],'rows':['a','b','c'],'columns':['x','y']},'row_linkage':[[2,1,1,2],[0,3,2,3]],'row_linkage_ids':['a','b','c'],'hierarchy_method':'source average','hierarchy_row_distance':'1-TOM'}
  fig,m=render_template('deg_heatmap',d);self.assertEqual(m['row_order'],['a','c','b']);self.assertEqual(m['column_order'],['x','y']);self.assertEqual(m['hierarchy_source'],'supplied frozen linkage');self.assertEqual(m['row_distance'],'1-TOM')
 def test_source_tree_and_new_condition_blocks_conflict(self):
  d={'matrix':{'values':[[1,2],[3,4]],'rows':['a','b'],'columns':['x','y']},'row_linkage':[[0,1,1,2]],'groups':['A','B']}
  with self.assertRaises(ValueError):render_template('deg_heatmap',d,cluster_mode='condition_blocks')
 def test_source_tree_cannot_use_reordered_axis_ids(self):
  d={'matrix':{'values':[[1,2],[3,4]],'rows':['a','b'],'columns':['x','y']},'row_linkage':[[0,1,1,2]],'row_linkage_ids':['b','a']}
  with self.assertRaises(ValueError):render_template('deg_heatmap',d)
 def test_completed_bindings_are_required(self):
  with tempfile.TemporaryDirectory() as t:
   f=NativeFixture(t);r=json.loads(f.receipt.read_text());r['state']='RUNNING';dump(f.receipt,r)
   with self.assertRaises(ValueError):f.plan()
 def test_source_change_expires_acceptance(self):
  with tempfile.TemporaryDirectory() as t:
   f=NativeFixture(t);f.source={'changed.py':'c'*64}
   with self.assertRaises(ValueError):f.plan()
 def test_qc_hold_is_not_hidden(self):
  with tempfile.TemporaryDirectory() as t:
   f=NativeFixture(t);q=json.loads(f.acceptance.read_text());q['state']='HOLD';dump(f.acceptance,q)
   with self.assertRaises(ValueError):f.plan()
 def test_repeated_role_needs_explicit_path(self):
  with tempfile.TemporaryDirectory() as t:
   f=NativeFixture(t,files={'a.tsv':('shap_summary','x\ty\na\t1\n'),'b.tsv':('shap_summary','x\ty\nb\t2\n')});p=f.plan()
   self.assertEqual(len(p['selected']['shap_summary']),2)
   with self.assertRaises(ValueError):_one(p,'shap_summary')
   self.assertEqual(_one(p,'shap_summary','a.tsv').name,'a.tsv')
 def test_change_after_planning_is_detected(self):
  with tempfile.TemporaryDirectory() as t:
   f=NativeFixture(t);p=f.plan();(Path(t)/'a.tsv').write_text('changed')
   with self.assertRaises(ValueError):_one(p,'shap_summary')
 def test_unknown_path_is_not_looked_up_elsewhere(self):
  with tempfile.TemporaryDirectory() as t:
   f=NativeFixture(t);f.selection['shap_summary']=['../other.tsv']
   with self.assertRaises(ValueError):f.plan()
 def test_abundance_is_not_normalized_to_proportions(self):
  with tempfile.TemporaryDirectory() as t:
   f=NativeFixture(t,'cell2location_map',{'a.tsv':('celltype_abundance','spot\tT\tB\ns1\t8\t3\ns2\t9\t5\n')});p=f.plan()
   fig,m=render_native_matrix(p,'celltype_abundance');self.assertEqual(m['unit'],'Estimated cell abundance')
   with self.assertRaises(ValueError):render_native_matrix(p,'celltype_abundance',unit='fraction')
 def test_invalid_proportions_are_rejected_without_renormalization(self):
  with tempfile.TemporaryDirectory() as t:
   f=NativeFixture(t,'destvi_deconvolution',{'a.tsv':('celltype_proportions','spot\tT\tB\ns1\t8\t3\n')})
   with self.assertRaises(ValueError):render_native_matrix(f.plan(),'celltype_proportions')
 def test_batchie_q05_q95_are_90_percent_credible_intervals(self):
  text='row_id\tobserved\tposterior_mean_viability\tposterior_q05_viability\tposterior_q95_viability\nr1\tfalse\t0.4\t0.2\t0.6\n'
  with tempfile.TemporaryDirectory() as t:
   f=NativeFixture(t,'batchie_posterior',{'b.tsv':('combination_predictions',text)});fig,m=render_batchie_intervals(f.plan());self.assertEqual(m['interval_mass'],.9);self.assertEqual(m['interval_kind'],'posterior_credible_conditional_mean')
 def test_upstream_shap_metadata_is_engine_free_and_scale_correct(self):
  p=ROOT/'workflow_integration/server/shap_native.py';spec=importlib.util.spec_from_file_location('reviewed_shap_metadata',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  self.assertEqual(m.display_metadata({'output':'probability','class_label':'Event'})['contribution_unit'],'probability')
  self.assertEqual(m.display_metadata({'output':'decision_function'})['contribution_unit'],'model decision score')
  self.assertEqual(m.display_metadata({'output':'response','response_unit':'mm'})['contribution_unit'],'mm')
 def test_native_four_file_shap_reader_and_tamper_rejection(self):
  import pandas as pd
  with tempfile.TemporaryDirectory() as t:
   files={n:(role,'temporary fixture content') for n,role in [('v.npz','shap_values'),('d.json','shap_diagnostics'),('s.tsv','shap_summary'),('i.tsv','shap_identity')]}
   f=NativeFixture(t,'ml',files);root=Path(t);a=np.array([[.02,-.01],[.03,.01]]);base=np.array([.4,.4]);pred=base+a.sum(axis=1);ids=['test1','test2'];features=['literal_A','literal_B']
   np.savez(root/'v.npz',values=a,base_values=base,model_output=pred,original_feature_values=np.array([[10,1000],[20,4000]]),feature_names=np.asarray(features),unit_ids=np.asarray(ids))
   cfg={'output':'probability','class_label':'Actual event','background_units':['train1'],'explain_units':ids,'additivity_tolerance':1e-8}
   dump(root/'d.json',{'model':'actual_model','algorithm':'CONTRACT_FIXTURE_ONLY','output':'probability','output_name':'Actual event','contribution_unit':'probability','link':'identity','background_units':['train1'],'explained_units':ids,'feature_axis':features,'additivity_pass':True,'additivity_tolerance':1e-8})
   pd.DataFrame({'feature_id':features,'mean_abs_shap':abs(a).mean(axis=0),'mean_shap':a.mean(axis=0)}).to_csv(root/'s.tsv',sep='\t',index=False)
   pd.DataFrame({'unit_id':ids,'base_value':base,'model_output':pred,'sum_shap':a.sum(axis=1)}).to_csv(root/'i.tsv',sep='\t',index=False)
   req=json.loads(f.request.read_text());req['parameters']['shap']=cfg;dump(f.request,req);rec=json.loads(f.receipt.read_text());rec['request_sha256']=digest(f.request)
   for row in rec['outputs']:p=root/row['path'];row.update(sha256=digest(p),bytes=p.stat().st_size)
   dump(f.receipt,rec);qc=json.loads(f.acceptance.read_text());qc.update(request_sha256=digest(f.request),receipt_sha256=digest(f.receipt));dump(f.acceptance,qc)
   plan=f.plan();d=native_shap_data(plan,'actual_model');np.testing.assert_array_equal(d['explanation']['shap'],a);self.assertEqual(d['positive_class'],'Actual event')
   (root/'s.tsv').write_text('changed')
   with self.assertRaises(ValueError):native_shap_data(plan,'actual_model')
 def test_unlabelled_interval_does_not_claim_95_percent(self):
  fig,m=render_template('forest',{'table':[{'label':'fixture','estimate':1,'lo':0,'hi':2}]});self.assertNotIn('95',m['interval_label'])
 def test_posterior_mean_can_lie_outside_equal_tail_interval(self):
  text='row_id\tobserved\tposterior_mean_viability\tposterior_q05_viability\tposterior_q95_viability\nr1\tfalse\t0.225\t0.1\t0.2\n'
  with tempfile.TemporaryDirectory() as t:
   f=NativeFixture(t,'batchie_posterior',{'b.tsv':('combination_predictions',text)});fig,m=render_batchie_intervals(f.plan());self.assertEqual(m['interval_mass'],.9)
 def test_zero_interaction_does_not_invent_tiny_color_range(self):
  d={'models':{},'explanation':{'unit':'probability'},'additional':{'interaction':{'features':['A','B'],'matrix':[[1,0],[0,1]],'matrix_kind':'off_diagonal_only'}}}
  fig,m=render_template('shap_interaction',d);self.assertTrue(m['all_supplied_interactions_zero']);self.assertEqual(m['unit'],'probability')
 def test_existing_qc_import_is_same_style(self):
  import biostyle,qcstyle
  self.assertIs(biostyle.use_style,qcstyle.use_style)
 def test_composite_honors_requested_width_in_svg(self):
  from composite import render_composite
  import xml.etree.ElementTree as ET
  d={'pca_samples':{'pca':[[0,0],[1,1]],'groups':['A','A'],'sample_ids':['s1','s2']}}
  with tempfile.TemporaryDirectory() as t:
   p,m=render_composite('bulk-de-story',d,outdir=t,panel_ids=['pca_samples'],ncols=1,width='onehalf')
   self.assertEqual(m['width_mm'],120);self.assertEqual(ET.parse(p).getroot().get('width'),'120.0mm')
 def test_discrete_checkpoints_do_not_create_continuous_lines(self):
  from native_figures import render_proteintalks_checkpoints
  with tempfile.TemporaryDirectory() as t:
   f=NativeFixture(t,'proteintalks_predict',{'p.npz':('proteome_predictions','temporary fixture content')});root=Path(t)
   np.savez(root/'p.npz',protein_expression=np.array([[[1],[2],[3]]]),case_ids=np.asarray(['case1']),protein_ids=np.asarray(['protein1']),native_internal_ticks=np.asarray([1,2,3]),physical_timepoint_labels_hours=np.asarray([6,24,48]))
   request=json.loads(f.request.read_text());request['parameters']['expression_scale']='FIXTURE_SCALE';dump(f.request,request);rec=json.loads(f.receipt.read_text());rec['request_sha256']=digest(f.request);rec['outputs'][0].update(sha256=digest(root/'p.npz'),bytes=(root/'p.npz').stat().st_size);dump(f.receipt,rec);q=json.loads(f.acceptance.read_text());q.update(request_sha256=digest(f.request),receipt_sha256=digest(f.receipt));dump(f.acceptance,q)
   fig,m=render_proteintalks_checkpoints(f.plan(),['protein1']);self.assertFalse(m['continuous_physical_time_model']);self.assertEqual(m['trained_labels_hours'],[6,24,48]);self.assertFalse(fig.axes[0].lines)

if __name__=='__main__':unittest.main(verbosity=2)
