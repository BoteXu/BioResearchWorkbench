"""Bounded synthetic contract checks, not local scientific analysis or omics backend acceptance."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bridge')); sys.path.insert(0, str(ROOT))
import omics_workflows_ext as omics
import generate_omics_guide
import extensions
import generate_catalog
import upgrade


def fixture(workflow='bulk_rna', selected=None):
    catalog, _, profile = omics._selected(workflow)
    context = {'species': 'fixture_species', 'model': 'synthetic_fixture', 'assay': 'synthetic_assay', 'reference': 'fixture_reference',
               'assembly': 'fixture_build', 'annotation_version': 'fixture_annotation_v1',
               'reference_version': 'fixture_v1', 'feature_namespace': 'fixture_features'}
    design = {'estimand': 'fixture_condition_difference', 'biological_unit': 'donor', 'unit_type': 'donor',
              'contrast': 'B_vs_A', 'missingness_plan': 'fixture complete case', 'inference_mode': 'inferential',
              'batch_confounded': False, 'repeated_measures': False, 'covariates': [],
              'units': [{'id': 'unit_' + str(i), 'group': 'A' if i < 2 else 'B'} for i in range(4)],
              'capabilities': {}}
    selected = selected or []
    for e in selected:
        for prerequisite in catalog['extensions'][e]['prerequisites']:
            design['capabilities'][prerequisite] = {'available': True, 'source_location': 'synthetic_locator', 'source_sha256': 'a' * 64}
    inputs = [{'id': 'input_fixture', 'kind': profile['input_kinds'][0], 'source_location': 'synthetic_locator', 'sha256': 'a' * 64}]
    return omics.plan_omics_workflow(workflow, context, design, inputs, selected)


def evidence(plan):
    return {**plan['binding'], 'plan_sha256': plan['plan_sha256'], 'source_location': 'synthetic_locator',
            'source_sha256': 'a' * 64, 'reviewed_by_host': True}


def ready(plan):
    binding = evidence(plan)
    checks = [{**binding, 'id': q['id'], 'status': 'passed'} for q in plan['required_qc']]
    stats = {**binding, 'status': 'reviewed', 'estimand': plan['design']['estimand'], 'biological_unit': plan['design']['biological_unit']}
    backend = {**binding, 'status': 'runtime_verified', 'route': 'existing_server', 'method_versions': {'fixture_method': '1.0'}}
    return checks, stats, backend


class OmicsContracts(unittest.TestCase):
    def test_every_workflow_and_compatible_extension_has_resolved_contract(self):
        catalog, _ = omics._catalog()
        self.assertEqual(len(catalog['workflows']), 28)
        self.assertEqual(len(catalog['extensions']), 21)
        self.assertEqual(sum(len(w['extensions']) for w in catalog['workflows']), 108)
        for w in catalog['workflows']:
            for e in [None, *w['extensions']]:
                plan = fixture(w['id'], [e] if e else [])
                checks, stats, backend = ready(plan)
                result = omics.audit_omics_readiness(plan, checks, stats, backend)
                self.assertTrue(result['summary_consistent'], (w['id'], e, result['issues']))
                self.assertFalse(result['analysis_authorized'])
                self.assertFalse(result['scientific_validity_established'])
        summary = omics.inspect_omics_workflows(limit=1)
        self.assertEqual(summary['returned'], 1); self.assertEqual(summary['matched'], 28)
        with self.assertRaises(ValueError): omics.inspect_omics_workflows(workflow='invented')
        with self.assertRaises(ValueError): omics.inspect_omics_workflows(limit=True)

    def test_processed_expression_cannot_pass_as_bulk_raw_counts(self):
        plan = fixture(); inputs = copy.deepcopy(plan['input_manifest']); inputs[0]['kind'] = 'normalized_expression'
        bad = omics.plan_omics_workflow('bulk_rna', plan['context'], plan['design'], inputs)
        self.assertFalse(bad['plan_contract_consistent'])
        self.assertIn('incompatible_input_scale_or_kind', [v['code'] for v in bad['issues']])

    def test_extension_conditions_are_explicit_and_never_silently_added(self):
        plan = fixture('scrna')
        self.assertEqual(plan['requested_extensions'], [])
        bad = omics.plan_omics_workflow('scrna', plan['context'], plan['design'], plan['input_manifest'], ['velocity'])
        self.assertFalse(bad['plan_contract_consistent'])
        self.assertEqual(bad['extension_routes'][0]['state'], 'blocked')
        with self.assertRaises(ValueError): fixture('bulk_rna', ['velocity'])
        with self.assertRaises(ValueError): fixture('bulk_rna', ['pathway', 'pathway'])

    def test_missing_qc_unknown_sources_and_statistical_consultation_block(self):
        plan = fixture(); checks, stats, backend = ready(plan)
        self.assertFalse(omics.audit_omics_readiness(plan, checks[1:], stats, backend)['summary_consistent'])
        checks[0]['status'] = 'unknown'
        self.assertFalse(omics.audit_omics_readiness(plan, checks, stats, backend)['summary_consistent'])
        checks[0]['status'] = 'passed'; checks[0]['reviewed_by_host'] = False
        self.assertFalse(omics.audit_omics_readiness(plan, checks, stats, backend)['summary_consistent'])
        checks, stats, backend = ready(plan)
        self.assertFalse(omics.audit_omics_readiness(plan, checks, None, backend)['summary_consistent'])
        stats['biological_unit'] = 'cell'
        self.assertFalse(omics.audit_omics_readiness(plan, checks, stats, backend)['summary_consistent'])
        checks[0]['status'] = 'not_applicable'
        with self.assertRaises(ValueError): omics.audit_omics_readiness(plan, checks, stats, backend)

    def test_numeric_qc_checks_definitions_units_and_threshold_contradictions(self):
        plan = fixture('bulk_atac'); checks, stats, backend = ready(plan)
        checks[0]['measurements'] = [{'id': 'metric_fixture', 'definition': 'synthetic fraction', 'unit': 'fraction',
                                     'observation_scope': 'fixture_sample', 'threshold_basis': 'synthetic acceptance criterion',
                                     'value': 0.1, 'operator': 'ge', 'bound': 0.2}]
        self.assertFalse(omics.audit_omics_readiness(plan, checks, stats, backend)['summary_consistent'])
        for value in [True, '0.3', float('nan')]:
            checks[0]['measurements'][0]['value'] = value
            with self.assertRaises(ValueError): omics.audit_omics_readiness(plan, checks, stats, backend)
        checks[0]['measurements'][0]['value'] = 0.3
        self.assertTrue(omics.audit_omics_readiness(plan, checks, stats, backend)['summary_consistent'])

    def test_changed_context_plan_catalog_or_qc_binding_cannot_reuse_acceptance(self):
        plan = fixture(); checks, stats, backend = ready(plan)
        bad = copy.deepcopy(plan); bad['context']['reference_version'] = 'new'
        with self.assertRaises(ValueError): omics.audit_omics_readiness(bad, checks, stats, backend)
        bad = copy.deepcopy(plan); bad['required_qc'] = []
        with self.assertRaises(ValueError): omics.audit_omics_readiness(bad, checks, stats, backend)
        checks[0]['design_sha256'] = 'b' * 64
        self.assertFalse(omics.audit_omics_readiness(plan, checks, stats, backend)['summary_consistent'])
        with patch.object(omics, '_catalog', return_value=({**omics._catalog()[0], 'catalog_version': 'changed'}, 'b' * 64)):
            with self.assertRaises(ValueError): omics.audit_omics_readiness(plan, [], stats, backend)

    def test_design_independent_units_confounded_repeated_and_descriptive_modes(self):
        plan = fixture(); design = copy.deepcopy(plan['design']); design['unit_type'] = 'cell'
        with self.assertRaises(ValueError): omics.plan_omics_workflow('scrna', plan['context'], design, plan['input_manifest'])
        design = copy.deepcopy(plan['design']); design['batch_confounded'] = True
        self.assertFalse(omics.plan_omics_workflow('bulk_rna', plan['context'], design, plan['input_manifest'])['plan_contract_consistent'])
        design = copy.deepcopy(plan['design']); design['repeated_measures'] = True
        self.assertFalse(omics.plan_omics_workflow('bulk_rna', plan['context'], design, plan['input_manifest'])['plan_contract_consistent'])
        design = copy.deepcopy(plan['design']); design['units'] = design['units'][:1]
        self.assertFalse(omics.plan_omics_workflow('bulk_rna', plan['context'], design, plan['input_manifest'])['plan_contract_consistent'])
        design['inference_mode'] = 'descriptive'
        descriptive = omics.plan_omics_workflow('bulk_rna', plan['context'], design, plan['input_manifest'])
        checks, _, backend = ready(descriptive)
        self.assertTrue(omics.audit_omics_readiness(descriptive, checks, None, backend)['summary_consistent'])
        self.assertNotIn('differential', descriptive['result_roles']); self.assertIn('descriptive_results', descriptive['result_roles'])

    def test_backend_route_requires_real_server_declaration_and_fixed_versions(self):
        plan = fixture(); checks, stats, backend = ready(plan)
        for route in ['local', 'prepared_only']:
            backend['route'] = route
            self.assertFalse(omics.audit_omics_readiness(plan, checks, stats, backend)['summary_consistent'])
        backend['route'] = 'existing_server'; backend['method_versions'] = {'fixture': 'latest'}
        self.assertFalse(omics.audit_omics_readiness(plan, checks, stats, backend)['summary_consistent'])

    def test_returned_bundle_requires_extensions_completion_and_exact_lineage(self):
        plan = fixture('bulk_rna', ['pathway']); checks, stats, backend = ready(plan)
        binding = evidence(plan)
        manifest = [{**binding, 'id': r, 'role': r, 'sha256': 'a' * 64, 'bytes': 100} for r in plan['result_roles']]
        receipt = {**binding, 'state': 'COMPLETED', 'exit_code': 0, 'scheduler_receipt_id': 'synthetic_scheduler', 'runner_receipt_id': 'synthetic_runner'}
        result = omics.audit_omics_result_bundle(plan, manifest, receipt, checks, stats, backend)
        self.assertTrue(result['summary_consistent']); self.assertFalse(result['local_file_hashes_verified']); self.assertFalse(result['actual_server_process_observed'])
        self.assertFalse(omics.audit_omics_result_bundle(plan, manifest[:-1], receipt, checks, stats, backend)['summary_consistent'])
        receipt['state'] = 'UNKNOWN'
        result = omics.audit_omics_result_bundle(plan, manifest, receipt, checks, stats, backend)
        self.assertFalse(result['summary_consistent']); self.assertFalse(result['automatic_retry'])
        receipt['state'] = 'COMPLETED'; receipt['exit_code'] = False
        self.assertFalse(omics.audit_omics_result_bundle(plan, manifest, receipt, checks, stats, backend)['summary_consistent'])
        receipt['exit_code'] = 0; manifest[0]['context_sha256'] = 'b' * 64
        self.assertFalse(omics.audit_omics_result_bundle(plan, manifest, receipt, checks, stats, backend)['summary_consistent'])

    def test_portable_catalog_guide_distribution_and_lazy_core_registration(self):
        self.assertEqual((ROOT / 'OMICS_WORKFLOWS.md').read_text(encoding='utf8'), generate_omics_guide.generate())
        generated, _ = generate_catalog.generate()
        tools = [t for t in generated['tools'] if t['category'] == 'omics_workflows']
        self.assertEqual(len(tools), 4)
        self.assertEqual(len(tools[1]['input_schema']['properties']['workflow']['enum']), 28)
        self.assertEqual(set(extensions.EXPORTS['omics_workflows'][1]), {t['name'] for t in tools})
        _, mapping = upgrade._mapping(ROOT)
        self.assertIn('.local/omics_workflows.json', mapping)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            shutil.copyfile(ROOT / 'bridge/omics_workflows_ext.py', folder / 'omics_workflows_ext.py')
            shutil.copyfile(ROOT / 'omics_workflows.json', folder / 'omics_workflows.json')
            spec = importlib.util.spec_from_file_location('isolated_omics_fixture', folder / 'omics_workflows_ext.py')
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            self.assertEqual(module.inspect_omics_workflows()['total_workflows'], 28)
            with self.assertRaises(ValueError): module.plan_omics_workflow('bulk_rna', {}, {}, [])


if __name__ == '__main__':
    unittest.main()
