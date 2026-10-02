param(
    [string]$InstallDir = (Join-Path $env:USERPROFILE 'BiomniTools'),
    [ValidateSet('core','omics','full')][string]$Profile = 'core',
    [ValidateSet('codex','claude-desktop','vscode','portable')][string]$Client = 'codex',
    [switch]$SkipRegistration,
    [switch]$TrustDnsProxy,
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
function Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Program (exit $LASTEXITCODE)" }
}
$PackageRoot = $PSScriptRoot
$PackagePrefix = [IO.Path]::GetFullPath($PackageRoot).TrimEnd('\') + '\'
$Manifest = Get-Content -LiteralPath (Join-Path $PackageRoot 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($Entry in $Manifest.files) {
    $Candidate = [IO.Path]::GetFullPath((Join-Path $PackageRoot $Entry.path))
    if (-not $Candidate.StartsWith($PackagePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid package path' }
    if (-not (Test-Path -LiteralPath $Candidate -PathType Leaf)) { throw "Missing package file: $($Entry.path)" }
    if ((Get-FileHash -LiteralPath $Candidate -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Entry.sha256) { throw "Checksum mismatch: $($Entry.path)" }
}
Write-Output 'PACKAGE_CHECKSUMS_OK'
if ($ValidateOnly) { return }
$Uv = (Get-Command uv -ErrorAction Stop).Source
if (-not $SkipRegistration -and $Client -eq 'codex') {
    $Codex = (Get-Command codex -ErrorAction Stop).Source
    & $Codex mcp get biomni *> $null
    if ($LASTEXITCODE -eq 0) { throw 'A biomni MCP entry already exists. Inspect it first, or use -SkipRegistration to install separately.' }
}
$TargetRoot = [IO.Path]::GetFullPath($InstallDir)
if (Test-Path -LiteralPath $TargetRoot) { throw 'Choose a new install directory; existing files will not be overwritten.' }
$ParentDir = Split-Path -Parent $TargetRoot
New-Item -ItemType Directory -Path $ParentDir -Force | Out-Null
Checked $Uv @('run', '--python', '3.11', '--no-project', (Join-Path $PackageRoot 'bootstrap_upstream.py'), $TargetRoot)
Copy-Item -LiteralPath (Join-Path $PackageRoot 'bridge') -Destination (Join-Path $TargetRoot '.local') -Recurse
$RuntimeRoot = Join-Path $TargetRoot '.venv_tools'
Checked $Uv @('venv', '--python', '3.11', $RuntimeRoot)
$Python = Join-Path $RuntimeRoot 'Scripts\python.exe'
$RequirementsName = if ($Profile -eq 'full') { 'requirements.windows-py311.lock.txt' } elseif ($Profile -eq 'core') { 'requirements-core.windows-py311.lock.txt' } else { 'requirements-omics.txt' }
Checked $Uv @('pip', 'install', '--python', $Python, '-r', (Join-Path $PackageRoot $RequirementsName))
Checked $Uv @('pip', 'install', '--python', $Python, '--no-deps', '-e', $TargetRoot)
$Bridge = Join-Path $TargetRoot '.local\bridge.py'
$env:PYTHONUTF8 = '1'
if ($TrustDnsProxy) { $env:BIOMNI_TRUST_DNS_PROXY = '1' }
Checked $Python @($Bridge, '--status')
Checked $Python @((Join-Path $TargetRoot '.local\smoke_mcp.py'), '--network')
$AgentText = (Get-Content -LiteralPath (Join-Path $PackageRoot 'AGENTS.template.md') -Raw -Encoding UTF8).Replace('{{INSTALL_DIR}}', $TargetRoot.Replace('\','/'))
$AgentFile = Join-Path $TargetRoot 'AGENTS.generated.md'
[IO.File]::WriteAllText($AgentFile, $AgentText, (New-Object Text.UTF8Encoding($false)))
$ConfigArguments = @((Join-Path $PackageRoot 'client_config.py'), '--install-dir', $TargetRoot, '--output-dir', (Join-Path $TargetRoot 'client_configs'))
if ($TrustDnsProxy) { $ConfigArguments += '--trust-dns-proxy' }
Checked $Python $ConfigArguments
if (-not $SkipRegistration -and $Client -eq 'codex') {
    $McpArguments = @('mcp', 'add', 'biomni', '--env', 'PYTHONUTF8=1')
    if ($TrustDnsProxy) { $McpArguments += @('--env', 'BIOMNI_TRUST_DNS_PROXY=1') }
    $McpArguments += @('--', $Python, (Join-Path $TargetRoot '.local\mcp_server.py'))
    Checked $Codex $McpArguments
}
Write-Output "INSTALLATION_AND_SMOKE_CHECKS_OK: $TargetRoot"
Write-Output "Merge the Biomni section from $AgentFile into your own AGENTS.md; existing instructions are not changed automatically."
Write-Output 'Open a new Codex chat to discover the MCP server. Configure your own server SSH route separately.'
