"""Returned summary/identity/claim audits, no scientific numerical computation or public requests."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bridge'))
import research_quality_ext as quality


class QualityChecks(unittest.TestCase):
    def test_same_title_does_not_merge_preprint_and_published_article(self):
        searches = [{'id':'s', 'source':'fixture', 'exact_query':'public fixture', 'retrieved_at_utc':'fixture',
                     'reported_total':5, 'returned_count':3, 'coverage_state':'bounded_page'}]
        rows = [{'id':'a', 'doi':'10.1234/a', 'title':'Same title', 'search_id':'s', 'publication_type':'preprint'},
                {'id':'b', 'doi':'10.1234/b', 'title':'Same title', 'search_id':'s', 'publication_type':'article'},
                {'id':'c', 'doi':'https://doi.org/10.1234/a', 'title':'Same title', 'search_id':'s', 'publication_type':'preprint'}]
        result = quality.audit_literature_set(rows, searches)
        self.assertEqual(result['exact_identifier_duplicate_groups'], [['a','c']])
        self.assertEqual(result['title_only_review_candidates'], [['a','b','c']])
        searches[0]['coverage_state']='all_reported_records'
        self.assertFalse(quality.audit_literature_set(rows, searches)['summary_consistent'])

    def test_retraction_conflicts_and_unlocated_relations_block(self):
        rows = [{'id':'a','doi':'10.1234/a','pmid':'1','search_id':'s','publication_type':'article'},
                {'id':'b','doi':'10.1234/a','pmid':'2','search_id':'s','publication_type':'article','retracted':True}]
        searches = [{'id':'s','source':'fixture','exact_query':'public','retrieved_at_utc':'fixture',
                     'reported_total':2,'returned_count':2,'coverage_state':'all_reported_records'}]
        result = quality.audit_literature_set(rows, searches, [{'from':'a','to':'b','type':'is_version_of'}])
        codes = {v['code'] for v in result['issues']}
        self.assertTrue({'conflicting_strong_identifiers','declared_retraction_review_required','unlocated_publication_relation'}<=codes)

    def test_isoform_and_version_ambiguity_are_retained(self):
        context = {'species':'synthetic_species','annotation_version':'v1'}
        row = {'id':'a','namespace':'protein_isoform', **context,'source_id':'p','target_id':'x','source_reference':'fixture',
               'source_version':'v1','candidate_coverage_complete':False,'canonical_substituted':True}
        other = {**row,'id':'b','target_id':'y'}
        result = quality.audit_identifier_context([row, other], context)
        self.assertFalse(result['safe_one_to_one_join']); self.assertEqual(len(result['ambiguous_mappings']),1)
        self.assertIn('isoform_identity_not_established', {v['code'] for v in result['issues']})

    def test_public_batch_requires_approval_and_cache_preserves_source_date(self):
        with self.assertRaises(ValueError): quality.resolve_public_identifiers('pdb',['1ABC'])
        quality.PUBLIC_CACHE = quality.BoundedCache()
        with patch('research_ext.resolve_identifier', return_value={'status':'partial','candidate_coverage_complete':False}) as backend:
            first = quality.resolve_public_identifiers('pdb',['1ABC'],approved_public_data=True)
            second = quality.resolve_public_identifiers('pdb',['1ABC'],approved_public_data=True)
        self.assertEqual(backend.call_count,1); self.assertTrue(second['records'][0]['cache_hit'])
        self.assertEqual(first['records'][0]['retrieved_at_utc'], second['records'][0]['retrieved_at_utc'])
        self.assertFalse(second['records'][0]['resolution']['candidate_coverage_complete'])

    def test_missing_outputs_bad_hash_and_old_qc_block_return_acceptance(self):
        context = {'species':'synthetic','model':'fixture','biological_unit':'donor','contrast':'a-b',
                   'method':'fixture','method_version':'1','reference_version':'1','design_sha256':'a'*64}
        binding = quality._digest(context)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'summary.txt'; path.write_text('bounded summary')
            artifact = {'id':'a','role':'input_qc','sha256':'0'*64,'path':str(path),'context_sha256':binding,
                        'source_reference':'server fixture','locator':'line 1'}
            result = quality.audit_returned_analysis('bulk',[artifact],context,{'state':'passed','context_sha256':'wrong'},
                                                    {'state':'completed','exit_code':0,'context_sha256':binding,'receipt_reference':'fixture'})
        codes = {v['code'] for v in result['issues']}
        self.assertTrue({'qc_not_passed_for_exact_context','result_hash_mismatch'}<=codes)
        self.assertIn('differential', result['missing_roles']); self.assertFalse(result['scientific_validity_established'])

    def test_network_and_docking_claims_keep_their_evidence_ceiling(self):
        context = {'interaction_claim':'physical_binding','edge_evidence':'functional_association','score_units':'kcal/mol',
                   'claims_experimental_activity':True}
        artifact = [{'id':'a','role':'poses'}]
        ppi = quality.audit_returned_analysis('ppi',artifact,context,{}, {})
        docking = quality.audit_returned_analysis('docking',artifact,context,{}, {})
        self.assertIn('functional_network_not_physical_binding_proof', {v['code'] for v in ppi['issues']})
        self.assertIn('docking_not_experimental_activity', {v['code'] for v in docking['issues']})

    def test_located_hashes_do_not_establish_direct_causal_support(self):
        context = {'species':'synthetic','model':'fixture','assay':'rna','biological_unit':'donor','contrast':'a-b'}
        source = {'id':'s',**context,'reference':'fixture','version':'1','locator':'page 1 line 2','excerpt':'Located text',
                  'sha256':'a'*64,'evidence_type':'coexpression'}
        claim = {'id':'c','text':'A causes B','source_ids':['s'],'claim_type':'causal','support_label':'direct',
                 'reviewed_negation_and_context':True}
        result = quality.audit_evidence_trace([claim],[source],context)
        self.assertFalse(result['summary_consistent']); self.assertFalse(result['edges'][0]['direct_support_established'])
        self.assertIn('direct_support_label_requires_revision', {v['code'] for v in result['issues']})


if __name__ == '__main__': unittest.main()
