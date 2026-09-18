param([Parameter(Mandatory=$true)][string]$Wheel,[Parameter(Mandatory=$true)][string]$Venv,[string]$Wheelhouse,[switch]$Browser)
$ErrorActionPreference = 'Stop'
if (Test-Path $Venv) { throw "Installatiemap bestaat al: $Venv" }
py -m venv $Venv
$Python = Join-Path $Venv 'Scripts\python.exe'
if ($Wheelhouse) { & $Python -m pip install --no-index --find-links $Wheelhouse $Wheel } else { & $Python -m pip install $Wheel }
if ($LASTEXITCODE -ne 0) { throw 'Installatie mislukt.' }
if ($Browser) { & $Python -m playwright install chromium }
& (Join-Path $Venv 'Scripts\company-harvest.exe') --version

