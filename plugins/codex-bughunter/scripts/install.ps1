[CmdletBinding()]
param(
    [switch]$Uninstall,
    [switch]$RemoveMarketplace,
    [string]$BurpJar,
    [string]$BurpUrl,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'
$PluginName = 'codex-bughunter'
$MarketplaceName = 'codex-bughunter-local'
$PluginId = "$PluginName@$MarketplaceName"
$PluginRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PluginRoot)
$MarketplaceManifest = Join-Path $RepoRoot '.agents\plugins\marketplace.json'
$McpSetup = Join-Path $PSScriptRoot 'setup_harness_mcp.py'
$ExpectedMarketplaceRoot = [System.IO.Path]::TrimEndingDirectorySeparator(
    [System.IO.Path]::GetFullPath($RepoRoot)
)
$ExpectedPluginRoot = [System.IO.Path]::TrimEndingDirectorySeparator(
    [System.IO.Path]::GetFullPath($PluginRoot)
)

function Show-Usage {
    @'
Install Codex BugHunter from this checkout:
  pwsh ./plugins/codex-bughunter/scripts/install.ps1

Options:
  -Uninstall            remove the plugin
  -RemoveMarketplace    also remove the local marketplace
  -BurpJar <path>       opt in to a local Burp MCP JAR
  -BurpUrl <url>        opt in to a running Burp MCP HTTP endpoint
  -Help                 show this help
'@ | Write-Host
}

function Normalize-LocalPath {
    param([string]$PathValue)

    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return $null
    }

    $trimmed = $PathValue.Replace('/', '\')
    if ($trimmed.StartsWith('\\?\UNC\')) {
        $trimmed = '\\' + $trimmed.Substring(8)
    } elseif ($trimmed.StartsWith('\\?\')) {
        $trimmed = $trimmed.Substring(4)
    }

    return [System.IO.Path]::TrimEndingDirectorySeparator(
        [System.IO.Path]::GetFullPath($trimmed)
    )
}

function Invoke-CodexJson {
    param(
        [string[]]$Arguments,
        [string[]]$RequiredArrayFields
    )

    $output = & codex @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Codex command failed: codex $($Arguments -join ' ')"
    }

    $jsonText = ($output | Where-Object { $_ -ne $null }) -join "`n"
    if ([string]::IsNullOrWhiteSpace($jsonText)) {
        throw "Codex command returned empty JSON output: codex $($Arguments -join ' ')"
    }

    try {
        $parsed = $jsonText | ConvertFrom-Json -Depth 16
    } catch {
        throw "Codex command returned invalid JSON: codex $($Arguments -join ' ')"
    }

    if ($parsed -isnot [pscustomobject] -and $parsed -isnot [hashtable]) {
        throw "Codex command returned a non-object JSON payload: codex $($Arguments -join ' ')"
    }

    foreach ($field in $RequiredArrayFields) {
        $property = $parsed.PSObject.Properties[$field]
        if ($null -eq $property) {
            throw "Codex command omitted required '$field' array: codex $($Arguments -join ' ')"
        }
        if ($property.Value -isnot [System.Collections.IList]) {
            throw "Codex command returned non-array '$field' data: codex $($Arguments -join ' ')"
        }
    }

    return $parsed
}

function Invoke-CodexCommand {
    param(
        [string]$FailureMessage,
        [string[]]$Arguments
    )

    & codex @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

function Get-TargetMarketplace {
    $response = Invoke-CodexJson -Arguments @('plugin', 'marketplace', 'list', '--json') -RequiredArrayFields @('marketplaces')
    $matches = @($response.marketplaces | Where-Object {
            $_ -is [pscustomobject] -and $_.name -eq $MarketplaceName
        })
    if ($matches.Count -gt 1) {
        throw "Multiple marketplaces named $MarketplaceName are configured."
    }
    if ($matches.Count -eq 0) {
        return $null
    }
    return $matches[0]
}

function Assert-TargetMarketplaceMatches {
    param($Marketplace)

    if ($null -eq $Marketplace) {
        return
    }

    $actualRoot = Normalize-LocalPath $Marketplace.root
    if ($null -eq $actualRoot) {
        throw "Marketplace $MarketplaceName does not report a valid root."
    }
    if ($actualRoot -ne $ExpectedMarketplaceRoot) {
        throw "Marketplace $MarketplaceName already points to $actualRoot, expected $ExpectedMarketplaceRoot."
    }
}

function Get-ValidatedTargetMarketplace {
    $marketplace = Get-TargetMarketplace
    if ($null -ne $marketplace) {
        Assert-TargetMarketplaceMatches $marketplace
    }
    return $marketplace
}

function Get-TargetPluginRecord {
    param(
        [ValidateSet('installed', 'available')]
        [string]$RecordSet
    )

    if ($RecordSet -eq 'available') {
        $response = Invoke-CodexJson -Arguments @('plugin', 'list', '--available', '--json') -RequiredArrayFields @('available')
        $records = @($response.available)
    } else {
        $response = Invoke-CodexJson -Arguments @('plugin', 'list', '--json') -RequiredArrayFields @('installed')
        $records = @($response.installed)
    }

    $matches = @($records | Where-Object {
            $_ -is [pscustomobject] -and $_.pluginId -eq $PluginId
        })
    if ($matches.Count -gt 1) {
        throw "Multiple plugin records matched $PluginId."
    }
    if ($matches.Count -eq 0) {
        return $null
    }
    return $matches[0]
}

function Assert-TargetPluginMatches {
    param($PluginRecord)

    if ($null -eq $PluginRecord) {
        return
    }

    if ($PluginRecord.PSObject.Properties['source'] -eq $null -or
            ($PluginRecord.source -isnot [pscustomobject] -and $PluginRecord.source -isnot [hashtable])) {
        throw "Plugin record for $PluginId is missing a valid source object."
    }

    $actualSource = Normalize-LocalPath $PluginRecord.source.path
    if ($null -eq $actualSource) {
        throw "Plugin $PluginId is missing a source path."
    }
    if ($actualSource -ne $ExpectedPluginRoot) {
        throw "Plugin $PluginId is surfaced from $actualSource, expected $ExpectedPluginRoot."
    }

    if ($PluginRecord.PSObject.Properties['marketplaceSource'] -ne $null -and
            $PluginRecord.marketplaceSource -is [pscustomobject] -and
            $PluginRecord.marketplaceSource.sourceType -eq 'local') {
        $actualMarketplaceSource = Normalize-LocalPath $PluginRecord.marketplaceSource.source
        if ($null -eq $actualMarketplaceSource) {
            throw "Plugin $PluginId is missing a marketplace source path."
        }
        if ($actualMarketplaceSource -ne $ExpectedMarketplaceRoot) {
            throw "Plugin $PluginId is linked to marketplace root $actualMarketplaceSource, expected $ExpectedMarketplaceRoot."
        }
    }
}

function Get-ValidatedTargetPluginRecord {
    param(
        [ValidateSet('installed', 'available')]
        [string]$RecordSet
    )

    $pluginRecord = Get-TargetPluginRecord -RecordSet $RecordSet
    if ($null -ne $pluginRecord) {
        Assert-TargetPluginMatches $pluginRecord
    }
    return $pluginRecord
}

if ($Help) {
    Show-Usage
    exit 0
}

if ($BurpJar -and $BurpUrl) {
    throw 'Choose either -BurpJar or -BurpUrl, not both.'
}

if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw 'Codex CLI is required and must be available on PATH.'
}

if (-not (Test-Path -LiteralPath $MarketplaceManifest -PathType Leaf)) {
    throw "Marketplace manifest not found: $MarketplaceManifest"
}

if ($Uninstall) {
    $installedPluginRecord = Get-ValidatedTargetPluginRecord -RecordSet installed
    if ($null -ne $installedPluginRecord) {
        Invoke-CodexCommand -FailureMessage 'Codex plugin removal failed.' -Arguments @(
            'plugin', 'remove', $PluginId, '--json'
        )
    } else {
        Write-Host 'Codex BugHunter is not installed.'
    }

    if ($RemoveMarketplace) {
        $marketplace = Get-ValidatedTargetMarketplace
        if ($null -ne $marketplace) {
            Invoke-CodexCommand -FailureMessage 'Marketplace removal failed.' -Arguments @(
                'plugin', 'marketplace', 'remove', $MarketplaceName, '--json'
            )
        }
    }
    exit 0
}

$marketplace = Get-ValidatedTargetMarketplace
if ($null -eq $marketplace) {
    Invoke-CodexCommand -FailureMessage 'Could not register the local marketplace.' -Arguments @(
        'plugin', 'marketplace', 'add', $RepoRoot, '--json'
    )
}

$availablePluginRecord = Get-ValidatedTargetPluginRecord -RecordSet available
$installedPluginRecord = Get-ValidatedTargetPluginRecord -RecordSet installed
if ($null -eq $availablePluginRecord -and $null -eq $installedPluginRecord) {
    throw "Plugin $PluginId was not found in the configured marketplace or installed set."
}

Invoke-CodexCommand -FailureMessage 'Could not install Codex BugHunter.' -Arguments @(
    'plugin', 'add', $PluginId, '--json'
)

if ($BurpJar) {
    & python $McpSetup --jar $BurpJar
    if ($LASTEXITCODE -ne 0) { throw 'Burp MCP setup failed.' }
} elseif ($BurpUrl) {
    & python $McpSetup --url $BurpUrl
    if ($LASTEXITCODE -ne 0) { throw 'Burp MCP setup failed.' }
}

Write-Host 'Installed. Restart Codex, then invoke $codex-bughunter:workflow-hunt explicitly.'
