param([Parameter(Mandatory=$true)][string]$Venv,[Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)
& (Join-Path $Venv 'Scripts\company-lookup.exe') @Arguments
exit $LASTEXITCODE
