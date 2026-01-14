# tests\smoketest.ps1
param(
  [string]$Base = "http://localhost:8000",
  [string]$Email = "test@example.com",
  [string]$Password = "test1234"
)

$ErrorActionPreference = "Stop"
$PSDefaultParameterValues['Invoke-WebRequest:DisableKeepAlive'] = $true

Write-Host "🔎 Healthcheck..." -ForegroundColor Cyan
$h = Invoke-RestMethod -Uri "$Base/healthz"
if(-not $h.ok){ throw "Healthz faalde: $($h | ConvertTo-Json -Depth 3)" }
"OK: healthz $( $h.version ) – db=$($h.db_ready) auth=$($h.auth_ready)"

Write-Host "🔐 Login..." -ForegroundColor Cyan
$loginForm = @{
  username   = $Email
  password   = $Password
  grant_type = "password"
  scope      = ""
}
$loginResp = Invoke-WebRequest -Uri "$Base/auth/login" -Method POST `
  -Body $loginForm -ContentType "application/x-www-form-urlencoded"
$token = ($loginResp.Content | ConvertFrom-Json).access_token
if(-not $token){ throw "Geen token ontvangen: $($loginResp.Content)" }
"Token: $($token.Substring(0,24))..."

Write-Host "📊 Dashboard..." -ForegroundColor Cyan
$hdr = @{ Authorization = "Bearer $token" }
$dash = Invoke-WebRequest -Uri "$Base/dashboard" -Headers $hdr
$dashJson = $dash.Content | ConvertFrom-Json
$dashJson | ConvertTo-Json -Depth 5
