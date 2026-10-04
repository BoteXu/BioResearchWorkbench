"""Fixed server-side scientific and OCR adapter bundles; no local heavy execution."""
import json
import re
import shutil
from pathlib import Path
from academic_common import artifact, rows, text, digest
from evidence import atomic_json

HERE=Path(__file__).resolve().parent
BACKENDS={
    'coloc_susie':{'packages':['jsonlite','coloc','susieR'],'source':'https://chr1swallace.github.io/coloc/articles/a06_SuSiE.html','license':'GPL-3 / MIT (susieR)','required':{'trait1','trait2','ld1','ld2','genome_build','ancestry','ld_provenance','coverage_description','trait1_type','trait2_type','N1','N2','priors'}},
    'decoupler_activity':{'packages':['jsonlite','decoupleR'],'source':'https://saezlab.github.io/decoupleR/reference/run_ulm.html','license':'GPL-3','required':{'matrix','network','network_source','network_version','input_scale','min_targets','methods'}},
    'metafor_multilevel':{'packages':['jsonlite','metafor'],'source':'https://wviechtb.github.io/metafor/reference/rma.mv.html','license':'GPL-2','required':{'effects','covariance','effect_scale','estimand','independent_unit','moderators','dependence_description'}},
}


def inspect_scientific_backends() -> dict:
    """List fixed server adapters and their runtime boundaries without installing packages or probing a server."""
    return {'success':True,'adapters':{k:{**v,'runtime_state':'requires_server_receipt','placement':'server'} for k,v in BACKENDS.items()},
        'limitations':['Bundled R code is not proof of an available server package or scientific validation. Use the existing environment and real runner receipts. No automatic package installation.']}


def prepare_scientific_backend(backend: str, configuration: dict, remote_workdir: str, expected_host: str,
                               output_directory: str, context: dict, inputs: list, rscript: str = 'Rscript') -> dict:
    """Validate a fixed scientific configuration and prepare a checksum-bound server task with mandatory runtime QC; do not submit."""
    from workflow_ext import prepare_remote_task, _relative
    if backend not in BACKENDS:raise ValueError('Unknown scientific adapter')
    if not isinstance(configuration,dict) or not BACKENDS[backend]['required']<=set(configuration):raise ValueError('Incomplete scientific configuration')
    if not inputs:raise ValueError('Checksummed server input manifest required')
    paths={'coloc_susie':['trait1','trait2','ld1','ld2'],'decoupler_activity':['matrix','network'],'metafor_multilevel':['effects','covariance']}[backend]
    for key in paths:_relative(configuration[key])
    if not set(configuration[k] for k in paths)<={i['path'] for i in inputs}:raise ValueError('All data files must be in the checksum input manifest')
    _relative(output_directory)
    if not rscript or '\x00' in rscript:raise ValueError('Select an existing Rscript executable')
    config={**configuration,'backend':backend,'context':context,'output_directory':output_directory,'seed':configuration.get('seed',1)}
    if backend=='coloc_susie':
        if config['trait1_type'] not in {'quant','cc'} or config['trait2_type'] not in {'quant','cc'}:raise ValueError('Explicit trait types required')
        if type(config['N1']) is not int or type(config['N2']) is not int or min(config['N1'],config['N2'])<10:raise ValueError('Positive sample sizes required')
        for i in (1,2):
            k='sdY'+str(i) if config['trait'+str(i)+'_type']=='quant' else 's'+str(i)
            if k not in config:raise ValueError('Quantitative trait sdY or case-control case fraction required')
        for p in rows(config['priors'],20):
            if not {'p1','p2','p12'}<=set(p) or any(type(p[k]) not in {int,float} or not 0<p[k]<1 for k in ('p1','p2','p12')) or p['p12']>min(p['p1'],p['p2']):raise ValueError('Invalid coloc prior grid')
        if not config['priors']:raise ValueError('Explicit prior sensitivity grid required')
    if backend=='decoupler_activity':
        if config['input_scale'] not in {'normalized_expression','signed_statistic','log_fold_change'} or not config['methods'] or not set(config['methods'])<={'ulm','mlm'} or type(config['min_targets']) is not int or config['min_targets']<3:raise ValueError('Select ULM/MLM, declared input scale and at least three targets')
    if backend=='metafor_multilevel':
        if not isinstance(config['moderators'],list) or len(config['moderators'])>10 or any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',m) or m in {'yi','vi','study_id','effect_id'} for m in config['moderators']):raise ValueError('Use explicit safe moderator column names')
    bundle=prepare_remote_task([rscript,'scientific_backend.R','scientific_config.json'],remote_workdir,expected_host,
        [output_directory+'/summary.json',output_directory+'/results.rds',output_directory+'/session.txt'],context,inputs)
    folder=Path(bundle['bundle']);atomic_json(folder/'scientific_config.json',config);shutil.copyfile(HERE/'scientific_backend.R',folder/'scientific_backend.R')
    return {**bundle,'backend':backend,'qc':'mandatory_in_server_program','configuration_sha256':digest((folder/'scientific_config.json').read_bytes()),
        'limitations':bundle['limitations']+['Copy input data and the full bundle to the declared working directory. Scientific code performs QC before fitting; failed QC exits without success outputs. Existing packages only.']}


def prepare_pdf_ocr(pdf_input: str, remote_workdir: str, expected_host: str, output_directory: str,
                    context: dict, inputs: list, language: str = 'eng', ocrmypdf: str = 'ocrmypdf') -> dict:
    """Prepare a fixed server OCR batch adapter with searchable PDF, page-located extraction and low-text QC; no upload or local OCR installation."""
    from workflow_ext import prepare_remote_task,_relative
    _relative(pdf_input);_relative(output_directory)
    if not re.fullmatch(r'[a-z]{3}(\+[a-z]{3})*',language):raise ValueError('Use installed OCR language codes')
    if pdf_input not in {i['path'] for i in inputs}:raise ValueError('Checksummed PDF input required')
    config={'input':pdf_input,'output_directory':output_directory,'language':language,'executable':ocrmypdf}
    bundle=prepare_remote_task(['python3','ocr_adapter.py','ocr_config.json'],remote_workdir,expected_host,
        [output_directory+'/searchable.pdf',output_directory+'/pages.json',output_directory+'/qc.json'],context,inputs)
    folder=Path(bundle['bundle']);atomic_json(folder/'ocr_config.json',config);shutil.copyfile(HERE/'ocr_adapter.py',folder/'ocr_adapter.py')
    return {**bundle,'limitations':bundle['limitations']+['OCRmyPDF, Tesseract and pypdf must already exist on the server. Low text, replacement characters and page-count changes require review; OCR accuracy is not established by completion.']}
