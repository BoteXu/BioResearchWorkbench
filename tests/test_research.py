"""Fixed identity, ambiguity and routing checks, including expected failures."""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
import research_ext as research


class ResearchChecks(unittest.TestCase):
    def test_missing_species_and_variant_assembly_rejected_before_network(self):
        with patch.object(research, '_get_json') as query:
            for params in [('gene_symbol','INS','',''), ('rsid','rs699','homo_sapiens',''),
                           ('uniprot','P01308-1','homo_sapiens',''), ('pdb','../escape','','')]:
                with self.assertRaises(ValueError):
                    research.resolve_identifier(*params)
            query.assert_not_called()

    def test_ambiguous_symbol_preserves_candidates(self):
        def fixture(url, params=None):
            if '/xrefs/' in url:
                return [{'type':'gene','id':'ENSG000001'}, {'type':'gene','id':'ENSG000002'}]
            return {'id':url.rsplit('/',1)[-1], 'object_type':'Gene','species':'homo_sapiens','assembly_name':'GRCh38','version':1}
        with patch.object(research, '_get_json', side_effect=fixture):
            result = research.resolve_identifier('gene_symbol','FIXTURE','homo_sapiens','GRCh38')
        self.assertEqual(result['status'],'ambiguous')
        self.assertEqual(result['candidate_count'],2)

    def test_wrong_species_assembly_and_version_fail_context(self):
        data = {'id':'ENSG000001','object_type':'Gene','species':'mus_musculus','assembly_name':'GRCm39','version':2}
        with patch.object(research,'_get_json',return_value=data):
            result = research.resolve_identifier('ensembl_gene','ENSG000001.1','homo_sapiens','GRCh38')
        self.assertFalse(result['identity_check_pass'])
        self.assertEqual(set(result['issues']),{'species_mismatch','assembly_mismatch','requested_identifier_version_mismatch'})

    def test_transient_symbol_fallback_preserves_partial_coverage(self):
        def fixture(url, params=None):
            if '/xrefs/' in url:
                raise TimeoutError('Synthetic availability failure')
            if '/search' in url:
                return {'results':[{'organism':{'taxonId':9606},'uniProtKBCrossReferences':[
                    {'database':'Ensembl','properties':[{'key':'GeneId','value':'ENSG000001.2'}]}]}]}
            return {'id':'ENSG000001','object_type':'Gene','species':'homo_sapiens','assembly_name':'GRCh38','version':2}
        with patch.object(research,'_get_json',side_effect=fixture):
            result = research.resolve_identifier('gene_symbol','FIXTURE','homo_sapiens','GRCh38')
        self.assertEqual(result['status'],'partial')
        self.assertFalse(result['candidate_coverage_complete'])
        self.assertTrue(result['identity_check_pass'])
        self.assertEqual(result['source_data'][0]['failure_type'],'TimeoutError')

    def test_variant_build_is_never_silently_converted(self):
        data = {'name':'rs699','mappings':[{'assembly_name':'GRCh37','location':'8:1-1','allele_string':'A/G'}]}
        with patch.object(research,'_get_json',return_value=data):
            result = research.resolve_identifier('rsid','rs699','homo_sapiens','GRCh38')
        self.assertIn('requested_assembly_not_returned',result['issues'])
        self.assertFalse(result['identity_check_pass'])

    def test_uniprot_cannot_assert_build_or_accept_wrong_species(self):
        data = {'primaryAccession':'P01308','organism':{'taxonId':10090},'uniProtKBCrossReferences':[
            {'database':'Ensembl','id':'ENST000001','properties':[{'key':'GeneId','value':'ENSG000001'}]}]}
        with patch.object(research,'_get_json',return_value=data):
            result = research.resolve_identifier('uniprot','P01308','homo_sapiens','GRCh38')
        self.assertFalse(result['identity_check_pass'])
        self.assertIn('species_mismatch',result['issues'])
        self.assertIn('assembly_not_verified_for_uniprot_cross_references',result['issues'])

    def test_source_identity_mismatch_rejected(self):
        with patch.object(research,'_get_json',return_value={'rcsb_id':'0BAD'}):
            with self.assertRaises(ValueError):
                research.resolve_identifier('pdb','4HHB')

    def test_mapping_conflicts_duplicates_and_versions_block_join(self):
        row = {'source_namespace':'gene_symbol','source_id':'FIXTURE','target_namespace':'ensembl_gene',
               'target_id':'ENSG000001','species':'homo_sapiens','assembly':'GRCh38','evidence_reference':'synthetic fixture'}
        result = research.audit_identifier_mapping([row],'homo_sapiens','GRCh38')
        self.assertTrue(result['safe_one_to_one_join'])
        self.assertFalse(result['source_truth_verified'])
        result = research.audit_identifier_mapping([row,row,{**row,'target_id':'ENSG000002.2'}],'homo_sapiens','GRCh38')
        self.assertFalse(result['safe_one_to_one_join'])
        self.assertEqual(len(result['one_to_many']),1)
        self.assertIn('duplicate_mapping',result['row_issues'][0]['issues'])
        result = research.audit_identifier_mapping([{**row,'source_id':'OTHER'},row],'homo_sapiens','GRCh38')
        self.assertEqual(len(result['many_to_one']),1)
        result = research.audit_identifier_mapping([{**row,'species':'mus_musculus','evidence_reference':''}],'homo_sapiens','GRCh38')
        self.assertFalse(result['safe_one_to_one_join'])

    def test_routing_requires_authorization_and_redirects_heavy_work(self):
        def catalog(category,search,limit):
            return {'tools':[{'name':search,'dependency_check':{},'runtime_state':'untested'}]}
        fake = types.ModuleType('bridge')
        fake.tool_catalog = catalog
        with patch.dict(sys.modules,{'bridge':fake}):
            private = research.select_tools('literature',sensitive_data=True)
            heavy = research.select_tools('small_omics',large_computation=True)
        self.assertFalse(any(r['eligible_to_attempt'] for r in private['recommendations']))
        self.assertEqual(heavy['selected_intent'],'server_task')
        self.assertFalse(heavy['submitted'])
        self.assertFalse(any(r['runtime_success_established'] for r in heavy['recommendations']))


if __name__ == '__main__':
    unittest.main()
