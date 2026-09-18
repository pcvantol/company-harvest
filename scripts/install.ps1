param([Parameter(Mandatory=$true)][string]$Wheel,[Parameter(Mandatory=$true)][string]$Venv,[string]$Wheelhouse,[string]$Sha256,[switch]$Browser,[switch]$DryRun,[string]$Log)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Wheel -PathType Leaf)) { throw "Wheel ontbreekt: $Wheel" }
if ($Sha256 -and ((Get-FileHash -Algorithm SHA256 -LiteralPath $Wheel).Hash.ToLowerInvariant() -ne $Sha256.ToLowerInvariant())) { throw 'Wheelchecksum wijkt af.' }
if ($Log) { Start-Transcript -Path $Log -Append | Out-Null }
if ($DryRun) { Write-Output 'Dry-run geslaagd: wheel, checksum en opties zijn geldig.'; if ($Log) { Stop-Transcript | Out-Null }; exit 0 }
if (Test-Path $Venv) { throw "Installatiemap bestaat al: $Venv" }
try {
  py -m venv $Venv
  $Python = Join-Path $Venv 'Scripts\python.exe'
  if ($Wheelhouse) { & $Python -m pip install --no-index --find-links $Wheelhouse $Wheel } else { & $Python -m pip install $Wheel }
  if ($LASTEXITCODE -ne 0) { throw 'Installatie mislukt.' }
  if ($Browser) { & $Python -m playwright install chromium; if ($LASTEXITCODE -ne 0) { throw 'Browserinstallatie mislukt.' } }
  & (Join-Path $Venv 'Scripts\company-harvest.exe') --version
  if ($LASTEXITCODE -ne 0) { throw 'Versiecontrole mislukt.' }
} catch {
  if (Test-Path $Venv) { Remove-Item -LiteralPath $Venv -Recurse -Force }
  throw
} finally {
  if ($Log) { Stop-Transcript | Out-Null }
}
