; Inno-Setup-Skript für JaronsOPMakro-Setup.exe (wird von .github/workflows/release.yml gebaut).
; Installiert ohne Administratorrechte in den Benutzerordner, damit das Auto-Update die EXE ersetzen kann.
; Lokal bauen:  iscc /DAppVersion=1.5.3 installer\JaronsOPMakro.iss   (vorher EXE_BAUEN.bat und tools/make_icon.py)
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{2908D8A6-4BC3-434B-A105-3EF5416887A7}
AppName=Jaron's OP Makro
AppVersion={#AppVersion}
AppVerName=Jaron's OP Makro {#AppVersion}
AppPublisher=Jaron
DefaultDirName={autopf}\JaronsOPMakro
DefaultGroupName=Jaron's OP Makro
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=JaronsOPMakro-Setup
SetupIconFile=..\build\icon.ico
UninstallDisplayIcon={app}\JaronsOPMakro.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\JaronsOPMakro.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Jaron's OP Makro"; Filename: "{app}\JaronsOPMakro.exe"
Name: "{group}\{cm:UninstallProgram,Jaron's OP Makro}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Jaron's OP Makro"; Filename: "{app}\JaronsOPMakro.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\JaronsOPMakro.exe"; Description: "{cm:LaunchProgram,Jaron's OP Makro}"; Flags: nowait postinstall skipifsilent
