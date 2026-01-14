cd C:\Loesoe\loesoe
Write-Host "🐳 Docker containers starten..." -ForegroundColor Cyan
docker compose up -d
Write-Host "🌐 API bereikbaar op http://localhost:8000"
Write-Host "💻 Webinterface op http://localhost:5173"
