param([Parameter(Mandatory=$true)][string]$Venv,[Parameter(Mandatory=$true)][string]$RunDir)
& (Join-Path $Venv 'Scripts\company-harvest.exe') run preflight --run-dir $RunDir
exit $LASTEXITCODE

