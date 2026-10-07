#Requires -Version 5.1
<#
  End-to-end smoke test: Ollama -> Odysseus -> one real chat reply.

  Checks, in order:
    1. Ollama answers on -OllamaUrl and has -Model pulled
    2. Odysseus /api/health responds
    3. Admin login works
    4. The Ollama endpoint is registered in Odysseus (created if missing) and
       lists -Model
    5. A chat session on that model returns a non-empty reply via /api/chat

  Usage (native, default port 7000):
    powershell -ExecutionPolicy Bypass -File .\scripts\ollama-smoke.ps1 -Password <admin password>

  Usage (Docker overlay - the app reaches Ollama through host.docker.internal):
    powershell -ExecutionPolicy Bypass -File .\scripts\ollama-smoke.ps1 `
      -AppUrl http://127.0.0.1:7000 -EndpointUrl http://host.docker.internal:11434/v1 -Password <pw>

  The password defaults to $env:ODYSSEUS_ADMIN_PASSWORD. Exits non-zero on the
  first failed check.
#>
param(
    [string]$AppUrl = "http://127.0.0.1:7000",
    [string]$OllamaUrl = "http://localhost:11434",
    # URL Odysseus itself uses to reach Ollama (differs from -OllamaUrl in Docker).
    [string]$EndpointUrl = "",
    [string]$Model = "qwen3.5:2b",
    [string]$User = $(if ($env:ODYSSEUS_ADMIN_USER) { $env:ODYSSEUS_ADMIN_USER } else { "admin" }),
    [string]$Password = $env:ODYSSEUS_ADMIN_PASSWORD,
    [string]$Prompt = "Reply with exactly one word: pong",
    [int]$TimeoutSec = 180
)

$ErrorActionPreference = "Stop"
if (-not $EndpointUrl) { $EndpointUrl = ($OllamaUrl.TrimEnd('/') + "/v1") }

function Pass($msg) { Write-Host ("[ok]   " + $msg) -ForegroundColor Green }
function Fail($msg) { Write-Host ("[fail] " + $msg) -ForegroundColor Red; exit 1 }

# 1. Ollama itself
try {
    $tags = Invoke-RestMethod -TimeoutSec 5 ($OllamaUrl.TrimEnd('/') + "/api/tags")
} catch {
    Fail "Ollama not reachable at $OllamaUrl ($($_.Exception.Message)). Start it with 'ollama serve'."
}
$names = @($tags.models | ForEach-Object { $_.name })
if ($names -notcontains $Model) {
    Fail "Model '$Model' is not pulled. Run: ollama pull $Model   (have: $($names -join ', '))"
}
Pass "Ollama up at $OllamaUrl with $Model"

# 2. App health
$app = $AppUrl.TrimEnd('/')
try {
    Invoke-RestMethod -TimeoutSec 10 "$app/api/health" | Out-Null
} catch {
    Fail "Odysseus not reachable at $app/api/health ($($_.Exception.Message))"
}
Pass "Odysseus healthy at $app"

# 3. Login (session cookie kept in $web)
if (-not $Password) { Fail "No admin password. Pass -Password or set ODYSSEUS_ADMIN_PASSWORD." }
$web = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$headers = @{ "X-Requested-With" = "XMLHttpRequest"; "Origin" = $app }
try {
    $login = Invoke-RestMethod -Method Post -WebSession $web -Headers $headers -ContentType "application/json" `
        -Body (@{ username = $User; password = $Password } | ConvertTo-Json) "$app/api/auth/login"
} catch {
    Fail "Login failed for '$User' ($($_.Exception.Message))"
}
if (-not $login.ok) { Fail "Login did not complete (2FA enabled?): $($login | ConvertTo-Json -Compress)" }
Pass "Logged in as $User"

# 4. Register the Ollama endpoint (the route dedupes on base_url, so re-runs are safe)
try {
    $ep = Invoke-RestMethod -Method Post -WebSession $web -Headers $headers -TimeoutSec 60 `
        -Body @{ name = "Ollama"; base_url = $EndpointUrl; endpoint_kind = "auto" } "$app/api/model-endpoints"
} catch {
    Fail "Registering endpoint $EndpointUrl failed ($($_.Exception.Message))"
}
$epId = $ep.id
if (-not $epId) { Fail "Endpoint create returned no id: $($ep | ConvertTo-Json -Compress -Depth 4)" }
if (@($ep.models) -notcontains $Model) {
    Fail "Endpoint $EndpointUrl does not list $Model. Got: $(@($ep.models) -join ', ')"
}
Pass "Endpoint $EndpointUrl registered (id $epId) and lists $Model"

# 5. Session + one chat turn
try {
    $sess = Invoke-RestMethod -Method Post -WebSession $web -Headers $headers `
        -Body @{ name = "ollama-smoke"; endpoint_id = $epId; model = $Model } "$app/api/session"
} catch {
    Fail "Creating chat session failed ($($_.Exception.Message))"
}
$sw = [Diagnostics.Stopwatch]::StartNew()
try {
    $reply = Invoke-RestMethod -Method Post -WebSession $web -Headers $headers -TimeoutSec $TimeoutSec `
        -ContentType "application/json" -Body (@{ message = $Prompt; session = $sess.id } | ConvertTo-Json) "$app/api/chat"
} catch {
    Fail "Chat request failed ($($_.Exception.Message))"
}
$text = "$($reply.response)".Trim()
if (-not $text) { Fail "Chat returned an empty reply: $($reply | ConvertTo-Json -Compress -Depth 4)" }
Pass ("Chat reply from {0} in {1:N1}s: {2}" -f $Model, $sw.Elapsed.TotalSeconds, ($text.Substring(0, [Math]::Min(120, $text.Length))))

Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green
