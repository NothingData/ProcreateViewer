<# 
.SYNOPSIS
    ProcreateViewer - Uninstaller Script

.DESCRIPTION
    Removes ProcreateViewer, file associations, thumbnail handler, and shortcuts.
    Must be run as Administrator.
#>

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process -Verb RunAs -FilePath powershell.exe -ArgumentList "-ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Path)`""
    exit
}

$ErrorActionPreference = "SilentlyContinue"

$InstallDir = "$env:ProgramFiles\Procreate Viewer"
$clsid = "{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}"
$thumbGuid = "{e357fccd-a995-4576-b01f-234630154e96}"
$ext = ".procreate"
$progId = "ProcreateViewer.procreate"

# Check for saved install info
$infoFile = Join-Path $InstallDir "install_info.json"
if (Test-Path $infoFile) {
    $info = Get-Content $infoFile | ConvertFrom-Json
    $InstallDir = $info.InstallDir
}

Clear-Host
Write-Host ""
Write-Host "  +================================================+" -ForegroundColor Red
Write-Host "  |      ProcreateViewer Uninstaller                |" -ForegroundColor Red
Write-Host "  +================================================+" -ForegroundColor Red
Write-Host ""

$confirm = Read-Host "  Remove ProcreateViewer completely? (y/N)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "  Cancelled." -ForegroundColor Yellow
    exit
}

New-PSDrive -PSProvider Registry -Root HKEY_CLASSES_ROOT -Name HKCR -ErrorAction SilentlyContinue | Out-Null

Write-Host ""
Write-Host "  [1/6] Unregistering COM DLL..." -ForegroundColor Yellow

$dllPath = Join-Path $InstallDir "ProcreateThumbHandler.dll"
$regasm64 = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe"
if ((Test-Path $regasm64) -and (Test-Path $dllPath)) {
    & $regasm64 /unregister $dllPath 2>&1 | Out-Null
}

Write-Host "  [2/6] Removing CLSID entries..." -ForegroundColor Yellow
Remove-Item -Path "HKCR:\CLSID\$clsid" -Recurse -Force
Remove-Item -Path "HKLM:\Software\Classes\CLSID\$clsid" -Recurse -Force

Write-Host "  [3/6] Removing shell extension..." -ForegroundColor Yellow
Remove-Item -Path "HKCR:\$ext\ShellEx" -Recurse -Force
Remove-Item -Path "HKLM:\Software\Classes\$ext\ShellEx" -Recurse -Force
$approvedPath = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Approved"
Remove-ItemProperty -Path $approvedPath -Name $clsid -Force

Write-Host "  [4/6] Removing file association..." -ForegroundColor Yellow
Remove-Item -Path "HKCR:\$ext" -Recurse -Force
Remove-Item -Path "HKCR:\$progId" -Recurse -Force
Remove-Item -Path "HKCU:\Software\Classes\$ext" -Recurse -Force
Remove-Item -Path "HKCU:\Software\Classes\$progId" -Recurse -Force

Write-Host "  [5/6] Removing shortcuts..." -ForegroundColor Yellow
$desktopLink = Join-Path ([Environment]::GetFolderPath("Desktop")) "Procreate Viewer.lnk"
Remove-Item -Path $desktopLink -Force
$startMenuDir = Join-Path ([Environment]::GetFolderPath("Programs")) "Procreate Viewer"
Remove-Item -Path $startMenuDir -Recurse -Force

Write-Host "  [6/6] Removing files..." -ForegroundColor Yellow
Remove-Item -Path $InstallDir -Recurse -Force

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

Write-Host ""
Write-Host "  [OK] ProcreateViewer has been completely removed." -ForegroundColor Green
Write-Host ""
Read-Host "  Press Enter to close"
