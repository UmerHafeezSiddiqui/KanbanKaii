param(
    [string]$TunnelName = "",
    [string]$CloudflaredPath = "cloudflared",
    [switch]$UseNgrok,
    [string]$NgrokPath = "C:\ngrok\ngrok.exe",
    [string]$RedisContainer = "kanbankaii-redis"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $ProjectRoot "backend"

if ($UseNgrok -and $TunnelName) {
    throw "Choose either -UseNgrok or -TunnelName, not both."
}

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Test-HttpEndpoint([string]$Url) {
    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Wait-ForEndpoint([string]$Url, [string]$Service, [int]$Attempts = 15) {
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        if (Test-HttpEndpoint $Url) {
            Write-Host "$Service is ready." -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "$Service did not become ready at $Url. Check its terminal for errors."
}

function Start-ServiceTerminal(
    [string]$Title,
    [string]$WorkingDirectory,
    [string]$Command
) {
    $windowCommand = "`$Host.UI.RawUI.WindowTitle='$Title'; $Command"
    Start-Process powershell.exe `
        -WorkingDirectory $WorkingDirectory `
        -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $windowCommand) |
        Out-Null
}

function Wait-ForWorker([int]$Attempts = 15) {
    Push-Location $BackendRoot
    try {
        $lastCheckOutput = @()
        for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
            $previousErrorAction = $ErrorActionPreference
            try {
                # ARQ logs successful checks to stderr; PowerShell 5 must still read its exit code.
                $ErrorActionPreference = 'Continue'
                $lastCheckOutput = @(& $Python -m arq --check app.workers.slack_worker.WorkerSettings 2>&1)
                $checkExitCode = $LASTEXITCODE
            }
            finally {
                $ErrorActionPreference = $previousErrorAction
            }
            if ($checkExitCode -eq 0) {
                Write-Host "ARQ worker heartbeat is ready." -ForegroundColor Green
                return
            }
            Start-Sleep -Seconds 1
        }
        $details = ($lastCheckOutput | ForEach-Object { $_.ToString() } | Select-Object -Last 8) -join "`n"
        throw "ARQ worker has no live heartbeat. Check its terminal, credentials and Redis configuration.`n$details"
    }
    finally {
        Pop-Location
    }
}

Write-Step "Finding a working Python environment"
$Python = $null
foreach ($environment in @("backend\.venv", "backend\venv", ".runtime\audit-venv")) {
    $candidate = Join-Path $ProjectRoot "$environment\Scripts\python.exe"
    if (Test-Path $candidate) {
        try {
            & $candidate -c "import uvicorn, arq" 2>$null
            if ($LASTEXITCODE -eq 0) {
                $Python = $candidate
                break
            }
        }
        catch {
            continue
        }
    }
}
if (-not $Python) {
    throw "No working backend Python environment with uvicorn and arq was found. Create backend\.venv and install backend\requirements.txt."
}
Write-Host "Using $Python"

Write-Step "Checking Docker and Redis"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker was not found. Start Docker Desktop and ensure the docker command is available."
}
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not running. Start it, wait until it is ready, then run this script again."
}

$containerJson = docker container inspect $RedisContainer 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Redis container '$RedisContainer' does not exist. Create it with a named /data volume and -p 127.0.0.1:6379:6379. See README.md."
}
$container = @($containerJson | ConvertFrom-Json)[0]
$bindings = @($container.HostConfig.PortBindings.'6379/tcp')
if (-not $bindings.Count -or @($bindings | Where-Object { $_.HostIp -notin @("127.0.0.1", "::1") }).Count) {
    throw "Redis '$RedisContainer' must publish port 6379 only on loopback. Recreate it with -p 127.0.0.1:6379:6379, preserving its existing /data volume. No container or volume was changed."
}
if ($container.HostConfig.NetworkMode -eq "host") {
    throw "Redis host networking is not supported by this local launcher. Use a bridge network with a loopback port binding."
}
if (-not $container.State.Running) {
    docker start $RedisContainer | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not start Redis container '$RedisContainer'."
    }
}
$pong = docker exec $RedisContainer redis-cli ping 2>$null
if ($pong -ne "PONG") {
    throw "Redis started but did not return PONG."
}
Write-Host "Redis is ready." -ForegroundColor Green

Write-Step "Starting FastAPI"
if (Test-HttpEndpoint "http://127.0.0.1:8000/health") {
    Write-Host "FastAPI is already running." -ForegroundColor Yellow
}
else {
    Start-ServiceTerminal `
        "KanbanKaii - FastAPI" `
        $BackendRoot `
        "& '$Python' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
    Wait-ForEndpoint "http://127.0.0.1:8000/health" "FastAPI"
}

Write-Step "Starting ARQ worker"
$workerRunning = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like "*app.workers.slack_worker.WorkerSettings*" -and $_.CommandLine -notlike '*--check*' } |
    Select-Object -First 1
if ($workerRunning) {
    Write-Host "ARQ worker is already running." -ForegroundColor Yellow
}
else {
    Start-ServiceTerminal `
        "KanbanKaii - ARQ Worker" `
        $BackendRoot `
        "& '$Python' -m arq app.workers.slack_worker.WorkerSettings"
    Write-Host "ARQ worker terminal opened." -ForegroundColor Green
}
Wait-ForWorker

if ($UseNgrok) {
    Write-Step "Starting ngrok"
    if (-not (Test-Path $NgrokPath)) {
        throw "ngrok was not found at '$NgrokPath'. Pass -NgrokPath with its full location."
    }
    $ngrokRunning = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq "ngrok.exe" -and $_.CommandLine -like "*http*8000*" } |
        Select-Object -First 1
    if ($ngrokRunning) {
        Write-Host "ngrok is already forwarding port 8000." -ForegroundColor Yellow
    }
    else {
        Start-ServiceTerminal `
            "KanbanKaii - ngrok" `
            (Split-Path -Parent $NgrokPath) `
            "& '$NgrokPath' http 8000"
        Write-Host "ngrok terminal opened." -ForegroundColor Green
    }
}
elseif ($TunnelName) {
    Write-Step "Starting Cloudflare Tunnel '$TunnelName'"
    $Cloudflared = Get-Command $CloudflaredPath -ErrorAction SilentlyContinue
    if (-not $Cloudflared) {
        throw "cloudflared was not found. Install it or pass -CloudflaredPath with its full path."
    }
    $tunnelRunning = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*cloudflared*tunnel*run*$TunnelName*" } |
        Select-Object -First 1
    if ($tunnelRunning) {
        Write-Host "Cloudflare Tunnel is already running." -ForegroundColor Yellow
    }
    else {
        Start-ServiceTerminal `
            "KanbanKaii - Cloudflare Tunnel" `
            $ProjectRoot `
            "& '$($Cloudflared.Source)' tunnel run '$TunnelName'"
        Write-Host "Cloudflare Tunnel terminal opened." -ForegroundColor Green
    }
}
else {
    Write-Host "`nPublic tunnel was skipped. Pass -UseNgrok or -TunnelName." -ForegroundColor Yellow
}

Write-Host "`nKanbanKaii local services are started." -ForegroundColor Green
Write-Host "FastAPI: http://127.0.0.1:8000"
Write-Host "Swagger: http://127.0.0.1:8000/docs"
