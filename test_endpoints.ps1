$ErrorActionPreference = "Stop"

function Step($t){ Write-Host "`n=== $t ===" -ForegroundColor Cyan }

Step "1) /healthz"
Invoke-WebRequest http://localhost:8000/healthz | Select-Object -ExpandProperty Content

Step "2) /debug/env"
Invoke-WebRequest http://localhost:8000/debug/env | Select-Object -ExpandProperty Content

Step "3) /model"
Invoke-WebRequest http://localhost:8000/model | Select-Object -ExpandProperty Content

Step "4) /chat"
$body = @{ messages = @(@{role="user"; content="Hallo!"}) } | ConvertTo-Json -Depth 5
Invoke-WebRequest http://localhost:8000/chat -Method POST -ContentType "application/json" -Body $body | Select-Object -ExpandProperty Content
