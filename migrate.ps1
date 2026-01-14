# C:\Loesoe\loesoe\migrate.ps1
$ErrorActionPreference = "Stop"

# === Config ===
$FilePath   = "api\migrations\2025-09-18_add_sha256_unique.sql"
$ComposeDir = "infra"     # map met docker-compose.yml
$DbService  = "db"
$DbName     = "loesoe"
$DbUser     = "loesoe"
$Tmp        = "/tmp/migration.sql"

# 1) Bestaat de SQL?
if (-not (Test-Path $FilePath)) {
  Write-Error "SQL-bestand niet gevonden: $FilePath"
  exit 1
}

# 2) Ga naar infra-map voor docker compose
$startDir = Get-Location
Push-Location $ComposeDir

try {
  # -- Probeer compose cp/exec
  $CpTarget = "$($DbService):$Tmp"
  Write-Host "Copy via 'docker compose cp': ..\$FilePath -> $CpTarget"
  docker compose cp -- "..\$FilePath" $CpTarget | Out-Null

  Write-Host "Run migration via 'docker compose exec'..."
  docker compose exec -T $DbService psql -U $DbUser -d $DbName -f $Tmp

  Write-Host "Migration done."
}
catch {
  Write-Warning "compose cp/exec faalde → gebruik docker cp/exec fallback..."

  # -- Fallback met container id
  $DbContainer = (docker compose ps -q $DbService).Trim()
  if (-not $DbContainer) { throw "DB service container niet gevonden." }

  $Dest = "$($DbContainer):$Tmp"
  Write-Host "Copy via 'docker cp': ..\$FilePath -> $Dest"
  docker cp "..\$FilePath" $Dest | Out-Null

  Write-Host "Run migration via 'docker exec'..."
  docker exec -i $DbContainer psql -U $DbUser -d $DbName -f $Tmp

  Write-Host "Migration done (fallback)."
}
finally {
  Pop-Location
}
