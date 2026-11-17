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

#ifndef BaseSha
  #define BaseSha ""
#endif
#ifndef MediumSha
  #define MediumSha ""
#endif
#ifndef LargeSha
  #define LargeSha ""
#endif
#ifndef LocalAISha
  #define LocalAISha ""
#endif
#ifndef DictationSha
  #define DictationSha ""
#endif
#ifndef BaseFaster
  #define BaseFaster 0
#endif
#ifndef BaseVosk
  #define BaseVosk 0
#endif
#ifndef BaseStreaming
  #define BaseStreaming 0
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
DisableDirPage=no
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

[InstallDelete]
Type: files; Name: "{app}\scripts\UI\Pin_dialog.py"
Type: files; Name: "{app}\scripts\private_storage.py"
Type: files; Name: "{app}\docs\videos\privacy.mp4"
Type: filesandordirs; Name: "{app}\cryptography"
Type: filesandordirs; Name: "{app}\cryptography-48.0.1.dist-info"

[Icons]
Name: "{autoprograms}\СПИКЕР"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\СПИКЕР"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Запустить СПИКЕР"; Flags: postinstall nowait skipifsilent

[Code]
function BundlePath(Kind: String): String;
begin
  Result := AddBackslash(ExpandConstant('{src}')) + 'Spiker-Models' + Kind + '-{#AppVersion}{#AppFlavor}.zip';
end;

function CTranslateReady(Path: String): Boolean;
begin
  Result := FileExists(Path + '\model.bin') and FileExists(Path + '\config.json')
    and FileExists(Path + '\tokenizer.json')
    and (FileExists(Path + '\vocabulary.json') or FileExists(Path + '\vocabulary.txt'));
end;

function Ready(Kind: String): Boolean;
var App: String;
begin
  App := AddBackslash(ExpandConstant('{app}')) + 'models\';
  if Kind = '' then begin
    Result := FileExists(App + 'whisper\ggml-small.bin');
#if BaseFaster
    Result := Result and CTranslateReady(App + 'faster-whisper\small');
#endif
#if BaseVosk
    Result := Result and FileExists(App + 'vosk\vosk-model-small-ru-0.22\am\final.mdl')
      and FileExists(App + 'vosk\vosk-model-small-ru-0.22\graph\Gr.fst');
#endif
#if BaseStreaming
    Result := Result and FileExists(App + 'sherpa-onnx\sherpa-onnx-streaming-t-one-russian-2025-09-08\model.onnx')
      and FileExists(App + 'sherpa-onnx\sherpa-onnx-streaming-t-one-russian-2025-09-08\tokens.txt');
#endif
  end
  else if Kind = '-Medium' then Result := CTranslateReady(App + 'faster-whisper\medium')
  else if Kind = '-Large-v3' then Result := CTranslateReady(App + 'faster-whisper\large-v3')
  else if Kind = '-Dictation' then Result := FileExists(App + 'whisper\ggml-base-q5_1.bin') and FileExists(App + 'whisper\ggml-tiny-q5_1.bin')
  else Result := FileExists(App + 'llm\Qwen3-4B-Q4_K_M.gguf') and FileExists(App + 'llm\GigaChat3.1-10B-A1.8B-q4_K_M.gguf');
end;

function CheckBundle(Kind, Digest: String): String;
begin
  Result := '';
  if Digest <> '' then begin
    if FileExists(BundlePath(Kind)) then begin
      if CompareText(GetSHA256OfFile(BundlePath(Kind)), Digest) <> 0 then
        Result := 'Не совпала контрольная сумма: ' + BundlePath(Kind);
    end else if (Kind = '') and not Ready(Kind) then
      Result := 'Рядом с установщиком не найден обязательный архив: ' + BundlePath(Kind);
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := CheckBundle('', '{#BaseSha}');
  if Result = '' then Result := CheckBundle('-Medium', '{#MediumSha}');
  if Result = '' then Result := CheckBundle('-Large-v3', '{#LargeSha}');
  if Result = '' then Result := CheckBundle('-Local-AI', '{#LocalAISha}');
  if Result = '' then Result := CheckBundle('-Dictation', '{#DictationSha}');
end;

procedure ApplyBundle(Kind, Digest: String);
var ResultCode: Integer; Params: String;
begin
  if (Digest = '') or Ready(Kind) or not FileExists(BundlePath(Kind)) then Exit;
  Params := '--install-model-bundle "' + BundlePath(Kind) + '" "' + ExpandConstant('{app}') + '" ' + Digest;
  if not Exec(ExpandConstant('{app}\{#AppExeName}'), Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
    RaiseException('Не удалось установить пакет моделей: ' + BundlePath(Kind) + '. Проверьте свободное место.');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    ApplyBundle('', '{#BaseSha}');
    ApplyBundle('-Medium', '{#MediumSha}');
    ApplyBundle('-Large-v3', '{#LargeSha}');
    ApplyBundle('-Local-AI', '{#LocalAISha}');
    ApplyBundle('-Dictation', '{#DictationSha}');
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
