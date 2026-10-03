param(
    [string]$InstallDir = (Join-Path ([Environment]::GetFolderPath('UserProfile')) 'BiomniTools'),
    [ValidateSet('core','omics','full')][string]$Profile = 'core',
    [ValidateSet('codex','claude-desktop','vscode','portable')][string]$Client = 'codex',
    [switch]$SkipRegistration,
    [switch]$TrustDnsProxy,
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
$Uv = (Get-Command uv -ErrorAction Stop).Source
$InstallerArgs = @('run','--python','3.11','--no-project',(Join-Path $PSScriptRoot 'install.py'),'--install-dir',$InstallDir,'--profile',$Profile,'--client',$Client)
if ($SkipRegistration) { $InstallerArgs += '--skip-registration' }
if ($TrustDnsProxy) { $InstallerArgs += '--trust-dns-proxy' }
if ($ValidateOnly) { $InstallerArgs += '--validate-only' }
& $Uv @InstallerArgs
if ($LASTEXITCODE -ne 0) { throw "Installation failed (exit $LASTEXITCODE)" }
