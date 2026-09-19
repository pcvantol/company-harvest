$ErrorActionPreference = 'Stop'
$Python = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { 'python' }
$PythonArgs = @()
if (-not $env:PYTHON_BIN -and (Get-Command py -ErrorAction SilentlyContinue)) {
  try {
    & py -3.14 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,14) else 2)" 2>$null
    if ($LASTEXITCODE -eq 0) { $Python = 'py'; $PythonArgs = @('-3.14') }
  } catch { }
}
& $Python @PythonArgs -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,14) else 2)"
if ($LASTEXITCODE -ne 0) { throw 'Python 3.14 is vereist.' }
& $Python @PythonArgs -c "import platform; print(f'Hostpreflight: Python {platform.python_version()} op {platform.system()}/{platform.machine()} beschikbaar.')"
