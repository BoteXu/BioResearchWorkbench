"""Actual isolated code/notebook/workflow/DICOM adapters; public synthetic fixtures only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge'))
import academic_common as common
import code_execution_ext as execution


def call(argv,cwd,expected=0,env=None):
    result=subprocess.run(argv,cwd=cwd,capture_output=True,text=True,timeout=180,env=env)
    if result.returncode!=expected:
        print(result.stdout[-3000:]);print(result.stderr[-3000:]);raise AssertionError('Runtime adapter failed')


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp).resolve()
        import nbformat
        nb=nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell('value = 3'),nbformat.v4.new_code_cell('assert value == 3')])
        nbformat.write(nb,root/'notebook.ipynb');before=hashlib.sha256((root/'notebook.ipynb').read_bytes()).hexdigest()
        cfg={'mode':'notebook','files':['notebook.ipynb'],'output_directory':'notebook_ok','reviewed_code':True,'timeout_seconds':30}
        (root/'code.json').write_text(json.dumps(cfg));call([sys.executable,str(ROOT/'bridge'/'code_runner.py'),'code.json'],root)
        out=nbformat.read(root/'notebook_ok'/'executed.ipynb',as_version=4);assert [c.execution_count for c in out.cells]==[1,2]
        assert hashlib.sha256((root/'notebook.ipynb').read_bytes()).hexdigest()==before
        nb.cells.append(nbformat.v4.new_code_cell('raise ValueError("fixture refusal")'));nbformat.write(nb,root/'notebook.ipynb')
        cfg['output_directory']='notebook_failed';(root/'code.json').write_text(json.dumps(cfg));call([sys.executable,str(ROOT/'bridge'/'code_runner.py'),'code.json'],root,1)
        assert (root/'notebook_failed'/'executed.ipynb').is_file()
        # Actual R parser check never evaluates source.
        (root/'syntax.R').write_text('stop("must not be executed")\n')
        cfg={'mode':'r_syntax','files':['syntax.R'],'output_directory':'rsyntax','timeout_seconds':30};(root/'code.json').write_text(json.dumps(cfg));call([sys.executable,str(ROOT/'bridge'/'code_runner.py'),'code.json'],root)
        # Synthetic DICOM metadata only, never a private image.
        from pydicom.dataset import FileDataset,FileMetaDataset
        from pydicom.uid import ExplicitVRLittleEndian,generate_uid
        fm=FileMetaDataset();fm.TransferSyntaxUID=ExplicitVRLittleEndian;fm.MediaStorageSOPClassUID=generate_uid();fm.MediaStorageSOPInstanceUID=generate_uid()
        ds=FileDataset(str(root/'fixture.dcm'),{},file_meta=fm,preamble=b'\0'*128);ds.PatientID='synthetic';ds.Modality='CT';ds.Rows=2;ds.Columns=2;ds.save_as(root/'fixture.dcm',enforce_file_format=True)
        cfg={'mode':'dicom_metadata','files':['fixture.dcm'],'output_directory':'dicom','timeout_seconds':30};(root/'code.json').write_text(json.dumps(cfg));call([sys.executable,str(ROOT/'bridge'/'code_runner.py'),'code.json'],root)
        meta=json.loads((root/'dicom'/'metadata.json').read_text());assert meta['records'][0]['rows']==2
        # Execute generated workflow engines on the same fixed QC -> analysis design.
        for engine in ('snakemake','nextflow'):
            folder=root/engine;folder.mkdir()
            (folder/'fixture.py').write_text('import json,sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text(json.dumps({"gate_pass":True,"value":7}))\n')
            resources={'cpus':1,'memory_mb':256,'wall_minutes':1}
            stages=[{'id':'qc','kind':'qc','argv':['python3','fixture.py','qc.json'],'inputs':['fixture.py'],'outputs':['qc.json'],'qc_gate_output':'qc.json','depends_on':[],'resources':resources},
                    {'id':'analysis','kind':'analysis','argv':['python3','fixture.py','analysis.json'],'inputs':['fixture.py','qc.json'],'outputs':['analysis.json'],'depends_on':['qc'],'resources':resources}]
            with patch.object(common,'HERE',root):r=execution.prepare_code_workflow(stages,engine,True)
            for name in ('workflow.json','workflow_stage.py','Snakefile' if engine=='snakemake' else 'main.nf'):shutil.copyfile(Path(r['output_directory'])/name,folder/name)
            command=['snakemake','--cores','1','--snakefile','Snakefile'] if engine=='snakemake' else ['nextflow','run','main.nf','-ansi-log','false']
            call(command,folder);assert json.loads((folder/'analysis.json').read_text())['value']==7
            receipt=json.loads((folder/'.receipts'/'analysis.json').read_text());assert receipt['state']=='succeeded'
        print('ACTUAL_NOTEBOOK_R_PARSE_DICOM_AND_TWO_WORKFLOWS_PASS')


if __name__=='__main__':main()
