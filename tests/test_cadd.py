"""Synthetic scientific-contract and refusal cases; no molecular engine is executed."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bridge'))
import cadd_ext as c

H = 'a'*64
J = 'b'*64
K = 'c'*64
CONTEXT = {'species':'synthetic', 'system':'synthetic two-chain complex', 'purpose':'engineering validation', 'source_version':'fixture-v1'}


def protocol():
    return dict(engine='gromacs', mode='md', engine_version='synthetic', force_field='declared', solvent_model='declared',
                parameterization_source='fixture', protonation_basis='fixture', equilibration_acceptance='explicit observables',
                convergence_observables='block and independent-run comparison', resource_budget='server resource plan',
                system_sha256=H, topology_sha256=H, duration_unit='ps', timestep_unit='ps', temperature_unit='K', temperature_K=300,
                independent_starts=2, stages=[{'name':'minimization','steps':100}, {'name':'equilibration','steps':1000,'dt_ps':0.002,'duration_ps':2},
                                             {'name':'production','steps':5000,'dt_ps':0.002,'duration_ps':10}])


def domain():
    return dict(engine='fixture', version='v1', scoring='declared', units='arbitrary', search_mode='explicit', direction='lower',
                receptor_sha256=H, preparation_sha256=H, site_sha256=H)


def afrecord():
    return dict(id='one', target_id='target', seed=1, sample=0, structure_sha256=H, summary_sha256=H, input_sha256=H,
                binding_verified=True, chain_ids=['B','A','C'], summary={'iptm':0.6,'ptm':0.7,'ranking_score':0.62, 'has_clash':False,
                'chain_pair_iptm':[[0.7,0.8,0.2],[0.8,0.7,0.3],[0.2,0.3,0.7]], 'chain_pair_pae_min':[[0,2,9],[3,0,8],[9,8,0]]})


def energy(sid='one', estimate=-20, trajectory=H):
    return dict(id=sid, ligand_id='ligand', independent_start=sid, method='MMGBSA', units='kcal/mol', protocol_sha256=H,
                trajectory_sha256=trajectory, topology_sha256=H, estimate=estimate, frames=100, effective_samples=10,
                solvent_parameters='explicit', entropy_method='omitted', frame_selection='declared', receptor_ligand_mapping='declared',
                equilibration_removed=True, receipt_verified=True, state='completed', exit_code=0)


class CaddTests(unittest.TestCase):
    def setUp(self):
        self.patcher=patch.object(c, 'artifact', side_effect=lambda kind, data: {'success':True, **data})
        self.patcher.start(); self.addCleanup(self.patcher.stop)

    def codes(self, result): return {x['code'] for x in result['issues']}

    def test_all_routes_are_preparation_only(self):
        for task in c.ROUTES:
            r=c.guide_cadd_workflow(task, CONTEXT)
            self.assertEqual(r['compute_placement'],'server')
            self.assertEqual(r['scientific_validity'],'not_established')
        with self.assertRaises(ValueError): c.guide_cadd_workflow('arbitrary_command',CONTEXT)

    def test_protocol_times_and_units(self):
        r=c.audit_simulation_protocol(protocol(),CONTEXT)
        self.assertTrue(r['qc_gate_pass']); self.assertEqual(r['stages'][-1]['duration_ps'],10)
        p=protocol(); p['duration_unit']='ns'
        with self.assertRaises(ValueError): c.audit_simulation_protocol(p,CONTEXT)

    def test_protocol_mismatched_time_and_stage_order(self):
        p=protocol(); p['stages'][2]['duration_ps']=1000; p['stages'].reverse()
        codes=self.codes(c.audit_simulation_protocol(p,CONTEXT))
        self.assertIn('duration_steps_mismatch',codes); self.assertIn('stage_order',codes)

    def test_protocol_unknown_scientific_choices_block(self):
        p=protocol(); del p['force_field']; p['stages'][2].update(dt_ps=0.004,duration_ps=20)
        r=c.audit_simulation_protocol(p,CONTEXT)
        self.assertFalse(r['qc_gate_pass']); self.assertIn('missing_force_field',self.codes(r))
        self.assertIn('large_timestep_requires_validation',self.codes(r))

    def test_replica_resource_distribution_is_valid(self):
        p=protocol(); p.update(mode='tremd',temperatures_K=[300,350],mpi_ranks=3,pilot_receipt_verified=True,exchange_interval_steps=100)
        self.assertIn('insufficient_replica_resources',self.codes(c.audit_simulation_protocol(p,CONTEXT)))

    def test_rest2_has_real_capability_and_equal_bath_gates(self):
        p=protocol(); p.update(mode='rest2',temperatures_K=[300,400],mpi_ranks=2,pilot_receipt_verified=True,exchange_interval_steps=100,
                              reference_temperature_K=300,thermostat_temperatures_K=[300,300],scales=[1,0.75])
        for key in ['hot_region_reviewed','scaled_topologies_verified','hrex_verified','plumed_verified','capability_receipt_verified']: p[key]=True
        self.assertTrue(c.audit_simulation_protocol(p,CONTEXT)['qc_gate_pass'])
        p['thermostat_temperatures_K']=[300,400]; p['hrex_verified']=False
        codes=self.codes(c.audit_simulation_protocol(p,CONTEXT))
        self.assertIn('rest2_scaling_or_thermostat_mismatch',codes); self.assertIn('missing_hrex_verified',codes)

    def segments(self):
        first=dict(id='one',walker='w0',system_sha256=H,topology_sha256=H,protocol_sha256=H,output_checkpoint_sha256=J,
                   receipt_sha256=H,start_step=0,end_step=100,dt_ps=0.002,engine_version='fixture',state='completed',exit_code=0,receipt_verified=True)
        second={**first,'id':'two','start_step':100,'end_step':200,'input_checkpoint_sha256':J,'output_checkpoint_sha256':K}
        return [first,second]

    def test_restart_continuity(self):
        r=c.audit_restart_manifest(self.segments(),CONTEXT)
        self.assertTrue(r['qc_gate_pass']); self.assertEqual(r['walkers'][0]['end_step'],200)

    def test_restart_gap_wrong_hash_and_unknown_completion(self):
        s=self.segments(); s[1].update(start_step=101,input_checkpoint_sha256=H,state='unknown')
        codes=self.codes(c.audit_restart_manifest(s,CONTEXT))
        self.assertTrue({'gap_or_overlap','checkpoint_lineage_mismatch','segment_not_verified_complete'}<=codes)

    def test_restart_protocol_change_blocks(self):
        s=self.segments(); s[1]['protocol_sha256']=J
        self.assertIn('restart_compatibility_changed',self.codes(c.audit_restart_manifest(s,CONTEXT)))

    def exchange(self, visits=None):
        return c.audit_replica_exchange([300,350],[{'state_a':0,'state_b':1,'attempted':10,'accepted':4}],
            visits or [{'step':0,'walker_states':[0,1]},{'step':100,'walker_states':[1,0]},{'step':200,'walker_states':[0,1]},{'step':300,'walker_states':[1,0]}],CONTEXT)

    def test_exchange_observed_trips_do_not_establish_convergence(self):
        r=self.exchange(); self.assertEqual(r['pair_counters'][0]['acceptance'],0.4)
        self.assertEqual([x['observed_low_high_low_round_trips'] for x in r['walkers']],[1,1])
        self.assertEqual(r['scientific_validity'],'not_established')

    def test_exchange_invalid_counts_and_permutations_refused(self):
        with self.assertRaises(ValueError): self.exchange([{'step':0,'walker_states':[0,0]}])
        with self.assertRaises(ValueError): c.audit_replica_exchange([300,350],[{'state_a':0,'state_b':1,'attempted':1,'accepted':2}],[{'step':0,'walker_states':[0,1]}],CONTEXT)

    def test_exchange_zero_acceptance_blocks(self):
        r=c.audit_replica_exchange([300,350],[{'state_a':0,'state_b':1,'attempted':0,'accepted':0}],[{'step':0,'walker_states':[0,1]}],CONTEXT)
        self.assertFalse(r['qc_gate_pass']); self.assertIsNone(r['pair_counters'][0]['acceptance'])

    def campaign(self):
        e=[{'id':name,'parent_id':name,'role':role,'ligand_sha256':H} for name,role in [('one','candidate'),('two','reference'),('three','negative_control')]]
        r=[{'id':x['id'],'state':'completed','exit_code':0,'ligand_sha256':H,'score_domain':domain(),'pose_qc_pass':True,'pose_sha256':H,'score':value} for x,value in zip(e,[-10,-8,-4])]
        return e,r

    def test_campaign_exact_domain_ranking(self):
        e,r=self.campaign(); result=c.audit_docking_campaign(e,r,domain(),CONTEXT)
        self.assertTrue(result['qc_gate_pass']); self.assertEqual([x['score'] for x in result['eligible']],[-10,-8,-4])

    def test_campaign_failures_missing_and_mixed_domain_visible(self):
        e,r=self.campaign(); r.pop(); r[0]['score_domain']={**domain(),'version':'other'}; r[1]['state']='failed'
        result=c.audit_docking_campaign(e,r,domain(),CONTEXT)
        self.assertEqual(result['eligible'],[]); self.assertEqual(len(result['excluded']),3)
        self.assertTrue({'missing_result','incomparable_score_domain','execution_failed_or_unknown'}<=self.codes(result))

    def test_campaign_all_missing_is_reported(self):
        e,_=self.campaign(); r=c.audit_docking_campaign(e,[],domain(),CONTEXT)
        self.assertEqual(len(r['excluded']),3); self.assertFalse(r['qc_gate_pass'])

    def test_campaign_nonfinite_and_duplicate_refused(self):
        e,r=self.campaign(); r[0]['score']=float('nan')
        with self.assertRaises(ValueError): c.audit_docking_campaign(e,r,domain(),CONTEXT)
        e,r=self.campaign(); r.append(r[0])
        with self.assertRaises(ValueError): c.audit_docking_campaign(e,r,domain(),CONTEXT)

    def restraint(self, present=True):
        mapping=[dict(source_chain='A',source_residue='10A',structure_chain='B',structure_residue='22A',numbering_scheme='author_with_insertion',source_version='fixture-v1',present=present)]
        restraints=[dict(id='one',evidence='synthetic located evidence',kind='active',endpoints=[{'source_chain':'A','source_residue':'10A'}])]
        return mapping,restraints

    def test_restraint_insertion_code_preserved(self):
        m,r=self.restraint(); self.assertTrue(c.audit_restraint_mapping(m,r,CONTEXT)['qc_gate_pass'])
        r[0]['endpoints'][0]['source_residue']='10'
        self.assertIn('unmapped_endpoint',self.codes(c.audit_restraint_mapping(m,r,CONTEXT)))

    def test_restraint_missing_and_stale_mapping_block(self):
        m,r=self.restraint(False); self.assertIn('missing_structure_residue',self.codes(c.audit_restraint_mapping(m,r,CONTEXT)))
        m,r=self.restraint(); m[0]['source_version']='old'
        self.assertIn('mapping_source_version_mismatch',self.codes(c.audit_restraint_mapping(m,r,CONTEXT)))

    def test_af3_selected_chain_order_and_direction(self):
        r=c.audit_af3_records([afrecord()],['A','B'],CONTEXT)
        self.assertTrue(r['qc_gate_pass']); self.assertEqual(r['records'][0]['chain_pair_pae_min'],{'forward':3,'reverse':2})

    def test_af3_unsupported_binding_and_chain_order_block(self):
        row=afrecord(); row['binding_verified']=False; row['summary']['chain_ids']=['A','B','C']
        codes=self.codes(c.audit_af3_records([row],['A','B'],CONTEXT))
        self.assertTrue({'sample_file_binding_required','summary_chain_order_mismatch'}<=codes)

    def test_af3_matrix_atom_token_confusion_refused(self):
        row=afrecord(); row['summary']['chain_pair_iptm']=[[0.8]*4]*4
        with self.assertRaises(ValueError): c.audit_af3_records([row],['A','B'],CONTEXT)
        with self.assertRaises(ValueError): c.audit_af3_records([afrecord(),afrecord()],['A','B'],CONTEXT)

    def test_energy_run_uncertainty_not_frame_uncertainty(self):
        r=c.audit_mmgbsa_summary([energy(),energy('two',-24,J)],CONTEXT)
        self.assertEqual(r['summaries'][0]['mean_run_estimate'],-22)
        self.assertAlmostEqual(r['summaries'][0]['sd_between_runs'],2**0.5*2)
        self.assertEqual(r['summaries'][0]['independent_starts'],2)

    def test_energy_reused_trajectory_and_failed_run_excluded(self):
        a=energy(); b=energy('two',-100); b['state']='failed'
        r=c.audit_mmgbsa_summary([a,b],CONTEXT)
        self.assertEqual(r['excluded'],['two']); self.assertEqual(r['summaries'][0]['mean_run_estimate'],-20)
        self.assertIn('reused_trajectory_not_independent',self.codes(r))

    def test_energy_mixed_units_and_protocols_stay_separate(self):
        b=energy('two',-80,J); b['units']='kJ/mol'; b['protocol_sha256']=J
        r=c.audit_mmgbsa_summary([energy(),b],CONTEXT)
        self.assertEqual(len(r['summaries']),2); self.assertIn('incomparable_protocols_kept_separate',self.codes(r))

    def test_energy_topology_change_is_not_pooled(self):
        b=energy('two',-24,J); b['topology_sha256']=J
        r=c.audit_mmgbsa_summary([energy(),b],CONTEXT)
        self.assertEqual(len(r['summaries']),2)

    def test_input_budgets_and_boolean_numbers_refused(self):
        with self.assertRaises(ValueError): c._bounded({'too_large':'x'*2_000_001})
        with self.assertRaises(ValueError): c._num(True)
        with self.assertRaises(ValueError): c._hash('fake')
        with self.assertRaises(ValueError): c.guide_cadd_workflow('md',{})


if __name__ == '__main__': unittest.main()
