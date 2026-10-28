$ErrorActionPreference = 'Stop'

$state = Join-Path $env:LOCALAPPDATA 'dsh-multicad'
$venvPython = Join-Path $state 'venv\Scripts\python.exe'
$server = Join-Path $state 'python\src\server.py'

if (-not (Test-Path $venvPython)) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $state 'bin\setup.ps1') *>> (Join-Path $state 'setup.log')
}

if (-not (Test-Path $venvPython)) {
    [Console]::Error.WriteLine("multicad: Python environment setup failed; see $state\setup.log")
    exit 1
}

& $venvPython $server
exit $LASTEXITCODE
