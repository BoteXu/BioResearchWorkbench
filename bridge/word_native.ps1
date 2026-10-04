param([Parameter(Mandatory=$true)][string]$RequestFile)
$ErrorActionPreference = 'Stop'
$request = Get-Content -LiteralPath $RequestFile -Raw -Encoding UTF8 | ConvertFrom-Json
$word = $null
$doc = $null
$keepOpen = $false
function Checkpoint([string]$stage) { [IO.File]::WriteAllText((Join-Path $request.folder 'native_progress.json'), ('{"stage":"' + $stage + '"}')) }
try {
    $hash = [Security.Cryptography.SHA256]::Create()
    try { $actualHash = [BitConverter]::ToString($hash.ComputeHash([IO.File]::ReadAllBytes($request.source))).Replace('-','').ToLowerInvariant() } finally { $hash.Dispose() }
    if ($actualHash -ne $request.source_sha256) { throw 'Native source hash changed' }
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.Options.BackgroundSave = $false
    $word.AutomationSecurity = 3
    if ($word.Documents.Count -ne 0) { $keepOpen=$true; throw 'Word automation instance is not empty; no existing documents will be touched' }
    $readOnly = $request.operation -in @('inspect','render')
    $doc = $word.Documents.Open($request.source, $false, $readOnly, $false)
    Checkpoint 'opened'
    if ($doc.ProtectionType -ne -1) { throw 'Protected document is unsupported' }
    $fields = @()
    foreach ($field in $doc.Fields) {
        $fields += @{start=$field.Code.Start; end=$field.Result.End; code=$field.Code.Text}
    }
    $paragraphs = @()
    foreach ($paragraph in $doc.Paragraphs) {
        $range = $paragraph.Range
        $paragraphs += @{start=$range.Start; end=$range.End; text=$range.Text; page=$range.Information(3)}
    }
    $result = @{state='inspected'; word_version=$word.Version; fields=$fields; paragraphs=$paragraphs; comments=$doc.Comments.Count; revisions=$doc.Revisions.Count}
    if ($request.operation -eq 'revise') {
        # Validate every range before any edit; offsets refer to original text.
        foreach ($change in @($request.edits) + @($request.comments)) {
            if ($null -eq $change) { continue }
            $range = $doc.Range($change.start,$change.end)
            if ($range.Text -cne $change.old_text) { throw 'Native range text changed' }
            if ($range.Fields.Count -gt 0 -or $range.Revisions.Count -gt 0) { throw 'Field or existing revision intersects requested range' }
            foreach ($field in $fields) {
                if ($change.start -lt $field.end -and $change.end -gt $field.start) { throw 'Edit/comment intersects a citation field' }
            }
        }
        $doc.TrackRevisions = $true
        Checkpoint 'validated'
        # Comments before descending edits let Word retain their anchor movement.
        foreach ($comment in $request.comments) {
            $range = $doc.Range($comment.start,$comment.end)
            [void]$doc.Comments.Add($range,$comment.comment)
        }
        Checkpoint 'commented'
        foreach ($change in ($request.edits | Sort-Object start -Descending)) {
            $range = $doc.Range($change.start,$change.end)
            if ($range.Text.Contains([char]7) -or $range.Text.EndsWith("`r")) { throw 'Select text inside a paragraph/cell, excluding structure markers' }
            $range.Text = $change.new_text
        }
        Checkpoint 'edited'
        if ($request.refresh_fields) {
            # Zotero fields require the plugin; exclude them from generic update.
            foreach ($field in $doc.Fields) {
                if ($field.Code.Text -notmatch 'ZOTERO|CSL_CITATION|CSL_BIBLIOGRAPHY') { [void]$field.Update() }
            }
        }
        $doc.Save()
        Checkpoint 'saved'
        $result.state = 'saved_revision'
        $result.comments = $doc.Comments.Count
        $result.revisions = $doc.Revisions.Count
    } elseif ($request.operation -eq 'render') {
        # Rendering is a separate read-only task; its timeout cannot obscure an
        # already saved revision or trigger a retry of a manuscript write.
        $doc.ExportAsFixedFormat((Join-Path $request.folder 'rendered.pdf'),17,$false,0,0,1,1,0,$false,$false,0,$false,$false,$false)
        Checkpoint 'rendered'
        $result.state='rendered_review_required'
    } elseif ($request.operation -eq 'zotero_refresh') {
        # Only an already-installed trusted global template; no document macros.
        $trusted = @($word.Templates | Where-Object { $_.Name -eq 'Zotero.dotm' })
        if ($trusted.Count -ne 1) { throw 'Installed Zotero global template required' }
        $doc.Activate()
        $word.Visible = $true
        $word.Run('Zotero.ZoteroRefresh')
        $keepOpen = $true
        $result.state = 'refresh_invoked_pending_review'
    } elseif ($request.operation -ne 'inspect') { throw 'Unknown fixed native operation' }
    $result | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $request.folder 'native_receipt.json') -Encoding UTF8
} finally {
    if (-not $keepOpen) {
        if ($null -ne $doc) { $doc.Close(0) }
        if ($null -ne $word) { $word.Quit(0) }
    }
}
