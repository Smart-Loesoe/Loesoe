param(
  [string]$DbContainer = "loesoe-db-1",
  [string]$DbName      = "loesoe",
  [string]$DbUser      = "postgres",
  [string]$SqlFile     = ".\init_auth_schema.sql"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path $SqlFile)) {
  Write-Error "SQL file not found: $SqlFile"
  exit 1
}

Write-Host "[1/3] Copy SQL into container..."
$dest = "/tmp/init_auth_schema.sql"
# Let op de ${DbContainer}: om de : niet als drive-letter te laten gelden
docker cp $SqlFile "${DbContainer}:$dest" | Out-Null

Write-Host "[2/3] Execute SQL in Postgres..."
$cmd = "psql -U $DbUser -d $DbName -v ON_ERROR_STOP=1 -f $dest"
docker exec -i $DbContainer sh -lc $cmd

Write-Host "[3/3] Verify tables..."
docker exec -i $DbContainer psql -U $DbUser -d $DbName -c "\dt"

Write-Host "✅ Done. Users-table should exist now."
