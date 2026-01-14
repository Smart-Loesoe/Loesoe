Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-RandomBase64([int]$bytes = 64) {
    $b = New-Object byte[] $bytes
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    return [Convert]::ToBase64String($b)
}

function New-RandomPassword([int]$length = 30) {
    # Veilig + env-friendly (geen quotes nodig)
    $chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789_-"
    $rand = New-Object System.Random
    -join (1..$length | ForEach-Object { $chars[$rand.Next(0, $chars.Length)] })
}

$projectRoot = (Get-Location).Path
$envPath = Join-Path $projectRoot ".env"

Write-Host "== Loesoe .env generator ==" -ForegroundColor Cyan

# Vaste waarden
$tz = "Europe/Amsterdam"
$cors = "http://localhost:5173,http://127.0.0.1:5173"

# Nieuwe secrets
$authSecret = New-RandomBase64 64
$pgDb = "loesoe"
$pgUser = "loesoe"
$pgPass = New-RandomPassword 30

# Keys (vragen aan jou; je mag leeg laten en later invullen)
$openaiKey = Read-Host "Plak je NIEUWE OPENAI_API_KEY (of laat leeg en vul later in .env)"
$openaiProject = Read-Host "Plak je OPENAI_PROJECT (of laat leeg)"
$serpApiKey = Read-Host "Plak je NIEUWE SERPAPI_KEY (of laat leeg)"
$modelDefault = "gpt-5.1"

$envContent = @"
# Tijdszone
TZ=$tz

# CORS
CORS_ORIGINS=$cors

# =========================
# AUTH / JWT
# =========================
AUTH_SECRET=$authSecret
AUTH_ISSUER=loesoe
AUTH_AUDIENCE=loesoe-web
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=43200

# =========================
# DATABASE (LEIDEND + MATCHT ALTIJD)
# =========================
POSTGRES_DB=$pgDb
POSTGRES_USER=$pgUser
POSTGRES_PASSWORD=$pgPass
DATABASE_URL=postgresql+asyncpg://`$`{POSTGRES_USER}:`$`{POSTGRES_PASSWORD}@db:5432/`$`{POSTGRES_DB}

# =========================
# Uploads & signed links
# =========================
UPLOADS_DIR=/app/data/uploads
SIGNER_DEFAULT_TTL=600

# =========================
# OpenAI / GPT
# =========================
OPENAI_API_KEY=$openaiKey
OPENAI_PROJECT=$openaiProject
MODEL_DEFAULT=$modelDefault

# =========================
# Websearch
# =========================
SERPAPI_KEY=$serpApiKey
"@

$envContent | Set-Content -Path $envPath -Encoding utf8 -NoNewline

Write-Host "`n✅ .env geschreven naar: $envPath" -ForegroundColor Green
Write-Host "✅ Nieuwe POSTGRES_PASSWORD + AUTH_SECRET zijn gezet." -ForegroundColor Green
Write-Host "`nNEXT (belangrijk!):" -ForegroundColor Yellow
Write-Host "1) docker compose down -v" -ForegroundColor Yellow
Write-Host "2) docker compose up -d --build --force-recreate" -ForegroundColor Yellow
Write-Host "3) docker exec -it loesoe-api-1 sh -lc `"printenv | grep DATABASE_URL`"" -ForegroundColor Yellow
