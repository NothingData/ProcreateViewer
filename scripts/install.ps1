<# 
.SYNOPSIS
    ProcreateViewer - One-Click Install Script
    Run this to install everything without Inno Setup.

.DESCRIPTION
    This PowerShell script installs ProcreateViewer with:
    - File association (.procreate -> ProcreateViewer)  
    - Explorer thumbnail previews
    - Desktop shortcut
    - Start Menu shortcut
    
    Must be run as Administrator!

.NOTES
    License: MIT
    GitHub: https://github.com/NothingData/ProcreateViewer
#>

param(
    [string]$InstallDir = "$env:ProgramFiles\Procreate Viewer"
)

# ===================================================================
# Check Admin
# ===================================================================
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host ""
    Write-Host "  Requesting Administrator privileges..." -ForegroundColor Yellow
    Write-Host ""
    $scriptPath = $MyInvocation.MyCommand.Path
    Start-Process -Verb RunAs -FilePath powershell.exe -ArgumentList "-ExecutionPolicy Bypass -File `"$scriptPath`" -InstallDir `"$InstallDir`""
    exit
}

# ===================================================================
# CONFIG
# ===================================================================
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$distDir = Join-Path $projectDir "dist"
$resDir = Join-Path $projectDir "resources"

$exeName = "ProcreateViewer.exe"
$dllName = "ProcreateThumbHandler.dll"
$iconName = "icon.ico"
$clsid = "{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}"
$thumbGuid = "{e357fccd-a995-4576-b01f-234630154e96}"
$ext = ".procreate"
$progId = "ProcreateViewer.procreate"

$exeSrc = Join-Path $distDir $exeName
$dllSrc = Join-Path $distDir $dllName
$iconSrc = Join-Path $resDir $iconName

# ===================================================================
# BANNER
# ===================================================================

# Force UTF-8 output for consistent display
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Clear-Host
Write-Host ""
Write-Host "  +================================================+" -ForegroundColor Cyan
Write-Host "  |                                                |" -ForegroundColor Cyan
Write-Host "  |      ProcreateViewer Installer v1.0.0          |" -ForegroundColor Cyan
Write-Host "  |                                                |" -ForegroundColor Cyan
Write-Host "  |  Preview .procreate files on Windows!          |" -ForegroundColor Cyan
Write-Host "  |                                                |" -ForegroundColor Cyan
Write-Host "  +================================================+" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Install directory: $InstallDir" -ForegroundColor White
Write-Host ""

# ===================================================================
# PROGRESS BAR HELPER
# ===================================================================
function Show-Progress {
    param([string]$Activity, [string]$Status, [int]$Percent)
    Write-Progress -Activity $Activity -Status $Status -PercentComplete $Percent
}

# ===================================================================
# VERIFY FILES
# ===================================================================
Show-Progress "Installing ProcreateViewer" "Checking files..." 0

$missing = @()
if (-not (Test-Path $exeSrc)) { $missing += $exeName }
if (-not (Test-Path $dllSrc)) { Write-Host "  Note: $dllName not found - thumbnails won't be installed" -ForegroundColor Yellow }
if (-not (Test-Path $iconSrc)) { $missing += $iconName }

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "  ERROR: Missing required files:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "    - $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "  Run 'build.bat' first to build from source." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit 1
}

$hasDLL = Test-Path $dllSrc

# ===================================================================
# STEP 1: Copy Files
# ===================================================================
$step = 1
$totalSteps = if ($hasDLL) { 7 } else { 5 }

Show-Progress "Installing ProcreateViewer" "[$step/$totalSteps] Copying files..." ([int](($step/$totalSteps)*100))
Write-Host "  [$step/$totalSteps] Copying files to $InstallDir..." -ForegroundColor Yellow

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Copy-Item -Path $exeSrc -Destination $InstallDir -Force
Copy-Item -Path $iconSrc -Destination $InstallDir -Force
if ($hasDLL) {
    Copy-Item -Path $dllSrc -Destination $InstallDir -Force
}
# Copy docs
$readme = Join-Path $projectDir "README.md"
$license = Join-Path $projectDir "LICENSE"
if (Test-Path $readme) { Copy-Item -Path $readme -Destination $InstallDir -Force }
if (Test-Path $license) { Copy-Item -Path $license -Destination $InstallDir -Force }

Write-Host "    Copied to $InstallDir" -ForegroundColor Green
$step++

# ===================================================================
# STEP 2: File Association
# ===================================================================
Show-Progress "Installing ProcreateViewer" "[$step/$totalSteps] Setting file association..." ([int](($step/$totalSteps)*100))
Write-Host "  [$step/$totalSteps] Registering .procreate file association..." -ForegroundColor Yellow

New-PSDrive -PSProvider Registry -Root HKEY_CLASSES_ROOT -Name HKCR -ErrorAction SilentlyContinue | Out-Null

$viewerExe = Join-Path $InstallDir $exeName
$iconPath = Join-Path $InstallDir $iconName
$openCmd = "`"$viewerExe`" `"%1`""

# ProgID
New-Item -Path "HKCR:\$progId" -Force | Out-Null
Set-ItemProperty -Path "HKCR:\$progId" -Name "(Default)" -Value "Procreate Artwork"
New-Item -Path "HKCR:\$progId\DefaultIcon" -Force | Out-Null
Set-ItemProperty -Path "HKCR:\$progId\DefaultIcon" -Name "(Default)" -Value "`"$iconPath`",0"
New-Item -Path "HKCR:\$progId\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path "HKCR:\$progId\shell\open\command" -Name "(Default)" -Value $openCmd
Set-ItemProperty -Path "HKCR:\$progId\shell\open" -Name "FriendlyAppName" -Value "Procreate Viewer" -Force

# Extension
New-Item -Path "HKCR:\$ext" -Force | Out-Null
Set-ItemProperty -Path "HKCR:\$ext" -Name "(Default)" -Value $progId
Set-ItemProperty -Path "HKCR:\$ext" -Name "Content Type" -Value "application/x-procreate"
Set-ItemProperty -Path "HKCR:\$ext" -Name "PerceivedType" -Value "image"

# OpenWithProgids
New-Item -Path "HKCR:\$ext\OpenWithProgids" -Force | Out-Null
New-ItemProperty -Path "HKCR:\$ext\OpenWithProgids" -Name $progId -PropertyType None -Force -ErrorAction SilentlyContinue | Out-Null

# Context menu
New-Item -Path "HKCR:\$ext\shell\ProcreateViewer\command" -Force | Out-Null
Set-ItemProperty -Path "HKCR:\$ext\shell\ProcreateViewer" -Name "(Default)" -Value "Open with Procreate Viewer"
Set-ItemProperty -Path "HKCR:\$ext\shell\ProcreateViewer" -Name "Icon" -Value $iconPath
Set-ItemProperty -Path "HKCR:\$ext\shell\ProcreateViewer\command" -Name "(Default)" -Value $openCmd

# Current user
New-Item -Path "HKCU:\Software\Classes\$ext" -Force | Out-Null
Set-ItemProperty -Path "HKCU:\Software\Classes\$ext" -Name "(Default)" -Value $progId
New-Item -Path "HKCU:\Software\Classes\$progId\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path "HKCU:\Software\Classes\$progId\shell\open\command" -Name "(Default)" -Value $openCmd

Write-Host "    .procreate -> Procreate Viewer" -ForegroundColor Green
$step++

# ===================================================================
# STEP 3: Register thumbnail handler DLL
# ===================================================================
if ($hasDLL) {
    Show-Progress "Installing ProcreateViewer" "[$step/$totalSteps] Registering thumbnail handler..." ([int](($step/$totalSteps)*100))
    Write-Host "  [$step/$totalSteps] Registering thumbnail preview handler..." -ForegroundColor Yellow

    $dllInstalled = Join-Path $InstallDir $dllName
    
    # RegAsm
    $regasm64 = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe"
    $regasm32 = "C:\Windows\Microsoft.NET\Framework\v4.0.30319\RegAsm.exe"
    
    if (Test-Path $regasm64) {
        & $regasm64 /codebase $dllInstalled 2>&1 | Out-Null
    }
    if (Test-Path $regasm32) {
        & $regasm32 /codebase $dllInstalled 2>&1 | Out-Null
    }

    # Manual InprocServer32
    $codeBase = "file:///$($dllInstalled.Replace('\','/'))"
    $asmName = "ProcreateThumbHandler, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null"

    foreach ($root in @("HKCR:\CLSID\$clsid\InprocServer32", "HKLM:\Software\Classes\CLSID\$clsid\InprocServer32")) {
        New-Item -Path $root -Force | Out-Null
        Set-ItemProperty -Path $root -Name "(Default)" -Value "mscoree.dll"
        Set-ItemProperty -Path $root -Name "Assembly" -Value $asmName
        Set-ItemProperty -Path $root -Name "Class" -Value "ProcreateThumbHandler.ProcreateThumbProvider"
        Set-ItemProperty -Path $root -Name "CodeBase" -Value $codeBase
        Set-ItemProperty -Path $root -Name "RuntimeVersion" -Value "v4.0.30319"
        Set-ItemProperty -Path $root -Name "ThreadingModel" -Value "Both"
    }

    # CLSID properties
    Set-ItemProperty -Path "HKCR:\CLSID\$clsid" -Name "(Default)" -Value "Procreate Thumbnail Handler"
    Set-ItemProperty -Path "HKCR:\CLSID\$clsid" -Name "DisableProcessIsolation" -Value 1 -Type DWord

    # Implemented Categories
    New-Item -Path "HKCR:\CLSID\$clsid\Implemented Categories\{62C8FE65-4EBB-45e7-B440-6E39B2CDBF29}" -Force | Out-Null

    Write-Host "    COM handler registered" -ForegroundColor Green
    $step++

    # ===================================================================
    # STEP 4: Shell extension registration
    # ===================================================================
    Show-Progress "Installing ProcreateViewer" "[$step/$totalSteps] Registering shell extension..." ([int](($step/$totalSteps)*100))
    Write-Host "  [$step/$totalSteps] Registering Explorer shell extension..." -ForegroundColor Yellow

    # ShellEx
    New-Item -Path "HKCR:\$ext\ShellEx\$thumbGuid" -Force | Out-Null
    Set-ItemProperty -Path "HKCR:\$ext\ShellEx\$thumbGuid" -Name "(Default)" -Value $clsid
    New-Item -Path "HKLM:\Software\Classes\$ext\ShellEx\$thumbGuid" -Force | Out-Null
    Set-ItemProperty -Path "HKLM:\Software\Classes\$ext\ShellEx\$thumbGuid" -Name "(Default)" -Value $clsid

    # Approved
    $approvedPath = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Approved"
    if (Test-Path $approvedPath) {
        Set-ItemProperty -Path $approvedPath -Name $clsid -Value "Procreate Thumbnail Handler"
    }

    Write-Host "    Thumbnail provider linked to .procreate" -ForegroundColor Green
    $step++
}

# ===================================================================
# STEP N-1: Create Shortcuts
# ===================================================================
Show-Progress "Installing ProcreateViewer" "[$step/$totalSteps] Creating shortcuts..." ([int](($step/$totalSteps)*100))
Write-Host "  [$step/$totalSteps] Creating shortcuts..." -ForegroundColor Yellow

$WshShell = New-Object -ComObject WScript.Shell

# Desktop shortcut
$desktopLink = Join-Path ([Environment]::GetFolderPath("Desktop")) "Procreate Viewer.lnk"
$shortcut = $WshShell.CreateShortcut($desktopLink)
$shortcut.TargetPath = $viewerExe
$shortcut.IconLocation = $iconPath
$shortcut.Description = "View and preview .procreate files"
$shortcut.WorkingDirectory = $InstallDir
$shortcut.Save()

# Start Menu shortcut
$startMenuDir = Join-Path ([Environment]::GetFolderPath("Programs")) "Procreate Viewer"
New-Item -ItemType Directory -Path $startMenuDir -Force | Out-Null
$startLink = Join-Path $startMenuDir "Procreate Viewer.lnk"
$shortcut = $WshShell.CreateShortcut($startLink)
$shortcut.TargetPath = $viewerExe
$shortcut.IconLocation = $iconPath
$shortcut.Description = "View and preview .procreate files"
$shortcut.WorkingDirectory = $InstallDir
$shortcut.Save()

Write-Host "    Desktop + Start Menu shortcuts created" -ForegroundColor Green
$step++

# ===================================================================
# STEP N: Finalize
# ===================================================================
Show-Progress "Installing ProcreateViewer" "[$step/$totalSteps] Finalizing..." ([int](($step/$totalSteps)*100))
Write-Host "  [$step/$totalSteps] Finalizing..." -ForegroundColor Yellow

# Clear thumbnail cache
Stop-Process -Name "dllhost" -Force -ErrorAction SilentlyContinue
$explorerCache = "$env:LOCALAPPDATA\Microsoft\Windows\Explorer"
Get-ChildItem "$explorerCache\thumbcache_*.db" -ErrorAction SilentlyContinue | ForEach-Object {
    try { Remove-Item $_.FullName -Force } catch {}
}

# Notify Explorer
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class ShellNotify {
    [DllImport("shell32.dll")]
    public static extern void SHChangeNotify(uint wEventId, uint uFlags, IntPtr dwItem1, IntPtr dwItem2);
}
"@ -ErrorAction SilentlyContinue
[ShellNotify]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)

# Save uninstall info
$uninstallInfo = @{
    InstallDir = $InstallDir
    HasDLL = $hasDLL
    Version = "1.0.0"
    Date = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
} | ConvertTo-Json
$uninstallInfo | Out-File (Join-Path $InstallDir "install_info.json") -Force

Write-Progress -Activity "Installing ProcreateViewer" -Completed

# ===================================================================
# DONE
# ===================================================================
Write-Host ""
Write-Host "  +================================================+" -ForegroundColor Green
Write-Host "  |                                                |" -ForegroundColor Green
Write-Host "  |     [OK] INSTALLATION COMPLETE!                |" -ForegroundColor Green
Write-Host "  |                                                |" -ForegroundColor Green
Write-Host "  +------------------------------------------------+" -ForegroundColor Green
Write-Host "  |                                                |" -ForegroundColor Green
Write-Host "  |  [OK] ProcreateViewer.exe installed            |" -ForegroundColor Green
Write-Host "  |  [OK] .procreate file association set          |" -ForegroundColor Green
if ($hasDLL) {
Write-Host "  |  [OK] Explorer thumbnail preview registered    |" -ForegroundColor Green
}
Write-Host "  |  [OK] Desktop shortcut created                 |" -ForegroundColor Green
Write-Host "  |  [OK] Start Menu shortcut created              |" -ForegroundColor Green
Write-Host "  |                                                |" -ForegroundColor Green
Write-Host "  |  Note: Restart Explorer or sign out/in         |" -ForegroundColor Yellow
Write-Host "  |  for thumbnail previews to appear.             |" -ForegroundColor Yellow
Write-Host "  |                                                |" -ForegroundColor Green
Write-Host "  +================================================+" -ForegroundColor Green
Write-Host ""

$launch = Read-Host "  Launch Procreate Viewer now? (Y/n)"
if ($launch -ne "n" -and $launch -ne "N") {
    Start-Process $viewerExe
}
