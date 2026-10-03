"""Private persistent software registry and explicit fixed adapters; no generic shell runner."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from evidence import atomic_json

HERE = Path(__file__).resolve().parent
REGISTRY = HERE/'software_registry.json'
SPECS = {
    'rscript':{'command':'Rscript','version_args':['--version'],'capabilities':['limma','edgeR'],'placement':'local_or_server'},
    'vina':{'command':'vina','version_args':['--version'],'capabilities':['single_ligand_docking'],'placement':'local_or_server'},
    'obabel':{'command':'obabel','version_args':['-V'],'capabilities':['explicit_structure_conversion'],'placement':'local_or_server'},
    'samtools':{'command':'samtools','version_args':['--version'],'capabilities':['server_alignment_qc'],'placement':'server'},
    'salmon':{'command':'salmon','version_args':['--version'],'capabilities':['server_transcript_quantification'],'placement':'server'},
    'star':{'command':'STAR','version_args':['--version'],'capabilities':['server_rnaseq_alignment'],'placement':'server'},
    'kallisto':{'command':'kallisto','version_args':['version'],'capabilities':['server_transcript_quantification'],'placement':'server'},
    'fastqc':{'command':'fastqc','version_args':['--version'],'capabilities':['server_fastq_qc'],'placement':'server'},
    'multiqc':{'command':'multiqc','version_args':['--version'],'capabilities':['server_qc_report_aggregation'],'placement':'server'},
    'nextflow':{'command':'nextflow','version_args':['-version'],'capabilities':['server_workflow_orchestration'],'placement':'server'},
    'docker':{'command':'docker','version_args':['--version'],'capabilities':['container_runtime_inventory'],'placement':'local_or_server'},
}


def _registry():
    if not REGISTRY.exists(): return {'schema':1,'software':{}}
    data = json.loads(REGISTRY.read_text(encoding='utf8'))
    if data.get('schema')!=1 or not isinstance(data.get('software'),dict): raise ValueError('Unsupported software registry schema')
    return data


def resolve(name,requested=None):
    if name not in SPECS: raise ValueError('Unknown fixed software adapter')
    standard = SPECS[name]['command']
    if requested and requested!=standard:
        candidate = Path(requested).expanduser().resolve(strict=True)
    else:
        saved = _registry()['software'].get(name,{}).get('executable')
        found = saved or shutil.which(standard)
        if not found and name=='vina':
            private = HERE/'bin'/('vina.exe' if os.name=='nt' else 'vina')
            if private.is_file(): found=str(private)
        if not found and name=='rscript' and os.name=='nt':
            candidates = list((Path(os.environ.get('ProgramFiles',''))/'R').glob('R-*/bin/Rscript.exe'))
            if len(candidates)==1: found=str(candidates[0])
        if not found: raise ValueError('Software is not configured or installed: '+name)
        candidate = Path(found).expanduser().resolve(strict=True)
    stem = candidate.stem.lower()
    if stem!=standard.lower() and not (name=='vina' and re.fullmatch(r'vina_\d[\w.-]*',stem)):
        raise ValueError('Executable filename does not match the fixed adapter')
    if not candidate.is_file(): raise ValueError('Software executable is not a file')
    return str(candidate)


def register_local_software(name: str, executable: str) -> dict:
    """Persist a private executable path for a known adapter; probe only its fixed version command."""
    resolved = resolve(name,executable)
    probe = subprocess.run([resolved,*SPECS[name]['version_args']],capture_output=True,text=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if probe.returncode: raise ValueError('Software version probe failed')
    data = _registry()
    data['software'][name] = {'executable':resolved,'version_output':(probe.stdout+probe.stderr).strip()[:4000],'capabilities':SPECS[name]['capabilities'],'placement':SPECS[name]['placement'],'runtime_state':'version_probe_passed'}
    atomic_json(REGISTRY,data)
    return {'success':True,'software':name,'registry_file':str(REGISTRY),'version_probe_pass':True,'limitations':['A version probe is not execution of an analysis or proof of optional package availability.','Private registry paths are excluded from publication.']}


def software_inventory() -> dict:
    """Report registered or discovered adapters without launching analyses, containers or services."""
    saved = _registry()['software']
    rows = []
    for name,spec in SPECS.items():
        try: path=resolve(name)
        except ValueError: path=None
        rows.append({'name':name,'available_path':path,'registered':name in saved,'capabilities':spec['capabilities'],'placement':spec['placement'],'runtime_state':saved.get(name,{}).get('runtime_state','unprobed')})
    return {'success':True,'software':rows,'cytoscape_interface':'local CyREST only; use explicit port and import operation','limitations':['Local discovery does not inspect the server. Use a real returned server inventory receipt.','Version and capability descriptions do not establish successful analysis execution.']}


def convert_molecular_structure(input_path: str, output_format: str, context: dict, obabel: str = 'obabel', ph: float = 7.4, generate_3d: bool = False) -> dict:
    """Convert one bounded structure through configured Open Babel with explicit pH/3D flags; chemistry needs review."""
    from compute_policy import require_local
    from transcriptomics_ext import _context,_folder,_finish
    require_local();_context(context)
    source = Path(input_path).resolve(strict=True)
    formats = {'sdf','mol','mol2','pdb','pdbqt'}
    if source.suffix.lower()[1:] not in formats or output_format not in formats or source.stat().st_size>10000000 or not 0<=ph<=14 or type(generate_3d) is not bool:
        raise ValueError('Provide supported bounded structure formats and explicit pH/3D options')
    folder = _folder('structure_conversion')
    executable = resolve('obabel',obabel)
    dest = folder/('converted.'+output_format)
    command = [executable,str(source),'-O',str(dest),'-p',str(ph)]
    if generate_3d: command.append('--gen3d')
    try:
        with (folder/'backend.log').open('w',encoding='utf8') as log:
            process = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if process.returncode or not dest.is_file() or not dest.stat().st_size: raise RuntimeError('Structure conversion failed; review the private log')
    except Exception:
        (folder/'state.json').write_text('{"state":"failed"}\n',encoding='utf8');raise
    return _finish(folder,{'workflow':'structure_conversion','context':context,'ph':ph,'generate_3d':generate_3d,'output_format':output_format,'limitations':['Conversion does not validate protonation, stereochemistry, metal coordination or force-field atom types.','Prepared PDBQT must pass the separate docking-input audit.']})


def cytoscape_import_network(graphml_path: str, port: int = 1234) -> dict:
    """Import an explicit local GraphML into a running local Cytoscape through CyREST; do not start the GUI."""
    if type(port) is not int or not 1<=port<=65535: raise ValueError('Provide a valid local CyREST port')
    file = Path(graphml_path).resolve(strict=True)
    if file.stat().st_size>10000000: raise ValueError('GraphML is too large for local visualization')
    import networkx as nx
    import requests
    graph = nx.read_graphml(file)
    if len(graph)>2000 or graph.number_of_edges()>10000: raise ValueError('Network exceeds local visualization limits')
    payload = {'data':{'name':'Biomni reviewed network'},'elements':{'nodes':[{'data':{**a,'id':str(n),'name':str(n)}} for n,a in graph.nodes(data=True)],'edges':[{'data':{**v,'id':'edge'+str(i),'source':str(a),'target':str(b)}} for i,(a,b,v) in enumerate(graph.edges(data=True))]}}
    session = requests.Session();session.trust_env=False
    try:
        response = session.post('http://localhost:'+str(port)+'/v1/networks',json=payload,timeout=30)
        response.raise_for_status()
        data = response.json()
    finally: session.close()
    return {'success':True,'cytoscape_response':data,'nodes_imported':len(graph),'edges_imported':graph.number_of_edges(),'limitations':['This records an import response only; layout, visual inspection and scientific interpretation remain separate.','The endpoint is restricted to this host; no public service or clinical data transfer is configured.']}
