#pragma codepage "UTF-8"
#ifndef AppVersion
  #define AppVersion "3.0.5"
#endif

#define AppName "СПИКЕР"
#define AppExeName "Spiker.exe"
#define AppPublisher "Ивасик"

[Setup]
AppId={{7E72D61D-CC27-4E42-8F43-620ABCB9C194}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\Spiker
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
OutputDir=..\dist
OutputBaseFilename=Spiker-Setup-{#AppVersion}
SetupIconFile=..\Spiker.ico
UninstallDisplayIcon={app}\{#AppExeName}
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
Uninstallable=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"; Flags: unchecked

[Files]
Source: "..\dist\Spiker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\СПИКЕР"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\СПИКЕР"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Запустить СПИКЕР"; Flags: postinstall nowait skipifsilent
