"""Fixed server-native R routes; no package installation or arbitrary script selection."""
from pathlib import Path
import subprocess
from runtime import read,write
def analyze(inputs,p,out,mode):
    allowed={'seurat_workflow','harmony_integrate','seurat_transfer','singler_annotate','hdwgcna_network','monocle3_trajectory','diablo_fit','snf_fusion','msstats_compare','muscat_pseudobulk','banksy_domains','progeny_activity','spark_spatial','xcms_preprocess','nestedcv_glmnet'}
    if mode not in allowed:raise ValueError('Unrecognized fixed native R route')
    from native_teaching_contracts import validate
    validate(mode,p)
    exe=Path(p['rscript'])
    if not exe.is_absolute() or not exe.is_file() or exe.name!='Rscript':raise ValueError('Existing exact server Rscript required')
    if not isinstance(p['software_versions'],dict) or not p['software_versions']:raise ValueError('Pin the actual installed R package versions')
    write(out/'native_r_request.private.json',{'inputs':{k:str(v) for k,v in inputs.items()},'parameters':p,'out':str(out),'mode':mode})
    with (out/'native_r.stdout.log').open('xb') as stdout,(out/'native_r.stderr.log').open('xb') as stderr:
        script='native_nestedcv.R' if mode=='nestedcv_glmnet' else 'native_xcms.R' if mode=='xcms_preprocess' else 'native_omics_expansion.R' if mode in {'monocle3_trajectory','diablo_fit','snf_fusion','msstats_compare','muscat_pseudobulk','banksy_domains','progeny_activity','spark_spatial','xcms_preprocess','nestedcv_glmnet'} else 'native_teaching.R'
        run=subprocess.run([str(exe),str(Path(__file__).with_name(script)),str(out/'native_r_request.private.json')],stdout=stdout,stderr=stderr,check=False)
    if run.returncode:raise RuntimeError('Native R backend failed; inspect preserved logs and partial results')
    outputs=[(out/r['file'],r['role']) for r in read(out/'native_r_outputs.json')]
    for filename,role in [('native_r.stdout.log','backend_stdout'),('native_r.stderr.log','backend_stderr')]:
        if (out/filename).stat().st_size:outputs.append((out/filename,role))
    return outputs
