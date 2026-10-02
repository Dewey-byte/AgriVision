; Inno Setup script for AgriVision.
; Build the app first (PyInstaller -> dist\AgriVision), then:
;   ISCC installer\AgriVision.iss
; Output: installer\Output\AgriVisionSetup.exe

#define AppName "AgriVision"
#define AppVersion "1.0.0"
#define AppExe "AgriVision.exe"

[Setup]
AppId={{E3FA9933-B902-44B5-84B4-F876C1E1E905}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=AgriVision
; Per-user dir: the app writes output/ next to the exe, so it must be user-writable.
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=AgriVisionSetup
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#AppExe}
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\AgriVision\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Reports/sessions/maps written at runtime are left in place on purpose.
Type: filesandordirs; Name: "{app}\output\cache"
