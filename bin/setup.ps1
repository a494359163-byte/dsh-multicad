$ErrorActionPreference = 'Stop'

$state = Join-Path $env:LOCALAPPDATA 'dsh-multicad'
$venv = Join-Path $state 'venv'
$root = Split-Path -Parent $PSScriptRoot
$requirements = Join-Path $root 'python\requirements.txt'

New-Item -ItemType Directory -Path $state -Force | Out-Null
Write-Output "[multicad] setup started $(Get-Date -Format o)"

function Find-Python {
    foreach ($candidate in @('py', 'python')) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        try {
            if ($candidate -eq 'py') {
                $version = & py -3 -c "import sys; print(sys.version_info[:2])" 2>$null
            } else {
                $version = & python -c "import sys; print(sys.version_info[:2])" 2>$null
            }
        } catch { continue }
        if ($LASTEXITCODE -eq 0 -and $version) { return $candidate }
    }
    throw 'No Python 3.10+ interpreter found on PATH. Install Python from python.org first.'
}

if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) {
    $python = Find-Python
    Write-Output "[multicad] creating venv with $python"
    if ($python -eq 'py') {
        & py -3 -m venv $venv
    } else {
        & python -m venv $venv
    }
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed with exit code $LASTEXITCODE" }
}

$venvPython = Join-Path $venv 'Scripts\python.exe'
Write-Output "[multicad] installing requirements"
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
    & uv pip install --python $venvPython -r $requirements
} else {
    & $venvPython -m pip install --disable-pip-version-check -r $requirements
}
if ($LASTEXITCODE -ne 0) { throw "dependency installation failed with exit code $LASTEXITCODE" }

Write-Output "[multicad] verifying imports"
& $venvPython -c "import fastmcp, mcp.server.fastmcp, win32com.client, openpyxl; print('imports ok')"
if ($LASTEXITCODE -ne 0) { throw 'import verification failed' }

Set-Content -LiteralPath (Join-Path $state 'ready.txt') -Value (Get-Date -Format o) -Encoding UTF8
Write-Output "[multicad] setup completed"
