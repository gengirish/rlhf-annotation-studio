$API = "https://rlhf-annotation-api.fly.dev/api/v1"

Write-Host "`n=== Latency Benchmark (3 rounds) ===" -ForegroundColor Cyan
Write-Host ""

$endpoints = @(
    @{ Name = "Health";     Method = "GET";  Uri = "$API/health";           Body = $null },
    @{ Name = "Models";     Method = "GET";  Uri = "$API/inference/models"; Body = $null },
    @{ Name = "Inf Status"; Method = "GET";  Uri = "$API/inference/status"; Body = $null }
)

foreach ($ep in $endpoints) {
    $times = @()
    for ($i = 0; $i -lt 3; $i++) {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        try {
            if ($ep.Method -eq "GET") {
                $r = Invoke-WebRequest -Uri $ep.Uri -UseBasicParsing -TimeoutSec 30
            } else {
                $r = Invoke-WebRequest -Uri $ep.Uri -Method POST -Body $ep.Body -ContentType "application/json" -UseBasicParsing -TimeoutSec 30
            }
            $sw.Stop()
            $serverTime = ""
            if ($r.Headers["X-Response-Time"]) { $serverTime = " (server: $($r.Headers['X-Response-Time']))" }
            $times += $sw.ElapsedMilliseconds
        } catch {
            $sw.Stop()
            $times += $sw.ElapsedMilliseconds
        }
    }
    $avg = [math]::Round(($times | Measure-Object -Average).Average)
    $min = ($times | Measure-Object -Minimum).Minimum
    $max = ($times | Measure-Object -Maximum).Maximum
    Write-Host "$($ep.Name.PadRight(12)) avg=${avg}ms  min=${min}ms  max=${max}ms  raw=[$($times -join ', ')]" -ForegroundColor $(if ($avg -lt 500) {"Green"} elseif ($avg -lt 2000) {"Yellow"} else {"Red"})
}

# Auth round-trip (register + login)
$ts = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$email = "bench-$ts@test.com"

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$b = '{"name":"Bench","email":"' + $email + '","password":"bench123","phone":"+1"}'
try {
    $r = Invoke-WebRequest -Uri "$API/auth/register" -Method POST -Body $b -ContentType "application/json" -UseBasicParsing -TimeoutSec 30
    $sw.Stop()
    $regMs = $sw.ElapsedMilliseconds
    $serverTime = if ($r.Headers["X-Response-Time"]) { $r.Headers["X-Response-Time"] } else { "n/a" }
    Write-Host "Register     total=${regMs}ms  (server: $serverTime)" -ForegroundColor $(if ($regMs -lt 1500) {"Green"} elseif ($regMs -lt 3000) {"Yellow"} else {"Red"})
} catch {
    $sw.Stop()
    Write-Host "Register     FAILED after $($sw.ElapsedMilliseconds)ms: $_" -ForegroundColor Red
}

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$b = '{"email":"' + $email + '","password":"bench123"}'
try {
    $r = Invoke-WebRequest -Uri "$API/auth/login" -Method POST -Body $b -ContentType "application/json" -UseBasicParsing -TimeoutSec 30
    $sw.Stop()
    $loginMs = $sw.ElapsedMilliseconds
    $serverTime = if ($r.Headers["X-Response-Time"]) { $r.Headers["X-Response-Time"] } else { "n/a" }
    Write-Host "Login        total=${loginMs}ms  (server: $serverTime)" -ForegroundColor $(if ($loginMs -lt 1500) {"Green"} elseif ($loginMs -lt 3000) {"Yellow"} else {"Red"})
} catch {
    $sw.Stop()
    Write-Host "Login        FAILED after $($sw.ElapsedMilliseconds)ms: $_" -ForegroundColor Red
}

Write-Host ""
