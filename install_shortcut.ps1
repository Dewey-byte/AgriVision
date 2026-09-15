# Create a Desktop (and Start Menu) shortcut that launches AgriVision.
# Double-click:  Install Desktop Shortcut.bat
# Or:            powershell -ExecutionPolicy Bypass -File .\install_shortcut.ps1

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Vbs = Join-Path $Root "AgriVision.vbs"
if (-not (Test-Path $Vbs)) {
    throw "AgriVision.vbs was not found next to this script."
}

$Wsh = New-Object -ComObject WScript.Shell

function Install-AgriVisionShortcut([string]$Directory) {
    if (-not (Test-Path $Directory)) {
        New-Item -ItemType Directory -Path $Directory | Out-Null
    }
    $path = Join-Path $Directory "AgriVision.lnk"
    $sc = $Wsh.CreateShortcut($path)
    $sc.TargetPath = Join-Path $env:SystemRoot "System32\wscript.exe"
    $sc.Arguments = "`"$Vbs`""
    $sc.WorkingDirectory = $Root
    $sc.WindowStyle = 1
    $sc.Description = "AgriVision - banana disease detection"
    $sc.Save()
    return $path
}

$desktop = [Environment]::GetFolderPath("Desktop")
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$desktopLink = Install-AgriVisionShortcut $desktop
$startLink = Install-AgriVisionShortcut $startMenu

Write-Host "Shortcut created:"
Write-Host "  $desktopLink"
Write-Host "  $startLink"
Write-Host ""
Write-Host "Double-click AgriVision on the Desktop to open the system."
