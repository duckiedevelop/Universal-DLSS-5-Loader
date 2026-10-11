param([string]$PythonExecutable)

$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    if (!(Test-Path -LiteralPath 'build\Release\Dlss5Setup.exe')) {
        throw 'Build the application first with .\build.ps1 -SourceOnly.'
    }
    if (!$PythonExecutable) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            $PythonExecutable = py -3 -c 'import sys; print(sys.executable)'
            if ($LASTEXITCODE -ne 0) { throw 'Python 3 could not be located.' }
        } else {
            $PythonExecutable = (Get-Command python -ErrorAction Stop).Source
        }
    }
    $feederRevision = '7b41f5f3e57c260dec6012695c258e876fdfe6c5'
    if (!(Test-Path -LiteralPath 'third_party\feeder\.git')) {
        git clone --depth 1 https://github.com/jlrouzies-fr/DLSS5-Feeder.git third_party/feeder
        if ($LASTEXITCODE -ne 0) { throw 'Feeder source download failed.' }
        git -C third_party/feeder fetch --depth 1 origin $feederRevision
        if ($LASTEXITCODE -ne 0) { throw 'Pinned Feeder revision download failed.' }
        git -C third_party/feeder checkout $feederRevision
        if ($LASTEXITCODE -ne 0) { throw 'Feeder checkout failed.' }
    }
    $actualRevision = git -C third_party/feeder rev-parse HEAD
    if ($actualRevision -ne $feederRevision) { throw 'Existing Feeder checkout is not the pinned revision. It was left intact.' }
    $hostSource = Get-Content -LiteralPath 'third_party\feeder\host\dlss5-feed-host64.cpp' -Raw
    if (!$hostSource.Contains('explicitly selected NVIDIA adapter')) {
        git -C third_party/feeder apply ../../tools/nvidia-host.patch
        if ($LASTEXITCODE -ne 0) { throw 'NVIDIA adapter patch failed.' }
    }
    & $PythonExecutable prepare-sdk.py
    if ($LASTEXITCODE -ne 0) { throw 'SDK preparation failed.' }
    & .\third_party\feeder\host\build-host.bat
    if ($LASTEXITCODE -ne 0) { throw 'Helper compilation failed.' }
    & $PythonExecutable prepare-packages.py
    if ($LASTEXITCODE -ne 0) { throw 'Package verification failed.' }
    if (!(Test-Path -LiteralPath 'runtime\nvngx_dlssnr.dll')) {
        & $PythonExecutable fetch-runtime.py
        if ($LASTEXITCODE -ne 0) { throw 'NR runtime verification failed.' }
    }
    New-Item -ItemType Directory -Path 'lab\native64' -Force | Out-Null
    Copy-Item -LiteralPath 'build\Release\Dlss5Setup.exe' -Destination 'lab\native64\PipelinePreview.exe'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\third_party\feeder\tools\Install-DLSS5Feeder.ps1 -GameExe .\lab\native64\PipelinePreview.exe -Api D3D -Consumer RenoDX -HelperMode No -MvProvider 3 -LocalFiles .\packages -Downloads .\packages\cache -FeederZip .\packages\DLSS5-Feeder-1.18.0-beta.2.zip -RenoDxAddon .\packages\renodx-dlss5_7.0.0-rc8.zip -DlssNrDll .\runtime\nvngx_dlssnr.dll -DlssDll .\packages\nvngx_dlss_310.9.1.zip -ReShadeSetup .\packages\ReShade_Setup_6.8.0_Addon.exe -LumeniteZip .\packages\LumeniteFX-mainline.zip -NoElevate -NoPause -Yes -NoVerify -Force
    if ($LASTEXITCODE -ne 0) { throw 'Project lab staging failed.' }
    & $PythonExecutable make-payload.py
    if ($LASTEXITCODE -ne 0) { throw 'Offline payload preparation failed.' }
    & $PythonExecutable prepare-d3d9.py
    if ($LASTEXITCODE -ne 0) { throw 'DirectX 9 bridge preparation failed.' }
    Write-Host 'Offline application payload ready. No game was changed.'
} finally { Pop-Location }
