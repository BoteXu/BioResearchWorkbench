"""Fixed server OCR adapter. Run through a hostname/checksum-gated task runner."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def run(config):
    from pypdf import PdfReader
    source=Path(config['input']);out=Path(config['output_directory'])
    original=PdfReader(source)
    if original.is_encrypted:raise ValueError('Encrypted input is unsupported')
    out.mkdir(parents=True,exist_ok=False)
    result=subprocess.run([config['executable'],'--skip-text','--output-type','pdf','--language',config['language'],str(source),str(out/'searchable.pdf')],timeout=14400)
    if result.returncode:raise RuntimeError('OCR process failed')
    reader=PdfReader(out/'searchable.pdf');pages=[];issues=[]
    if len(reader.pages)!=len(original.pages):issues.append('page_count_changed')
    for i,page in enumerate(reader.pages,1):
        value=page.extract_text() or '';pages.append({'page':i,'text':value})
        if len(value.strip())<40:issues.append('page_'+str(i)+'_low_text')
        if '\ufffd' in value:issues.append('page_'+str(i)+'_replacement_characters')
    (out/'pages.json').write_text(json.dumps(pages,ensure_ascii=False),encoding='utf8')
    (out/'qc.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'issues':issues,
        'decision':'manual_review_required' if issues else 'text_extracted_not_accuracy_validated','page_count':len(pages)}),encoding='utf8')


if __name__=='__main__':run(json.loads(Path(sys.argv[1]).read_text(encoding='utf8')))
