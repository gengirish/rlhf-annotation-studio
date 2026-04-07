$env:NIM_API_KEY = "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"

$models = @(
    "nvidia/llama-3.1-nemotron-nano-8b-v1",
    "nvidia/nemotron-3-nano-30b-a3b",
    "nvidia/llama-3.3-nemotron-super-49b-v1",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1"
)

# Focused safety probes -- targeted sub-probes to keep runtime practical
$safety_probes = @(
    "dan.Dan_11_0",                                 # Jailbreak: classic DAN 11.0
    "dan.AutoDANCached",                            # Jailbreak: automated DAN
    "donotanswer.MaliciousUses",                    # Refusal: malicious use requests
    "donotanswer.InformationHazard",                # Refusal: dangerous information
    "encoding.InjectBase64",                        # Injection: base64 encoded prompts
    "encoding.InjectBase16",                        # Injection: hex encoded prompts
    "web_injection.MarkdownXSS",                     # XSS: markdown injection attacks
    "web_injection.TaskXSS",                         # XSS: task-based injection
    "lmrc.SlurUsage",                               # Toxicity: slur generation
    "lmrc.SexualContent",                           # Toxicity: sexual content generation
    "continuation.ContinueSlursReclaimedSlurs",     # Toxicity: continue slurs
    "malwaregen.TopLevel"                            # Malware: code generation
)

$probes_str = $safety_probes -join ","

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm"
$results_dir = "c:\Users\gengi\Documents\RLHF\garak-results\$timestamp"
New-Item -ItemType Directory -Force -Path $results_dir | Out-Null

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " GARAK SAFETY TEST SUITE" -ForegroundColor Cyan
Write-Host " $(Get-Date)" -ForegroundColor Cyan
Write-Host " Models: $($models.Count) (smallest to largest)" -ForegroundColor Cyan
Write-Host " Safety probes: $($safety_probes.Count)" -ForegroundColor Cyan
Write-Host " Generations per prompt: 1" -ForegroundColor Cyan
Write-Host " Results: $results_dir" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$model_idx = 0
foreach ($model in $models) {
    $model_idx++
    $short_name = ($model -split "/")[-1]
    $log_file = "$results_dir\$short_name.log"

    Write-Host ""
    Write-Host ">>> [$model_idx/$($models.Count)] Testing: $model" -ForegroundColor Yellow
    Write-Host "    Log: $log_file" -ForegroundColor DarkGray
    Write-Host "    Started: $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor DarkGray

    $cmd = "python -m garak --target_type nim --target_name $model --probes $probes_str --generations 1"

    Write-Host "    Command: $cmd" -ForegroundColor DarkGray

    Invoke-Expression $cmd 2>&1 | Tee-Object -FilePath $log_file

    Write-Host "    Finished: $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Green
    Write-Host "--------------------------------------------"
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " ALL SCANS COMPLETE" -ForegroundColor Cyan
Write-Host " Results directory: $results_dir" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "JSONL report files are in:" -ForegroundColor Yellow
Write-Host "  $env:USERPROFILE\.local\share\garak\garak_runs\" -ForegroundColor White
Write-Host ""
Write-Host "To generate an HTML report:" -ForegroundColor Yellow
Write-Host '  python -m garak.analyze --report_prefix <report_jsonl_path>' -ForegroundColor White
