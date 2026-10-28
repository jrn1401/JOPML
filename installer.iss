; Inno Setup Skript fuer Jaron's OP Makro Launcher (JOPML).
; Voraussetzung: dist\JaronsOPMakro.exe wurde mit EXE_BAUEN.bat gebaut. Inno Setup: https://jrsoftware.org/isinfo.php
#define AppName "Jaron's OP Makro"
#define AppExe "JaronsOPMakro.exe"
#ifndef AppVersion
  #define AppVersion "1.5.4"
#endif

[Setup]
AppId={{6E0B3C52-6F3A-4B9E-9A55-0F1A4C7D2B11}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\JaronsOPMakro
DefaultGroupName={#AppName}
OutputDir=dist
OutputBaseFilename=JaronsOPMakro-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#AppExe}
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknuepfung erstellen"; GroupDescription: "Zusaetzliche Symbole:"

[Files]
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{#AppName} starten"; Flags: nowait postinstall skipifsilent
