# AgriVision deploy - build the admin dashboard and start desktop + API together.
#
# Usage (from the repo root):
#   powershell -ExecutionPolicy Bypass -File .\deploy.ps1
#   .\deploy.ps1 -Lan                          # bind 0.0.0.0 so other devices on Wi-Fi can open the dashboard
#   .\deploy.ps1 -SkipBuild                    # reuse web/frontend/dist if it already exists
#   .\deploy.ps1 -SkipDesktop                  # dashboard only
#   .\deploy.ps1 -AdminUser farmer -AdminPassword "change-me"
#
# Optional gitignored file .env.deploy (KEY=VALUE, one per line):
#   AGRIVISION_ADMIN_USER=admin
#   AGRIVISION_ADMIN_PASSWORD=change-me
#   AGRIVISION_SECRET_KEY=long-random-hex

[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [switch]$SkipInstall,
    [switch]$SkipDesktop,
    [switch]$SkipDashboard,
    [switch]$Lan,
    [switch]$NoBrowser,
    [switch]$SkipShortcut,
    [int]$Port = 8077,
    [string]$AdminUser = "",
    [string]$AdminPassword = "",
    [string]$SecretKey = ""
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Hint([string]$Message) {
    Write-Host "    $Message" -ForegroundColor DarkGray
}

function Require-Command([string]$Name, [string]$Hint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found. $Hint"
    }
}

function Import-DotEnv([string]$Path) {
    if (-not (Test-Path $Path)) { return }
    Write-Hint "Loading $Path"
    Get-Content -Path $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
        $existing = [Environment]::GetEnvironmentVariable($key, "Process")
        if ([string]::IsNullOrWhiteSpace($existing)) {
            Set-Item -Path "Env:$key" -Value $val
        }
    }
}

function Escape-PsSingleQuote([string]$Value) {
    if ($null -eq $Value) { return "" }
    return $Value.Replace("'", "''")
}

function Test-PortListening([int]$ListenPort) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $ListenPort -State Listen -ErrorAction SilentlyContinue
        return [bool]$conns
    } catch {
        $client = New-Object System.Net.Sockets.TcpClient
        try {
            $client.Connect("127.0.0.1", $ListenPort)
            return $true
        } catch {
            return $false
        } finally {
            $client.Dispose()
        }
    }
}

function Get-LanIPv4 {
    try {
        $addrs = Get-NetIPConfiguration |
            Where-Object { $_.NetAdapter.Status -eq "Up" -and $null -ne $_.IPv4DefaultGateway } |
            ForEach-Object { $_.IPv4Address.IPAddress } |
            Where-Object { $_ -and $_ -notlike "169.254.*" }
        if ($addrs) { return @($addrs)[0] }
    } catch { }
    try {
        $addrs = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
            Select-Object -ExpandProperty IPAddress
        if ($addrs) { return @($addrs)[0] }
    } catch { }
    return $null
}

# --- prerequisites -----------------------------------------------------------

Write-Step "Checking tools"
Require-Command "py" "Install Python Launcher and Python 3.10 (https://www.python.org/downloads/)."
& py -3.10 -c "import sys; print(sys.version)" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.10 is required (same as run.ps1). Install it, then retry."
}
Write-Hint "Python 3.10 OK"

if (-not $SkipDashboard) {
    Require-Command "npm" "Install Node.js 18+ (https://nodejs.org/) to build the admin dashboard."
    Write-Hint "npm OK"
}

Import-DotEnv (Join-Path $Root ".env.deploy")

if ($AdminUser) { $env:AGRIVISION_ADMIN_USER = $AdminUser }
if ($AdminPassword) { $env:AGRIVISION_ADMIN_PASSWORD = $AdminPassword }
if ($SecretKey) { $env:AGRIVISION_SECRET_KEY = $SecretKey }

if ([string]::IsNullOrWhiteSpace($env:AGRIVISION_ADMIN_USER)) {
    $env:AGRIVISION_ADMIN_USER = "admin"
}
if ([string]::IsNullOrWhiteSpace($env:AGRIVISION_ADMIN_PASSWORD)) {
    $env:AGRIVISION_ADMIN_PASSWORD = "agrivision"
}

$usingDefaultPassword = ($env:AGRIVISION_ADMIN_PASSWORD -eq "agrivision")
if ($usingDefaultPassword) {
    Write-Host ""
    Write-Host "WARNING: using default admin password 'agrivision'." -ForegroundColor Yellow
    Write-Host "         Override with -AdminPassword, env AGRIVISION_ADMIN_PASSWORD, or .env.deploy" -ForegroundColor Yellow
}

# --- Python packages ---------------------------------------------------------

if (-not $SkipInstall) {
    Write-Step "Installing Python packages"
    if (-not $SkipDesktop) {
        & py -3.10 -m pip install -r (Join-Path $Root "requirements.txt")
        if ($LASTEXITCODE -ne 0) { throw "pip install -r requirements.txt failed." }
    }
    if (-not $SkipDashboard) {
        & py -3.10 -m pip install -r (Join-Path $Root "web\requirements.txt")
        if ($LASTEXITCODE -ne 0) { throw "pip install -r web/requirements.txt failed." }
    }
}

# --- frontend build ----------------------------------------------------------

$DistIndex = Join-Path $Root "web\frontend\dist\index.html"
if (-not $SkipDashboard) {
    $needBuild = -not $SkipBuild
    if ($SkipBuild -and -not (Test-Path $DistIndex)) {
        Write-Host "web/frontend/dist is missing; building anyway." -ForegroundColor Yellow
        $needBuild = $true
    }

    if ($needBuild) {
        $frontend = Join-Path $Root "web\frontend"
        Write-Step "Building admin dashboard"
        Push-Location $frontend
        try {
            if (-not $SkipInstall -or -not (Test-Path (Join-Path $frontend "node_modules"))) {
                & npm install
                if ($LASTEXITCODE -ne 0) { throw "npm install failed." }
            }
            & npm run build
            if ($LASTEXITCODE -ne 0) { throw "npm run build failed." }
        } finally {
            Pop-Location
        }
        if (-not (Test-Path $DistIndex)) {
            throw "Frontend build finished but web/frontend/dist/index.html was not created."
        }
    } else {
        Write-Hint "Skipping frontend build (web/frontend/dist already exists)."
    }
}

# --- start dashboard ---------------------------------------------------------

$BindHost = if ($Lan) { "0.0.0.0" } else { "127.0.0.1" }
$DashboardUrl = "http://127.0.0.1:$Port"
$LanIp = $null
if ($Lan) { $LanIp = Get-LanIPv4 }

if (-not $SkipDashboard) {
    if (Test-PortListening $Port) {
        Write-Step "Dashboard already listening on port $Port - reusing it"
    } else {
        Write-Step "Starting admin dashboard on ${BindHost}:$Port"

        $userEsc = Escape-PsSingleQuote $env:AGRIVISION_ADMIN_USER
        $passEsc = Escape-PsSingleQuote $env:AGRIVISION_ADMIN_PASSWORD
        $secretEsc = Escape-PsSingleQuote $env:AGRIVISION_SECRET_KEY
        $rootEsc = Escape-PsSingleQuote $Root

        $dashLines = @(
            "Set-Location '$rootEsc'"
            "`$env:AGRIVISION_ADMIN_USER = '$userEsc'"
            "`$env:AGRIVISION_ADMIN_PASSWORD = '$passEsc'"
        )
        if (-not [string]::IsNullOrWhiteSpace($env:AGRIVISION_SECRET_KEY)) {
            $dashLines += "`$env:AGRIVISION_SECRET_KEY = '$secretEsc'"
        }
        if (-not [string]::IsNullOrWhiteSpace($env:AGRIVISION_OUTPUT_DIR)) {
            $dashLines += "`$env:AGRIVISION_OUTPUT_DIR = '$(Escape-PsSingleQuote $env:AGRIVISION_OUTPUT_DIR)'"
        }
        if (-not [string]::IsNullOrWhiteSpace($env:AGRIVISION_REPORTS_DIR)) {
            $dashLines += "`$env:AGRIVISION_REPORTS_DIR = '$(Escape-PsSingleQuote $env:AGRIVISION_REPORTS_DIR)'"
        }
        $dashLines += "Write-Host ''"
        $dashLines += "Write-Host 'AgriVision admin dashboard' -ForegroundColor Green"
        $dashLines += "Write-Host '  Local  $DashboardUrl'"
        if ($Lan -and $LanIp) {
            $dashLines += "Write-Host '  LAN    http://${LanIp}:$Port'"
        }
        $dashLines += "Write-Host '  Sign in as $userEsc'"
        $dashLines += "Write-Host 'Close this window to stop the dashboard.'"
        $dashLines += "Write-Host ''"
        $dashLines += "py -3.10 -m uvicorn web.api.main:app --host $BindHost --port $Port"

        $shellExe = if ($PSVersionTable.PSEdition -eq "Core") { "pwsh" } else { "powershell" }
        Start-Process -FilePath $shellExe -ArgumentList @(
            "-NoExit",
            "-Command",
            ($dashLines -join "; ")
        ) | Out-Null

        $healthUrl = "${DashboardUrl}/api/health"
        Write-Hint "Waiting for $healthUrl ..."
        $ready = $false
        for ($i = 0; $i -lt 40; $i++) {
            Start-Sleep -Milliseconds 500
            try {
                $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 1
                if ($health.status -eq "ok") {
                    $ready = $true
                    $reportCount = $health.reports_found
                    Write-Hint "API ready ($reportCount reports found)."
                    break
                }
            } catch { }
        }
        if (-not $ready) {
            Write-Host "Dashboard did not respond in time. Check the 'AgriVision admin dashboard' window." -ForegroundColor Yellow
        }
    }

    if (-not $NoBrowser) {
        Start-Process $DashboardUrl | Out-Null
    }
}

# --- desktop shortcut --------------------------------------------------------

if (-not $SkipShortcut) {
    $installShortcut = Join-Path $Root "install_shortcut.ps1"
    if (Test-Path $installShortcut) {
        Write-Step "Installing Desktop shortcut"
        try {
            & $installShortcut
        } catch {
            Write-Host "Could not create Desktop shortcut: $_" -ForegroundColor Yellow
        }
    }
}

# --- start desktop -----------------------------------------------------------

Write-Host ""
Write-Host "--------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Desktop app : python main.py (this window)" -ForegroundColor Green
if (-not $SkipDashboard) {
    Write-Host "  Dashboard   : $DashboardUrl" -ForegroundColor Green
    if ($Lan -and $LanIp) {
        Write-Host "  LAN         : http://${LanIp}:$Port" -ForegroundColor Green
    }
    Write-Host "  Admin user  : $($env:AGRIVISION_ADMIN_USER)" -ForegroundColor Green
}
Write-Host "--------------------------------------------------" -ForegroundColor DarkGray

if ($SkipDesktop) {
    if ($SkipDashboard) {
        Write-Host "Nothing to start (-SkipDesktop and -SkipDashboard)."
        return
    }
    Write-Host ""
    Write-Host "Dashboard is running in its own window. Close that window to stop it."
    return
}

Write-Step "Starting AgriVision desktop app"
Write-Hint "Close the desktop window to exit this script. The dashboard window stays open until you close it."
& py -3.10 (Join-Path $Root "main.py")
if ($LASTEXITCODE -ne 0) {
    throw "Desktop app exited with code ${LASTEXITCODE}."
}
