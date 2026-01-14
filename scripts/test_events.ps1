param(
  [string]$BaseUrl = "http://localhost:8000",
  [string]$UserId = "richard",
  [string]$SessionId = "s1",
  [string]$Msg = "Loesoe time",
  [string[]]$Tags = @("loesoe","fase23")
)

Write-Host "[1/4] Healthz..." -ForegroundColor Cyan
curl.exe "$BaseUrl/healthz" | Out-Host

$body = @{
  event_type="chat"
  source="web"
  user_id=$UserId
  session_id=$SessionId
  confidence=0.9
  tags=$Tags
  payload=@{ msg=$Msg }
} | ConvertTo-Json -Depth 6

Write-Host "[2/4] POST /events/log ..." -ForegroundColor Cyan
try {
  irm -Method Post -Uri "$BaseUrl/events/log" -ContentType "application/json" -Body $body | Format-List | Out-Host
} catch {
  Write-Host "POST failed:" -ForegroundColor Red
  $_.Exception.Message | Out-Host
  exit 1
}

Write-Host "[3/4] GET /events/recent?limit=5 ..." -ForegroundColor Cyan
irm "$BaseUrl/events/recent?limit=5" | ConvertTo-Json -Depth 6 | Out-Host

Write-Host "[4/4] Done." -ForegroundColor Green
