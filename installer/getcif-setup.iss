; ----------------------------------------------------------------------------
; PolyXRD GetCIF Setup (Inno Setup 6)
;
; Build standard setup:
;   ISCC.exe installer\getcif-setup.iss /DAppVersion=1.2.0 /DAppFlavor=
; Build Plus setup:
;   ISCC.exe installer\getcif-setup.iss /DAppVersion=1.2.0 /DAppFlavor="-Plus"
;
; Output: installer\Output\PolyXRD-GetCIF[-Plus]-Setup.exe
; ----------------------------------------------------------------------------

#ifndef AppVersion
  #define AppVersion "1.2.0"
#endif

#ifndef AppFlavor
  #define AppFlavor ""
#endif

#define MyAppName "PolyXRD-GetCIF" + AppFlavor
#define MyAppExe "PolyXRD-GetCIF" + AppFlavor + ".exe"
#define OutputName "PolyXRD-GetCIF" + AppFlavor + "-Setup"

#if AppFlavor == "-Plus"
  #define AppTitle "PolyXRD GetCIF Plus"
  #define AppDesc "PolyXRD GetCIF Plus (3D preview)"
  #define MyAppId "{{7C1E4B52-8A93-4F6D-9B21-5E0C8D3A7F41}"
  #define SourceDir "..\dist\PolyXRD-GetCIF-Plus"
#else
  #define AppTitle "PolyXRD GetCIF"
  #define AppDesc "PolyXRD GetCIF (Standard)"
  #define MyAppId "{{3A9D6E14-2F58-4C7B-8D19-60B4E2A9C537}"
  #define SourceDir "..\dist\PolyXRD-GetCIF"
#endif

[Setup]
AppId={#MyAppId}
AppName={#AppTitle}
AppVersion={#AppVersion}
AppVerName={#AppTitle} {#AppVersion}
AppPublisher=PolyXRD Team
AppPublisherURL=https://github.com/PolyXRD/PolyXRD-GetCIF
AppSupportURL=https://github.com/PolyXRD/PolyXRD-GetCIF
DefaultDirName={autopf}\PolyXRD\GetCIF{#AppFlavor}
DefaultGroupName=PolyXRD
DisableProgramGroupPage=yes
; Per-user install (no admin/UAC required); user may change the folder.
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename={#OutputName}
SetupIconFile=..\resources\app-icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE-CN
UninstallDisplayName={#AppTitle}
UninstallDisplayIcon={app}\{#MyAppExe}
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppTitle}"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\Uninstall {#AppTitle}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppTitle}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#AppTitle}}"; Flags: nowait postinstall skipifsilent
