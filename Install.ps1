param(
    [string]$InstallDir = (Join-Path ([Environment]::GetFolderPath('UserProfile')) 'BiomniTools'),
    [ValidateSet('core','local','omics','full')][string]$Profile = '',
    [ValidateSet('codex','claude-desktop','vscode','portable')][string]$Client = 'codex',
    [switch]$SkipRegistration,
    [switch]$TrustDnsProxy,
    [switch]$InstallVina,
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
$Uv = (Get-Command uv -ErrorAction Stop).Source
$InstallerArgs = @('run','--python','3.11','--no-project',(Join-Path $PSScriptRoot 'install.py'),'--install-dir',$InstallDir,'--client',$Client)
if ($Profile) { $InstallerArgs += @('--profile',$Profile) }
if ($SkipRegistration) { $InstallerArgs += '--skip-registration' }
if ($TrustDnsProxy) { $InstallerArgs += '--trust-dns-proxy' }
if ($InstallVina) { $InstallerArgs += '--install-vina' }
if ($ValidateOnly) { $InstallerArgs += '--validate-only' }
& $Uv @InstallerArgs
if ($LASTEXITCODE -ne 0) { throw "Installation failed (exit $LASTEXITCODE)" }
