param(
    [string]$InstallDir = '',
    [string]$McpName = '',
    [ValidateSet('core','local','omics','full')][string]$Profile = '',
    [ValidateSet('codex','claude-desktop','vscode','portable')][string]$Client = 'codex',
    [ValidateSet('shared','stdio')][string]$Transport = '',
    [int]$SharedPort = 8768,
    [switch]$SkipRegistration,
    [switch]$TrustDnsProxy,
    [switch]$InstallVina,
    [switch]$InstallSkills,
    [string]$SkillsDir = '',
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
$Uv = (Get-Command uv -ErrorAction Stop).Source
$InstallerArgs = @('run','--python','3.11','--no-project',(Join-Path $PSScriptRoot 'install.py'),'--client',$Client)
if ($InstallDir) { $InstallerArgs += @('--install-dir',$InstallDir) }
if ($McpName) { $InstallerArgs += @('--mcp-name',$McpName) }
if ($Profile) { $InstallerArgs += @('--profile',$Profile) }
if ($Transport) { $InstallerArgs += @('--transport',$Transport) }
$InstallerArgs += @('--shared-port', [string]$SharedPort)
if ($SkipRegistration) { $InstallerArgs += '--skip-registration' }
if ($TrustDnsProxy) { $InstallerArgs += '--trust-dns-proxy' }
if ($InstallVina) { $InstallerArgs += '--install-vina' }
if ($InstallSkills) { $InstallerArgs += '--install-skills' }
if ($SkillsDir) { $InstallerArgs += @('--skills-dir',$SkillsDir) }
if ($ValidateOnly) { $InstallerArgs += '--validate-only' }
& $Uv @InstallerArgs
if ($LASTEXITCODE -ne 0) { throw "Installation failed (exit $LASTEXITCODE)" }
