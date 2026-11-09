#pragma codepage "UTF-8"
#ifndef AppVersion
  #define AppVersion "3.1.4"
#endif
#ifndef AppFlavor
  #define AppFlavor ""
#endif
#ifndef AppFolder
  #define AppFolder "Spiker"
#endif

#define AppName "СПИКЕР"
#define AppExeName "Spiker.exe"
#define AppPublisher "Ивасик"

[Setup]
AppId={{A6D54C25-895D-4FB4-8C2E-4B899EA1A310}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={code:GetUserInstallDir}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
OutputDir=..\dist
OutputBaseFilename=Spiker-Setup-{#AppVersion}{#AppFlavor}
SetupIconFile=..\Spiker.ico
UninstallDisplayIcon={app}\{#AppExeName}
WizardStyle=modern
Compression=lzma2/fast
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
Uninstallable=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"; Flags: unchecked

[Files]
Source: "..\dist\{#AppFolder}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\СПИКЕР"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\СПИКЕР"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Запустить СПИКЕР"; Flags: postinstall nowait skipifsilent

[Code]
function ModelArchivePath: String;
begin
  Result := AddBackslash(ExpandConstant('{src}')) + 'Spiker-Models-{#AppVersion}{#AppFlavor}.zip';
end;

function MediumModelArchivePath: String;
begin
  Result := AddBackslash(ExpandConstant('{src}')) + 'Spiker-Models-Medium-{#AppVersion}{#AppFlavor}.zip';
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not FileExists(ModelArchivePath) then begin
    MsgBox('Рядом с установщиком не найден архив моделей:' + #13#10 + ModelArchivePath + #13#10#13#10 +
      'Распакуйте Spiker-Setup и Spiker-Models в одну папку и запустите установщик ещё раз.', mbError, MB_OK);
    Result := False;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  PowerShellPath, Params: String;
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then begin
    PowerShellPath := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
    Params := '-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath ''' +
      ModelArchivePath + ''' -DestinationPath ''' + ExpandConstant('{app}') + ''' -Force"';
    if not Exec(PowerShellPath, Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
      RaiseException('Не удалось разложить модели. Убедитесь, что рядом с установщиком находится архив Spiker-Models и на диске достаточно места.');
    if FileExists(MediumModelArchivePath) then begin
      Params := '-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath ''' +
        MediumModelArchivePath + ''' -DestinationPath ''' + ExpandConstant('{app}') + ''' -Force"';
      if not Exec(PowerShellPath, Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
        RaiseException('Не удалось разложить архив Whisper Medium. Проверьте архив моделей и свободное место.');
    end;
  end;
end;

function GetUserInstallDir(Param: String): String;
var
  LocalAppData: String;
begin
  LocalAppData := GetEnv('LOCALAPPDATA');
  if LocalAppData = '' then
    LocalAppData := ExpandConstant('{userappdata}');
  Result := AddBackslash(LocalAppData) + 'Programs\Spiker';
end;
