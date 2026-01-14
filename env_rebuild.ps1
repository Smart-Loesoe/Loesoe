$ErrorActionPreference = "Stop"
Write-Host "Rebuild + tests..." -ForegroundColor Green
docker compose down -v --remove-orphans
docker compose up -d --build
Start-Sleep -Seconds 2
.\test_endpoints.ps1
