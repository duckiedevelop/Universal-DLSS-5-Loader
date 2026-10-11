param([switch]$SmokeUi)

$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    $application = Join-Path $PSScriptRoot 'build\Release\Dlss5Setup.exe'
    $ready = Test-Path -LiteralPath $application -PathType Leaf
    foreach ($arch in @('x64', 'x86')) {
        foreach ($folder in @('payload', 'payload\d3d9')) {
            $manifestPath = Join-Path $PSScriptRoot "$folder\$arch-manifest.json"
            if (!(Test-Path -LiteralPath $manifestPath)) { $ready = $false; continue }
            $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
            foreach ($entry in $manifest.PSObject.Properties) {
                $component = Join-Path $PSScriptRoot "$folder\$arch\$($entry.Name)"
                if (!(Test-Path -LiteralPath $component -PathType Leaf)) { $ready = $false }
            }
        }
    }
    if (!(Test-Path -LiteralPath 'diagnostics\host64\dlss5-feed-host64.exe')) { $ready = $false }
    if (!$ready) {
        Write-Host 'Preparing Universal DLSS 5 Loader in this project folder...'
        & .\build.ps1
    }
    if ($SmokeUi) {
        $smokeProcess = Start-Process -FilePath $application -ArgumentList '--smoke-ui' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
        if (!$smokeProcess.WaitForExit(30000)) {
            Stop-Process -Id $smokeProcess.Id
            throw 'UI startup check timed out.'
        }
        if ($smokeProcess.ExitCode -ne 0) { throw "UI startup check failed: $($smokeProcess.ExitCode)" }
        Write-Host 'UI startup check passed.'
    } else {
        Start-Process -FilePath $application -WorkingDirectory $PSScriptRoot
    }
} finally {
    Pop-Location
}
