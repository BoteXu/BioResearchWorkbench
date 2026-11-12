"""Fixed child launcher for source-reviewed native inference; no downloading."""
import sys,os,json,random,runpy,socket,importlib.metadata
from pathlib import Path

def main():
    job=json.loads(Path(sys.argv[1]).read_text(encoding='utf8'))
    scripts={'diffdock_pose':'inference.py','diffsbdd_generate':'generate_ligands.py','rfdiffusion_backbone':'scripts/run_inference.py'}
    if job['mode'] not in scripts or job['script']!=scripts[job['mode']]:raise ValueError('Unknown fixed native inference entry')
    def no_network(*args,**kwargs):raise RuntimeError('Native inference is offline; provision reviewed models/caches on the existing server first')
    socket.socket.connect=no_network;socket.socket.connect_ex=no_network;socket.create_connection=no_network
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',WANDB_MODE='offline',HYDRA_FULL_ERROR='1')
    if job['accelerator']=='cpu':os.environ['CUDA_VISIBLE_DEVICES']=''
    actual={name:importlib.metadata.version(name) for name in job['native_software_versions']}
    if actual!=job['native_software_versions']:raise RuntimeError('Native child interpreter dependencies differ from the explicitly reviewed versions')
    Path(job['version_receipt']).write_text(json.dumps({'interpreter':sys.executable,'actual_package_versions':actual,'mode':job['mode'],'download_allowed':False},indent=2),encoding='utf8')
    random.seed(job['seed'])
    import numpy as np,torch
    np.random.seed(job['seed']);torch.manual_seed(job['seed'])
    if job.get('torch_hub_directory'):torch.hub.set_dir(job['torch_hub_directory'])
    if torch.cuda.is_available():torch.cuda.manual_seed_all(job['seed'])
    root=Path(job['repository']).resolve();os.chdir(root);sys.path.insert(0,str(root));sys.argv=[str(root/job['script'])]+job['arguments'];runpy.run_path(str(root/job['script']),run_name='__main__')

if __name__=='__main__':main()
