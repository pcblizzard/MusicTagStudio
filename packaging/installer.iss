; Inno Setup Skript für MusicTagStudio
; Packt den PyInstaller-Build (dist/MusicTagStudio/) zu einem Setup.
;
; Voraussetzung: vorher bauen ->
;   py -3 -m PyInstaller packaging/musictagstudio.spec --noconfirm
; Dann dieses Skript in Inno Setup öffnen und "Compile" (oder ISCC aufrufen):
;   "C:\Program Files\Inno Setup 7\ISCC.exe" packaging\installer.iss
;
; Pfade sind relativ zu diesem Skript (SourceDir), damit der Build auf jedem
; Rechner ohne Anpassung funktioniert.

#define MyAppName "MusicTagStudio"
#define MyAppVersion "0.8.6"
#define MyAppPublisher "Michael (pcblizzard)"
#define MyAppURL "https://github.com/pcblizzard/MusicTagStudio"
#define MyAppExeName "MusicTagStudio.exe"
; Ordner mit dem PyInstaller-Ergebnis (relativ zu diesem Skript: ../dist/...)
#define BuildDir "..\dist\MusicTagStudio"

[Setup]
; Eindeutige AppId (aus dem Wizard übernommen) - NICHT für andere Apps nutzen.
AppId={{A9EC9B42-95E5-4DDD-A806-A11E0BE2D847}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
AllowNoIcons=yes
; Standardmäßig für alle Nutzer (Programme-Ordner). Nutzer kann im Dialog auf
; "nur für mich" wechseln; Nutzerdaten liegen ohnehin in %LOCALAPPDATA%.
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputBaseFilename=MusicTagStudio-Setup
; Ausgabeordner des fertigen Setups (relativ zum Skript).
OutputDir=..\dist\installer
; Optional: eigenes Setup-Icon, falls packaging\app.ico vorhanden.
; SetupIconFile=app.ico
; Optional: Lizenzanzeige im Setup, falls vorhanden.
; LicenseFile=..\LICENSE

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Den kompletten PyInstaller-Ordner rekursiv übernehmen.
Source: "{#BuildDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
