$API = "https://rlhf-annotation-api.fly.dev/api/v1"
$FE = "https://rlhf-annotation-studio.vercel.app"
$pass = 0; $fail = 0

function Ok($name, $detail) { Write-Host "PASS: $name - $detail" -ForegroundColor Green; $script:pass++ }
function Fail($name, $detail) { Write-Host "FAIL: $name - $detail" -ForegroundColor Red; $script:fail++ }
function Get-ErrStatusCode($err) {
    if ($null -ne $err.Exception -and $null -ne $err.Exception.Response -and $null -ne $err.Exception.Response.StatusCode) {
        return [int]$err.Exception.Response.StatusCode.value__
    }
    return -1
}

Write-Host "`n=== E2E Test Suite ===" -ForegroundColor Cyan

# 1. Frontend shell smoke
$frontendHtml = ""
try {
    $frontendHtml = (Invoke-WebRequest -Uri $FE -UseBasicParsing -TimeoutSec 30).Content
    if ($frontendHtml.Contains("__NEXT_DATA__") -and $frontendHtml.Contains("RLHF Annotation Studio")) {
        Ok "Frontend shell" "nextjs app shell detected"
    } else {
        Fail "Frontend shell" "missing Next.js shell markers"
    }
} catch { Fail "Frontend shell" $_ }

# 2. Frontend route smoke (auth + dashboard routes available)
try {
    $authHtml = (Invoke-WebRequest -Uri "$FE/auth" -UseBasicParsing -TimeoutSec 30).Content
    $dashStatus = (Invoke-WebRequest -Uri "$FE/dashboard" -UseBasicParsing -TimeoutSec 30 -MaximumRedirection 0 -ErrorAction SilentlyContinue).StatusCode
    $hasAuthCopy = $authHtml -match "RLHF Annotation Studio"

    if ($hasAuthCopy -and ($dashStatus -eq 200 -or $dashStatus -eq 307 -or $dashStatus -eq 308)) {
        Ok "Frontend routes" "auth route responds; dashboard route reachable/redirects"
    } else {
        $detail = "authHeading=$hasAuthCopy dashboardStatus=$dashStatus"
        Fail "Frontend routes" $detail
    }
} catch { Fail "Frontend routes" $_ }

# 3. Health
try {
    $r = (Invoke-WebRequest -Uri "$API/health" -UseBasicParsing -TimeoutSec 30).Content | ConvertFrom-Json
    if ($r.status -eq "ok") { Ok "Health" $r.status } else { Fail "Health" $r.status }
} catch { Fail "Health" $_ }

# 4. Inference status
try {
    $r = (Invoke-WebRequest -Uri "$API/inference/status" -UseBasicParsing -TimeoutSec 30).Content | ConvertFrom-Json
    if ($r.enabled -and $r.configured) { Ok "Inference status" "enabled=$($r.enabled) configured=$($r.configured)" }
    else { Fail "Inference status" "enabled=$($r.enabled) configured=$($r.configured)" }
} catch { Fail "Inference status" $_ }

# 5. Models
try {
    $r = (Invoke-WebRequest -Uri "$API/inference/models" -UseBasicParsing -TimeoutSec 30).Content | ConvertFrom-Json
    if ($r.models.Count -ge 3) { Ok "Models" "default=$($r.default) count=$($r.models.Count)" }
    else { Fail "Models" "count=$($r.models.Count)" }
} catch { Fail "Models" $_ }

$ts = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$emailA = "e2e-a-$ts@test.com"
$emailB = "e2e-b-$ts@test.com"
$tokenA = ""; $sidA = ""
$tokenB = ""; $sidB = ""

# 6. Register user A
try {
    $b = '{"name":"E2E Tester A","email":"' + $emailA + '","password":"Test123456","phone":"+1 555"}'
    $r = (Invoke-WebRequest -Uri "$API/auth/register" -Method POST -Body $b -ContentType "application/json" -UseBasicParsing -TimeoutSec 30).Content | ConvertFrom-Json
    $tokenA = $r.token; $sidA = $r.session_id
    if ($tokenA -and $sidA) { Ok "Register A" "session=$sidA" } else { Fail "Register A" "missing token/session" }
} catch { Fail "Register A" $_ }

# 7. Login user A
try {
    $b = '{"email":"' + $emailA + '","password":"Test123456"}'
    $r = (Invoke-WebRequest -Uri "$API/auth/login" -Method POST -Body $b -ContentType "application/json" -UseBasicParsing -TimeoutSec 30).Content | ConvertFrom-Json
    if ($r.token -and $r.annotator.email -eq $emailA) { Ok "Login A" "email=$($r.annotator.email)" }
    else { Fail "Login A" "mismatch" }
} catch { Fail "Login A" $_ }

# 8. Wrong password
try {
    $b = '{"email":"' + $emailA + '","password":"wrong"}'
    Invoke-WebRequest -Uri "$API/auth/login" -Method POST -Body $b -ContentType "application/json" -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop | Out-Null
    Fail "Wrong password" "should have returned 401"
} catch {
    $statusCode = Get-ErrStatusCode $_
    if ($statusCode -eq 401) { Ok "Wrong password" "401 as expected" }
    else { Fail "Wrong password" "got $statusCode" }
}

# 9. Duplicate email
try {
    $b = '{"name":"Dup","email":"' + $emailA + '","password":"Test123456","phone":"+1"}'
    Invoke-WebRequest -Uri "$API/auth/register" -Method POST -Body $b -ContentType "application/json" -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop | Out-Null
    Fail "Duplicate email" "should have returned 409"
} catch {
    $statusCode = Get-ErrStatusCode $_
    if ($statusCode -eq 409) { Ok "Duplicate email" "409 as expected" }
    else { Fail "Duplicate email" "got $statusCode" }
}

# 10. Register user B
try {
    $b = '{"name":"E2E Tester B","email":"' + $emailB + '","password":"Test123456","phone":"+1 777"}'
    $r = (Invoke-WebRequest -Uri "$API/auth/register" -Method POST -Body $b -ContentType "application/json" -UseBasicParsing -TimeoutSec 30).Content | ConvertFrom-Json
    $tokenB = $r.token; $sidB = $r.session_id
    if ($tokenB -and $sidB) { Ok "Register B" "session=$sidB" } else { Fail "Register B" "missing token/session" }
} catch { Fail "Register B" $_ }

# 11. Inference stream
try {
    $headers = @{ "Content-Type"="application/json" }
    if ($tokenA) { $headers["Authorization"] = "Bearer $tokenA" }
    $b = '{"prompt":"What is 2+2? Answer in one word.","model":"Qwen/Qwen2.5-7B-Instruct"}'
    $r = Invoke-WebRequest -Uri "$API/inference/stream" -Method POST -Body $b -Headers $headers -UseBasicParsing -TimeoutSec 120
    $lines = $r.Content -split "`n" | Where-Object { $_.StartsWith("data: ") }
    $tokens = ($lines | Where-Object { $_ -match '"token"' }).Count
    $done = ($lines | Where-Object { $_ -match "\[DONE\]" }).Count
    if ($tokens -ge 1 -and $done -ge 1) { Ok "Inference stream" "$tokens tokens, DONE received" }
    else { Fail "Inference stream" "tokens=$tokens done=$done" }
} catch { Fail "Inference stream" $_ }

# 12. Workspace round-trip for user A
try {
    $hA = @{ "Content-Type"="application/json"; "Authorization"="Bearer $tokenA" }
    $b = '{"tasks":[{"id":"t1","type":"rating","title":"Test"}],"annotations":{"t1":{"status":"done"}},"task_times":{"t1":42}}'
    Invoke-WebRequest -Uri "$API/sessions/$sidA/workspace" -Method PUT -Body $b -Headers $hA -UseBasicParsing -TimeoutSec 30 | Out-Null
    $r = (Invoke-WebRequest -Uri "$API/sessions/$sidA/workspace" -Headers @{"Authorization"="Bearer $tokenA"} -UseBasicParsing -TimeoutSec 30).Content | ConvertFrom-Json
    if ($r.tasks.Count -ge 1) { Ok "Workspace sync (owner)" "round-trip OK" } else { Fail "Workspace sync (owner)" "empty" }
} catch { Fail "Workspace sync (owner)" $_ }

# 13. Ownership check: B cannot read A workspace
try {
    Invoke-WebRequest -Uri "$API/sessions/$sidA/workspace" -Headers @{"Authorization"="Bearer $tokenB"} -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop | Out-Null
    Fail "Ownership GET (B->A)" "should have returned 403"
} catch {
    $statusCode = Get-ErrStatusCode $_
    if ($statusCode -eq 403) { Ok "Ownership GET (B->A)" "403 as expected" }
    else { Fail "Ownership GET (B->A)" "got $statusCode" }
}

# 14. Ownership check: B cannot write A workspace
try {
    $hB = @{ "Content-Type"="application/json"; "Authorization"="Bearer $tokenB" }
    $b = '{"tasks":[{"id":"x"}],"annotations":{"x":{"status":"done"}},"task_times":{"x":1}}'
    Invoke-WebRequest -Uri "$API/sessions/$sidA/workspace" -Method PUT -Body $b -Headers $hB -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop | Out-Null
    Fail "Ownership PUT (B->A)" "should have returned 403"
} catch {
    $statusCode = Get-ErrStatusCode $_
    if ($statusCode -eq 403) { Ok "Ownership PUT (B->A)" "403 as expected" }
    else { Fail "Ownership PUT (B->A)" "got $statusCode" }
}

# 15. Ownership check: A cannot read B workspace
try {
    Invoke-WebRequest -Uri "$API/sessions/$sidB/workspace" -Headers @{"Authorization"="Bearer $tokenA"} -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop | Out-Null
    Fail "Ownership GET (A->B)" "should have returned 403"
} catch {
    $statusCode = Get-ErrStatusCode $_
    if ($statusCode -eq 403) { Ok "Ownership GET (A->B)" "403 as expected" }
    else { Fail "Ownership GET (A->B)" "got $statusCode" }
}

# 16. Ownership check: A cannot write B workspace
try {
    $hA = @{ "Content-Type"="application/json"; "Authorization"="Bearer $tokenA" }
    $b = '{"tasks":[{"id":"y"}],"annotations":{"y":{"status":"done"}},"task_times":{"y":1}}'
    Invoke-WebRequest -Uri "$API/sessions/$sidB/workspace" -Method PUT -Body $b -Headers $hA -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop | Out-Null
    Fail "Ownership PUT (A->B)" "should have returned 403"
} catch {
    $statusCode = Get-ErrStatusCode $_
    if ($statusCode -eq 403) { Ok "Ownership PUT (A->B)" "403 as expected" }
    else { Fail "Ownership PUT (A->B)" "got $statusCode" }
}

# 17. Unauthenticated workspace GET must be denied
try {
    Invoke-WebRequest -Uri "$API/sessions/$sidA/workspace" -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop | Out-Null
    Fail "Workspace GET unauth" "should have returned 401"
} catch {
    $statusCode = Get-ErrStatusCode $_
    if ($statusCode -eq 401) { Ok "Workspace GET unauth" "401 as expected" }
    else { Fail "Workspace GET unauth" "got $statusCode" }
}

# 18. Unauthenticated workspace PUT must be denied
try {
    $b = '{"tasks":[],"annotations":{},"task_times":{}}'
    Invoke-WebRequest -Uri "$API/sessions/$sidA/workspace" -Method PUT -Body $b -ContentType "application/json" -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop | Out-Null
    Fail "Workspace PUT unauth" "should have returned 401"
} catch {
    $statusCode = Get-ErrStatusCode $_
    if ($statusCode -eq 401) { Ok "Workspace PUT unauth" "401 as expected" }
    else { Fail "Workspace PUT unauth" "got $statusCode" }
}

Write-Host "`n=== $pass passed, $fail failed ===" -ForegroundColor $(if ($fail -gt 0) {"Yellow"} else {"Green"})

# Release gate snapshot from automated checks
Write-Host "`n=== Release Gate (Automated) ===" -ForegroundColor Cyan
if ($fail -eq 0) {
    Write-Host "[x] all tests pass (this suite)" -ForegroundColor Green
    Write-Host "[x] deploy smoke pass (frontend + API checks)" -ForegroundColor Green
} else {
    Write-Host "[ ] all tests pass (this suite)" -ForegroundColor Yellow
    Write-Host "[ ] deploy smoke pass (frontend + API checks)" -ForegroundColor Yellow
}
Write-Host "[ ] manual scenario checklist completed (required before release)" -ForegroundColor Yellow
