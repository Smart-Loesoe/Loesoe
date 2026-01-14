Add-Type -AssemblyName System.Net.Http
$client = New-Object System.Net.Http.HttpClient
$client.Timeout = [TimeSpan]::FromSeconds(10)
$response = $client.GetAsync("http://localhost:8000/stream/sse", [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).Result
$stream = $response.Content.ReadAsStreamAsync().Result
$reader = New-Object System.IO.StreamReader($stream)
$start = Get-Date
while ((Get-Date) - $start -lt [TimeSpan]::FromSeconds(5)) {
    if ($reader.EndOfStream) { Start-Sleep -Milliseconds 100; continue }
    $line = $reader.ReadLine()
    if ($line) { Write-Host $line }
}
$reader.Dispose(); $client.Dispose()
