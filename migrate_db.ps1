param(
  [string]$Service = "db",
  [string]$File = "api/db/migrations/018_auth_rls.sql"
)

Write-Host "Applying migration: $File"
$cmd = "psql -v ON_ERROR_STOP=1 -U postgres -d app -f /app/$File"
docker compose exec $Service sh -lc $cmd
Write-Host "Done."
