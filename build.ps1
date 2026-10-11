param(
    [switch]$SourceOnly,
    [string]$PythonExecutable
)

$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    if (!$PythonExecutable) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            $PythonExecutable = py -3 -c 'import sys; print(sys.executable)'
            if ($LASTEXITCODE -ne 0) { throw 'Python 3 could not be located.' }
        } else {
            $PythonExecutable = (Get-Command python -ErrorAction Stop).Source
        }
    }
    if (!(Test-Path -LiteralPath 'third_party\imgui\imgui.h')) {
        git clone --depth 1 --branch v1.92.9b https://github.com/ocornut/imgui.git third_party/imgui
        if ($LASTEXITCODE -ne 0) { throw 'ImGui download failed.' }
    }
    $configureArgs = @('-S', '.', '-B', 'build', '-G', 'Visual Studio 17 2022', '-A', 'x64', "-DPython3_EXECUTABLE=$PythonExecutable")
    if (Test-Path -LiteralPath 'build\CMakeCache.txt') {
        $cachedSource = Get-Content -LiteralPath 'build\CMakeCache.txt' | Select-String '^CMAKE_HOME_DIRECTORY:INTERNAL=' | Select-Object -First 1
        if ($cachedSource) {
            $sourcePath = $cachedSource.Line.Substring('CMAKE_HOME_DIRECTORY:INTERNAL='.Length)
            if ([IO.Path]::GetFullPath($sourcePath) -ne [IO.Path]::GetFullPath($PSScriptRoot)) {
                $configureArgs += '--fresh'
                Write-Host 'Refreshing the CMake cache for the current project location.'
            }
        }
    }
    cmake @configureArgs
    if ($LASTEXITCODE -ne 0) { throw 'CMake configuration failed.' }
    cmake --build build --config Release --parallel 4
    if ($LASTEXITCODE -ne 0) { throw 'Compilation failed.' }
    if (!$SourceOnly) {
        # Manifests are tracked; the actual payloads are generated after cloning.
        $payloadReady = $true
        foreach ($arch in @('x64', 'x86')) {
            $manifestPath = "payload\$arch-manifest.json"
            if (!(Test-Path -LiteralPath $manifestPath)) { $payloadReady = $false; continue }
            $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
            foreach ($entry in $manifest.PSObject.Properties) {
                if (!(Test-Path -LiteralPath (Join-Path "payload\$arch" $entry.Name) -PathType Leaf)) {
                    $payloadReady = $false
                }
            }
        }
        if (!(Test-Path -LiteralPath 'diagnostics\host64\dlss5-feed-host64.exe')) { $payloadReady = $false }
        if (!$payloadReady) { & .\Prepare-App.ps1 -PythonExecutable $PythonExecutable }

        $bridgeReady = $true
        foreach ($arch in @('x64', 'x86')) {
            foreach ($file in @('d3d9.dll', 'dgVoodoo.conf', 'ReShade.ini')) {
                if (!(Test-Path -LiteralPath "payload\d3d9\$arch\$file")) { $bridgeReady = $false }
            }
            if (!(Test-Path -LiteralPath "payload\d3d9\$arch-manifest.json")) { $bridgeReady = $false }
        }
        if (!$bridgeReady) {
            & $PythonExecutable prepare-d3d9.py
            if ($LASTEXITCODE -ne 0) { throw 'DirectX 9 bridge preparation failed.' }
        }
        & $PythonExecutable -c "import backend; [backend.files_for(arch, 'D3D9') for arch in ('x64', 'x86')]; print('All payload hashes verified.')"
        if ($LASTEXITCODE -ne 0) { throw 'Payload verification failed.' }
        ctest --test-dir build -C Release --output-on-failure
    } else {
        ctest --test-dir build -C Release --output-on-failure -LE payload
    }
    if ($LASTEXITCODE -ne 0) { throw 'Loader tests failed.' }
    Write-Host 'Built: build\Release\Dlss5Setup.exe'
    if ($SourceOnly) { Write-Host 'Source-only build: run .\build.ps1 to prepare rendering payloads and run installer tests.' }
} finally {
    Pop-Location
}
