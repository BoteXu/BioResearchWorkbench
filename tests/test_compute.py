"""Refusal gates and persistent-interface contracts without scientific dependencies."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
import compute_policy
import transcriptomics_ext as tx
import molecular_ext as mx
import software_ext as sw
import systems_ext as sx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import client_config


class ComputeGates(unittest.TestCase):
    def test_two_editions_have_distinct_client_names(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);python=root/'.venv_tools'/('Scripts/python.exe' if os.name=='nt' else 'bin/python');server=root/'.local'/'mcp_server.py'
            python.parent.mkdir(parents=True);server.parent.mkdir(parents=True);python.touch();server.touch()
            data=client_config.generate(root,root/'configs',server_name='biomni-local')
            self.assertIn('biomni-local',json.loads(data['portable.mcp.json'])['mcpServers'])
            self.assertIn('[mcp_servers.biomni-local]',data['codex.config.toml'])
            with self.assertRaises(ValueError): client_config.generate(root,root/'invalid',server_name='invalid.name')
    def test_server_edition_refuses_formal_local_execution(self):
        with patch.dict(os.environ,{'BIOMNI_COMPUTE_EDITION':'server'}):
            with self.assertRaises(ValueError): compute_policy.require_local()
            with self.assertRaises(ValueError): mx.molecular_descriptors(['CCO'])
            with self.assertRaises(ValueError): tx.run_bulk_rnaseq('absent','absent','condition','unit','case','control',{})

    def test_matrix_duplicates_fractional_and_nonfinite_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'matrix.csv'
            for text in ['gene,a,a\ng,1,2\n','gene,a\ng,1\ng,2\n','gene,a\ng,0.5\n','gene,a\ng,nan\n']:
                path.write_text(text)
                with self.assertRaises(ValueError): tx._read(path,True,True)

    def test_native_dataframe_blank_index_header_is_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'matrix.csv';path.write_text(',sample\ngene,1\n')
            header,rows=tx._read(path,True,True)
            self.assertEqual(rows,[['gene',1.]])

    def test_large_resource_estimate_routes_to_server(self):
        memory=SimpleNamespace(available=1000000000)
        with patch.dict(sys.modules,{'psutil':SimpleNamespace(virtual_memory=lambda:memory)}):
            self.assertFalse(tx.inspect_local_compute(50000,10000,'single_cell')['local_gate_pass'])
            self.assertTrue(tx.inspect_local_compute(1000,12)['local_gate_pass'])

    def test_public_ppi_query_requires_specific_authorization(self):
        with self.assertRaises(ValueError): sx.query_string_network(['GENE_A','GENE_B'],9606)

    def test_docking_score_preserves_pose_bounds(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'poses.pdbqt';path.write_text('REMARK VINA RESULT: -6.5 0.0 0.0\nREMARK VINA RESULT: -5.2 1.2 2.3\n')
            result=mx.summarize_vina_poses(str(path))
            self.assertEqual(result['best_affinity_kcal_mol'],-6.5)
            self.assertEqual(result['poses'][1]['rmsd_upper_bound_angstrom'],2.3)

    def test_software_registration_persists_without_generic_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);binary=root/'Rscript';binary.write_text('synthetic fixture')
            with patch.object(sw,'REGISTRY',root/'registry.json'),patch.object(sw.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='synthetic version',stderr='')) as run:
                result=sw.register_local_software('rscript',str(binary))
                self.assertTrue(result['version_probe_pass'])
                self.assertEqual(run.call_args.args[0],[str(binary.resolve()),'--version'])
                self.assertEqual(sw.resolve('rscript'),str(binary.resolve()))
                with self.assertRaises(ValueError): sw.register_local_software('arbitrary_shell',str(binary))

    def test_invalid_compute_edition_is_not_silently_accepted(self):
        with patch.dict(os.environ,{'BIOMNI_COMPUTE_EDITION':'invalid'}):
            with self.assertRaises(ValueError): compute_policy.edition()


if __name__=='__main__': unittest.main()
