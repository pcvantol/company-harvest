param([Parameter(Mandatory=$true)][string]$Venv,[Parameter(Mandatory=$true)][string]$RunDir)
& (Join-Path $Venv 'Scripts\company-lookup.exe') run preflight --run-dir $RunDir
exit $LASTEXITCODE

