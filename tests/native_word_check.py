"""Explicit optional synthetic Windows Word execution; no personal library/draft reads."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import base64
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
import academic_common as common
import word_native_ext as word


def run():
    if os.name!='nt':raise RuntimeError('Optional native verification needs Windows Word')
    with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve(),ignore_cleanup_errors=True) as tmp:
        root=Path(tmp);source=root/'fixture.docx';script=root/'create_fixture.ps1';config=root/'fixture.json'
        config.write_text(json.dumps({'source':str(source)}),encoding='utf8')
        script.write_text("""param([string]$Config)
$ErrorActionPreference='Stop'
$value=Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
$app=New-Object -ComObject Word.Application
$app.Visible=$false
$app.AutomationSecurity=3
$app.DisplayAlerts=0
$doc=$null
try {
 if ($app.Documents.Count -ne 0) {throw 'Word instance is not empty'}
 $doc=$app.Documents.Add()
 $doc.Content.Text='Synthetic result.'
 $doc.Content.Font.Name='Arial'
 $doc.SaveAs2($value.source,16)
} finally {if($null -ne $doc){$doc.Close(0)};$app.Quit(0)}
""",encoding='utf8')
        code='$Config=$env:BRW_FIXTURE_CONFIG\n'+script.read_text().split('\n',1)[1]
        process=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(code.encode('utf-16le')).decode('ascii')],env={**os.environ,'BRW_FIXTURE_CONFIG':str(config)},capture_output=True,timeout=90)
        if process.returncode:raise RuntimeError(process.stderr.decode('utf8',errors='replace')[:3000])
        # Adapter code stays in its source folder; artifacts are redirected only.
        with patch.object(common,'HERE',root):
            sha=hashlib.sha256(source.read_bytes()).hexdigest()
            try:before=word.inspect_native_word(str(source))
            except RuntimeError:
                for log in root.rglob('native.stderr.txt'):print(log.read_text(encoding='utf8')[:4000])
                raise
            assert before['native']['state']=='inspected'
            plan=word.prepare_native_word_revision(str(source),sha,[{'start':10,'end':16,'old_text':'result','new_text':'finding','reason':'Synthetic edit'}],
                [{'start':0,'end':9,'old_text':'Synthetic','comment':'Synthetic native comment'}])
            p=Path(plan['output_directory'])/'review.json'
            # Generated-plan path must also use the isolated artifact root.
            source_home=word.HERE
            def native_call(config,folder):
                with patch.object(word,'HERE',source_home):return native_source(config,folder)
            with patch.object(word,'HERE',root),patch.object(word,'_native',side_effect=native_call):
                try:result=word.apply_native_word_revision(str(p),hashlib.sha256(p.read_bytes()).hexdigest(),True)
                except RuntimeError:
                    for log in root.rglob('native_progress.json'):print(log.read_text())
                    for log in root.rglob('native.stderr.txt'):print(log.read_text(encoding='utf8')[:2000])
                    raise
            assert result['native']['comments']==1 and result['native']['revisions']>=1
            assert result['state']=='saved_revision_rendering_pending'
            parts=common.docx_parts(Path(result['revised_file']).read_bytes())
            assert b'<w:ins' in parts['word/document.xml'] and b'<w:del' in parts['word/document.xml']
            assert b'Synthetic native comment' in parts['word/comments.xml']
            assert hashlib.sha256(source.read_bytes()).hexdigest()==sha
            print('NATIVE_WORD_SYNTHETIC_PASS: inspected offsets, tracked edit, native comment, unchanged source. PDF rendering and Zotero refresh remain separate.')


native_source=word._native
if __name__=='__main__':run()
