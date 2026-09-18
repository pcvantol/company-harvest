$ErrorActionPreference = 'Stop'
$Python = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { 'py' }
& $Python -c "import sys; raise SystemExit(0 if (3,11)<=sys.version_info[:2]<(3,15) else 2)"
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11-3.14 ontbreekt.' }
& $Python -c "import platform; print(f'Hostpreflight: Python {platform.python_version()} op {platform.system()}/{platform.machine()} beschikbaar.')"

