; Script do Inno Setup para o LegendAI.
; Compile com: ISCC.exe installer\LegendAI.iss (a partir da raiz do projeto).

#define AppName "LegendAI"
#define AppVersion "2.0.0"
#define AppPublisher "LegendAI"
#define AppExe "LegendAI.exe"

[Setup]
AppId={{B7E4B3A2-1C4D-4F6E-9A2B-3F8A1D2E5C60}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist_installer
OutputBaseFilename=LegendAI-Setup-{#AppVersion}
SetupIconFile=..\assets\legendai.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=none
SolidCompression=no
DiskSpanning=yes
DiskSliceSize=2000000000
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; O bundle tem ~6,6 GB descompactado; exige privilégio para Arquivos de Programas.
PrivilegesRequired=admin

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Empacota o Electron e o motor Python local já incluído em resources\engine.
Source: "..\release-electron\win-unpacked\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
