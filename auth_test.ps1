Param(
  [string]$Base = "http://localhost:8000",
  [string]$Email = ("richard+" + (Get-Random -Max 999999) + "@example.com"),
  [string]$Password = "P@ssw0rd!123",
  [string]$Name = "Richard"
)

Write-Host "Base      :" $Base
Write-Host "Email     :" $Email
Write-Host "Password  :" ("*" * $Password.Length)
Write-Host "----------"

# 1) Health
try {
  $health = Invoke-RestMethod "$Base/healthz"
  Write-Host "[healthz]" ($health | ConvertTo-Json -Depth 5)
} catch {
  Write-Warning "healthz failed: $($_.Exception.Message)"
  exit 1
}

# 2) Register
try {
  $regBody = @{ email = $Email; password = $Password; name = $Name } | ConvertTo-Json
  $reg = Invoke-RestMethod -Method POST "$Base/auth/register" -ContentType "application/json" -Body $regBody
  Write-Host "[register] OK:" ($reg | ConvertTo-Json -Depth 5)
} catch {
  Write-Warning ("register failed: " + $_.ErrorDetails.Message)
  # Continue: maybe user exists; that's ok
}

# 3) Login (OAuth2PasswordRequestForm)
try {
  $loginBody = "username=$($Email)&password=$([uri]::EscapeDataString($Password))"
  $login = Invoke-RestMethod -Method POST "$Base/auth/login" -ContentType "application/x-www-form-urlencoded" -Body $loginBody
  $token = $login.access_token
  if (-not $token) { throw "No token returned" }
  Write-Host "[login] OK, token acquired"
} catch {
  Write-Error ("login failed: " + $_.ErrorDetails.Message)
  exit 1
}

# 4) Me
try {
  $headers = @{ Authorization = "Bearer $token" }
  $me = Invoke-RestMethod "$Base/auth/me" -Headers $headers
  Write-Host "[me] OK:" ($me | ConvertTo-Json -Depth 5)
} catch {
  Write-Error ("me failed: " + $_.ErrorDetails.Message)
  exit 1
}
