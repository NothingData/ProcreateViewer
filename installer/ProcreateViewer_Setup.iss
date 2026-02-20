; ═══════════════════════════════════════════════════════════════════════════
; ProcreateViewer – Professional Inno Setup Installer
; ═══════════════════════════════════════════════════════════════════════════
; One-click installer:
;   ✓ Installs ProcreateViewer.exe application
;   ✓ Installs thumbnail shell extension (Explorer previews)
;   ✓ Registers .procreate file association
;   ✓ Registers COM thumbnail handler
;   ✓ Creates Start Menu & Desktop shortcuts
;   ✓ Full uninstaller included
;
; Build: Open this .iss in Inno Setup Compiler and press Ctrl+F9
;        Or: iscc.exe ProcreateViewer_Setup.iss
;
; Prerequisites: 
;   - dist\ProcreateViewer.exe (built with build.bat)  
;   - dist\ProcreateThumbHandler.dll (compiled C# shell extension)
;   - resources\icon.ico
; ═══════════════════════════════════════════════════════════════════════════

#define MyAppName      "Procreate Viewer"
#define MyAppVersion   "1.0.0"
#define MyAppPublisher "ProcreateViewer (Open Source)"
#define MyAppURL       "https://github.com/NothingData/ProcreateViewer"
#define MyAppExeName   "ProcreateViewer.exe"
#define MyDLLName      "ProcreateThumbHandler.dll"

[Setup]
; Unique identifier
AppId={{B4C5D6E7-F8A9-0B1C-2D3E-4F5A6B7C8D9E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases

; Install directories
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
DisableProgramGroupPage=yes

; Output
OutputDir=..\release
OutputBaseFilename=ProcreateViewer_Setup_v{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes

; Visual
WizardStyle=modern
WizardSizePercent=110,110
SetupIconFile=..\resources\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

; Admin required for COM registration
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

; File association notification
ChangesAssociations=yes
ChangesEnvironment=no

; License
LicenseFile=..\LICENSE

; Branding
AppCopyright=Copyright (c) 2026 ProcreateViewer (MIT License)

; Minimum OS
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "full";    Description: "Full installation (recommended)"
Name: "compact"; Description: "Application only (no Explorer thumbnails)"
Name: "custom";  Description: "Custom installation"; Flags: iscustom

[Components]
Name: "app";      Description: "Procreate Viewer Application";          Types: full compact custom; Flags: fixed
Name: "thumbext"; Description: "Explorer Thumbnail Previews (.procreate → thumbnail in folder views)"; Types: full custom
Name: "assoc";    Description: "File Association (double-click .procreate to open)"; Types: full custom

[Tasks]
Name: "desktopicon";  Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Components: app
Name: "startmenu";    Description: "Create &Start Menu shortcut"; GroupDescription: "Shortcuts:"; Components: app

[Files]
; Main application
Source: "..\dist\ProcreateViewer.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: app

; Shell extension DLL
Source: "..\dist\ProcreateThumbHandler.dll"; DestDir: "{app}"; Flags: ignoreversion; Components: thumbext

; Icon
Source: "..\resources\icon.ico"; DestDir: "{app}"; Flags: ignoreversion; Components: app

; Documentation
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion; Components: app
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion; Components: app

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}";            Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: startmenu
Name: "{group}\Uninstall {#MyAppName}";   Filename: "{uninstallexe}"; Tasks: startmenu

; Desktop
Name: "{autodesktop}\{#MyAppName}";       Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Registry]
; ── File Association ──────────────────────────────────────────────────
; Extension → ProgID
Root: HKCR; Subkey: ".procreate";                         ValueType: string; ValueName: "";             ValueData: "ProcreateViewer.procreate"; Flags: uninsdeletevalue; Components: assoc
Root: HKCR; Subkey: ".procreate";                         ValueType: string; ValueName: "Content Type"; ValueData: "application/x-procreate";    Components: assoc
Root: HKCR; Subkey: ".procreate";                         ValueType: string; ValueName: "PerceivedType"; ValueData: "image";                     Components: assoc

; ProgID → Description & Icons
Root: HKCR; Subkey: "ProcreateViewer.procreate";          ValueType: string; ValueName: "";             ValueData: "Procreate Artwork";         Flags: uninsdeletekey; Components: assoc
Root: HKCR; Subkey: "ProcreateViewer.procreate\DefaultIcon"; ValueType: string; ValueName: "";          ValueData: "{app}\icon.ico,0";          Components: assoc
Root: HKCR; Subkey: "ProcreateViewer.procreate\shell\open\command"; ValueType: string; ValueName: "";  ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Components: assoc
Root: HKCR; Subkey: "ProcreateViewer.procreate\shell\open"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#MyAppName}";          Components: assoc

; OpenWithProgids
Root: HKCR; Subkey: ".procreate\OpenWithProgids";         ValueType: none;   ValueName: "ProcreateViewer.procreate"; Flags: uninsdeletevalue;   Components: assoc

; Context menu
Root: HKCR; Subkey: ".procreate\shell\ProcreateViewer";           ValueType: string; ValueName: "";     ValueData: "Open with Procreate Viewer"; Components: assoc
Root: HKCR; Subkey: ".procreate\shell\ProcreateViewer";           ValueType: string; ValueName: "Icon"; ValueData: "{app}\icon.ico";              Components: assoc
Root: HKCR; Subkey: ".procreate\shell\ProcreateViewer\command";   ValueType: string; ValueName: "";     ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Components: assoc

; Current user classes (fallback)
Root: HKCU; Subkey: "Software\Classes\.procreate";                            ValueType: string; ValueName: ""; ValueData: "ProcreateViewer.procreate"; Components: assoc
Root: HKCU; Subkey: "Software\Classes\ProcreateViewer.procreate\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Components: assoc

; ── Thumbnail Handler Registration ────────────────────────────────────
; ShellEx → Thumbnail GUID → our CLSID
Root: HKCR; Subkey: ".procreate\ShellEx\{{e357fccd-a995-4576-b01f-234630154e96}";       ValueType: string; ValueName: ""; ValueData: "{{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}"; Components: thumbext
Root: HKLM; Subkey: "Software\Classes\.procreate\ShellEx\{{e357fccd-a995-4576-b01f-234630154e96}"; ValueType: string; ValueName: ""; ValueData: "{{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}"; Components: thumbext

; CLSID registration
Root: HKCR; Subkey: "CLSID\{{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}";                        ValueType: string; ValueName: "";                        ValueData: "Procreate Thumbnail Handler"; Components: thumbext
Root: HKCR; Subkey: "CLSID\{{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}";                        ValueType: dword;  ValueName: "DisableProcessIsolation"; ValueData: "1";                            Components: thumbext
Root: HKCR; Subkey: "CLSID\{{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}\Implemented Categories\{{62C8FE65-4EBB-45e7-B440-6E39B2CDBF29}"; ValueType: none; ValueName: ""; Components: thumbext

; Approved shell extensions
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Approved";  ValueType: string; ValueName: "{{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}"; ValueData: "Procreate Thumbnail Handler"; Components: thumbext

[Run]
; Register COM DLL with RegAsm (64-bit)
Filename: "{dotnet4064}\RegAsm.exe"; Parameters: "/codebase ""{app}\ProcreateThumbHandler.dll"""; StatusMsg: "Registering thumbnail preview handler..."; Flags: runhidden waituntilterminated; Components: thumbext

; Register COM DLL with RegAsm (32-bit)  
Filename: "{dotnet4032}\RegAsm.exe"; Parameters: "/codebase ""{app}\ProcreateThumbHandler.dll"""; StatusMsg: "Registering thumbnail handler (32-bit)..."; Flags: runhidden waituntilterminated skipifdoesntexist; Components: thumbext

; Clear thumbnail cache
Filename: "cmd.exe"; Parameters: "/c del /f /q ""%LOCALAPPDATA%\Microsoft\Windows\Explorer\thumbcache_*.db"" 2>nul & del /f /q ""%LOCALAPPDATA%\Microsoft\Windows\Explorer\iconcache_*.db"" 2>nul"; StatusMsg: "Clearing thumbnail cache..."; Flags: runhidden waituntilterminated; Components: thumbext

; Restart Explorer so new thumbnail handler + file associations take effect immediately
Filename: "cmd.exe"; Parameters: "/c taskkill /f /im explorer.exe & timeout /t 2 /nobreak >nul & start explorer.exe"; StatusMsg: "Restarting Windows Explorer..."; Flags: runhidden waituntilterminated

; Launch application after install
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Unregister COM DLL before removal
Filename: "{dotnet4064}\RegAsm.exe"; Parameters: "/unregister ""{app}\ProcreateThumbHandler.dll"""; Flags: runhidden waituntilterminated; RunOnceId: "UnregDLL64"
Filename: "{dotnet4032}\RegAsm.exe"; Parameters: "/unregister ""{app}\ProcreateThumbHandler.dll"""; Flags: runhidden waituntilterminated skipifdoesntexist; RunOnceId: "UnregDLL32"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
// ═══════════════════════════════════════════════════════════════════════
// Pascal Script: Custom progress UI + post-install actions
// ═══════════════════════════════════════════════════════════════════════

// Notify Explorer of file association changes
procedure SHChangeNotify(wEventId: Cardinal; uFlags: Cardinal; dwItem1: Cardinal; dwItem2: Cardinal);
  external 'SHChangeNotify@shell32.dll stdcall';

// Manual InprocServer32 registration to ensure it exists
procedure EnsureInprocServer32;
var
  DllPath: String;
  CodeBase: String;
begin
  DllPath := ExpandConstant('{app}\ProcreateThumbHandler.dll');
  CodeBase := 'file:///' + DllPath;
  StringChangeEx(CodeBase, '\', '/', True);

  // HKCR\CLSID\{...}\InprocServer32
  RegWriteStringValue(HKEY_CLASSES_ROOT,
    'CLSID\{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}\InprocServer32',
    '', 'mscoree.dll');
  RegWriteStringValue(HKEY_CLASSES_ROOT,
    'CLSID\{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}\InprocServer32',
    'Class', 'ProcreateThumbHandler.ProcreateThumbProvider');
  RegWriteStringValue(HKEY_CLASSES_ROOT,
    'CLSID\{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}\InprocServer32',
    'CodeBase', CodeBase);
  RegWriteStringValue(HKEY_CLASSES_ROOT,
    'CLSID\{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}\InprocServer32',
    'RuntimeVersion', 'v4.0.30319');
  RegWriteStringValue(HKEY_CLASSES_ROOT,
    'CLSID\{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}\InprocServer32',
    'ThreadingModel', 'Both');
  RegWriteStringValue(HKEY_CLASSES_ROOT,
    'CLSID\{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}\InprocServer32',
    'Assembly', 'ProcreateThumbHandler, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null');

  // Also under HKLM
  RegWriteStringValue(HKEY_LOCAL_MACHINE,
    'Software\Classes\CLSID\{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}\InprocServer32',
    '', 'mscoree.dll');
  RegWriteStringValue(HKEY_LOCAL_MACHINE,
    'Software\Classes\CLSID\{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}\InprocServer32',
    'Class', 'ProcreateThumbHandler.ProcreateThumbProvider');
  RegWriteStringValue(HKEY_LOCAL_MACHINE,
    'Software\Classes\CLSID\{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}\InprocServer32',
    'CodeBase', CodeBase);
  RegWriteStringValue(HKEY_LOCAL_MACHINE,
    'Software\Classes\CLSID\{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}\InprocServer32',
    'RuntimeVersion', 'v4.0.30319');
  RegWriteStringValue(HKEY_LOCAL_MACHINE,
    'Software\Classes\CLSID\{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}\InprocServer32',
    'ThreadingModel', 'Both');
  RegWriteStringValue(HKEY_LOCAL_MACHINE,
    'Software\Classes\CLSID\{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}\InprocServer32',
    'Assembly', 'ProcreateThumbHandler, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  MarkerPath: String;
begin
  if CurStep = ssPostInstall then
  begin
    // Ensure InprocServer32 is fully written (belt + suspenders)
    if WizardIsComponentSelected('thumbext') then
    begin
      EnsureInprocServer32;
    end;

    // Create .procreate_installed marker so the app skips its
    // own first-run setup dialog (the installer already did everything).
    MarkerPath := ExpandConstant('{app}\.procreate_installed');
    SaveStringToFile(MarkerPath, ExpandConstant('{app}\{#MyAppExeName}'), False);

    // Also create .setup_log.txt so the app sees a clean state
    SaveStringToFile(ExpandConstant('{app}\.setup_log.txt'), 'Installed via Setup ' + '{#MyAppVersion}', False);

    // Notify Explorer of changes
    SHChangeNotify($08000000, 0, 0, 0);
  end;
end;

// Clean up on uninstall
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // Clean up CLSID
    RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT,
      'CLSID\{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}');
    RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE,
      'Software\Classes\CLSID\{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}');

    // Clean up ShellEx
    RegDeleteKeyIncludingSubkeys(HKEY_CLASSES_ROOT,
      '.procreate\ShellEx');
    RegDeleteKeyIncludingSubkeys(HKEY_LOCAL_MACHINE,
      'Software\Classes\.procreate\ShellEx');

    // Remove from Approved
    RegDeleteValue(HKEY_LOCAL_MACHINE,
      'Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Approved',
      '{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}');

    // Notify Explorer
    SHChangeNotify($08000000, 0, 0, 0);
  end;
end;

// Custom welcome page text
function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo,
  MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
  Result := '';
  Result := Result + 'Installation Summary:' + NewLine + NewLine;

  if MemoDirInfo <> '' then
    Result := Result + MemoDirInfo + NewLine + NewLine;

  if MemoComponentsInfo <> '' then
    Result := Result + MemoComponentsInfo + NewLine + NewLine;

  if MemoTasksInfo <> '' then
    Result := Result + MemoTasksInfo + NewLine + NewLine;

  Result := Result + 'What will be configured:' + NewLine;
  Result := Result + Space + '• ProcreateViewer.exe application' + NewLine;

  if WizardIsComponentSelected('assoc') then
    Result := Result + Space + '• .procreate file association (double-click to open)' + NewLine;

  if WizardIsComponentSelected('thumbext') then
    Result := Result + Space + '• Explorer thumbnail previews (like .png thumbnails)' + NewLine;

  Result := Result + NewLine;
  Result := Result + 'Note: A restart of Windows Explorer may be needed' + NewLine;
  Result := Result + 'for thumbnail previews to appear.' + NewLine;
end;
