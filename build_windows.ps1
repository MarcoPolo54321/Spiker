[CmdletBinding()]
param(
    [switch]$Installer,
    [switch]$Clean,
    [switch]$SkipTests,
    [switch]$WithoutWhisperModel,
    [switch]$WithFasterWhisper,
    [switch]$WithFasterWhisperModel,
    [switch]$WithVoskModel,
    [switch]$WithLiveDictation,
    [switch]$ReuseFullBuildEnvironment,
    [switch]$RefreshArtifacts,
    [ValidateSet('Full', 'Basic')][string]$Profile = 'Full'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
Remove-Item Env:SPIKER_DATA_DIR -ErrorAction SilentlyContinue
$Version = (Get-Content (Join-Path $Root 'VERSION') -Raw).Trim()
if (-not $Version) { throw 'VERSION is empty.' }
$Dist = Join-Path $Root 'dist'
$ArtifactSuffix = if ($Profile -eq 'Basic') { '-Basic' } elseif ($RefreshArtifacts) { '-Refresh' } else { '' }
$BuildDistPath = if ($Profile -eq 'Basic') { Join-Path $Dist 'basic-stage' } else { Join-Path $Dist 'release-stage-update' }
$BuildVenvName = if ($Profile -eq 'Basic') { '.build-venv-basic' } else { '.build-venv' }
if ($ReuseFullBuildEnvironment) {
    if ($Profile -ne 'Basic') { throw '-ReuseFullBuildEnvironment is available only with -Profile Basic.' }
    $BuildVenvName = '.build-venv'
    $env:PIP_NO_INDEX = '1'
    Write-Host 'Reusing the validated Full build environment in offline mode.'
}
$BuildWorkName = if ($Profile -eq 'Basic') { 'pyinstaller-basic-release' } else { 'pyinstaller-release-update' }
$InnoAppFolder = if ($Profile -eq 'Basic') { 'basic-stage\Spiker' } else { 'release-stage-update\Spiker' }
if ($Profile -eq 'Basic' -and ($WithFasterWhisper -or $WithFasterWhisperModel -or $WithVoskModel)) {
    throw 'The Basic profile cannot include optional faster-whisper or Vosk engines. Use the Full profile for those assets.'
}
Write-Host "Release profile: $Profile"

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Path)
    $Stream = [System.IO.File]::OpenRead($Path)
    $Hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        $Digest = $Hasher.ComputeHash($Stream)
        return ([System.BitConverter]::ToString($Digest)).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $Hasher.Dispose()
        $Stream.Dispose()
    }
}

function Resolve-Python311 {
    # Prefer the Windows Python Launcher: it can select Python 3.11 even when
    # another Python version is first on PATH or the Microsoft Store alias wins.
    $Launcher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if ($Launcher) {
        # Emit an ASCII Base64 path: native Python stdout can otherwise be decoded
        # using the wrong Windows code page when the Windows account name is Cyrillic.
        $EncodedCandidate = $null
        $LauncherExitCode = 1
        try {
            $EncodedCandidate = (& $Launcher.Source -3.11 -c "import sys,base64; print(base64.b64encode(sys.executable.encode('utf-8')).decode('ascii'))" 2>$null | Select-Object -Last 1)
            $LauncherExitCode = $LASTEXITCODE
        } catch {
            # PowerShell 5 can turn stderr from a missing py -3.11 runtime into
            # a terminating NativeCommandError before direct-path fallback runs.
            $EncodedCandidate = $null
        }
        $Candidate = $null
        if ($LauncherExitCode -eq 0 -and $EncodedCandidate) {
            try { $Candidate = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(([string]$EncodedCandidate).Trim())) }
            catch { $Candidate = $null }
        }
        if ($LauncherExitCode -eq 0 -and $Candidate -and (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $Candidate).Path
        }
    }
    $Candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
        (Join-Path $env:ProgramFiles 'Python311\python.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Python311\python.exe')
    )
    foreach ($Candidate in $Candidates) {
        if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
            $CandidateVersion = (& $Candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null | Select-Object -Last 1)
            if ($LASTEXITCODE -eq 0 -and ([string]$CandidateVersion).Trim() -eq '3.11') {
                return (Resolve-Path -LiteralPath $Candidate).Path
            }
        }
    }
    return $null
}

$PythonBaseExe = Resolve-Python311
if (-not $PythonBaseExe) {
    throw 'Python 3.11 x64 is required. Install Python 3.11 x64 (including the Python Launcher) and run this build script again.'
}
$RuntimeVersion = (& $PythonBaseExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
$PythonArchitecture = (& $PythonBaseExe -c "import platform; print(platform.machine().lower())").Trim()
if ($RuntimeVersion -ne '3.11' -or $PythonArchitecture -notin @('amd64', 'x86_64')) {
    throw "Python 3.11 x64 is required for the release build; detected Python $RuntimeVersion ($PythonArchitecture) at $PythonBaseExe."
}
Write-Host "Base Python interpreter: $PythonBaseExe"

if ($WithFasterWhisperModel -and -not $WithFasterWhisper) {
    throw '-WithFasterWhisperModel requires -WithFasterWhisper.'
}
$FasterWhisperModelDir = Join-Path $Root 'models\faster-whisper\small'
$FasterWhisperModelSha256 = '3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671'

if ($env:GITHUB_REF_TYPE -eq 'tag') {
    $ExpectedTag = "v$Version"
    if ($env:GITHUB_REF_NAME -ne $ExpectedTag) {
        throw "Git tag '$env:GITHUB_REF_NAME' does not match VERSION '$Version'. Expected $ExpectedTag."
    }
}

function Find-InnoCompiler {
    # Accept an explicit override first, then common system/per-user install paths.
    $Candidates = @(
        $env:INNO_SETUP_PATH,
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
        (Join-Path $env:LOCALAPPDATA 'Inno Setup 6\ISCC.exe')
    )
    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $Candidate).Path
        }
    }
    $Command = Get-Command 'ISCC.exe' -ErrorAction SilentlyContinue
    if ($Command) { return $Command.Source }
    return $null
}

# Fail fast before downloading models or rebuilding PyInstaller if the compiler is
# unavailable. On Windows, try the official WinGet package automatically.
$ISCC = $null
if ($Installer) {
    $ISCC = Find-InnoCompiler
    if (-not $ISCC) {
        $Winget = Get-Command 'winget.exe' -ErrorAction SilentlyContinue
        if ($Winget) {
            Write-Host 'Inno Setup 6 is missing. Attempting installation with WinGet...'
            & $Winget.Source install --id JRSoftware.InnoSetup --exact --source winget --silent --accept-package-agreements --accept-source-agreements
            $WingetExitCode = $LASTEXITCODE
            # The package may install successfully even if WinGet returns a restart/status code.
            Start-Sleep -Seconds 2
            $ISCC = Find-InnoCompiler
            if (-not $ISCC) {
                Write-Warning "WinGet could not make Inno Setup available (exit code $WingetExitCode)."
            }
        }
    }
    if (-not $ISCC) {
        throw @'
Inno Setup 6 compiler (ISCC.exe) is required to create Spiker-Setup.exe.
Install it from https://jrsoftware.org/isdl.php, then run Build_Windows_Release.bat again.
If installed in a custom folder, set INNO_SETUP_PATH to the full path of ISCC.exe.
For a portable build only, run: powershell -ExecutionPolicy Bypass -File .\build_windows.ps1 -Clean
'@
    }
    Write-Host "Inno Setup compiler: $ISCC"
}

$BuildVenv = Join-Path $Root $BuildVenvName
$BuildWorkPath = Join-Path $Root "build\$BuildWorkName"
$Python = Join-Path $BuildVenv 'Scripts\python.exe'
if ($Clean) {
    $CleanTargets = @($BuildWorkPath, (Join-Path $BuildDistPath 'Spiker'))
    foreach ($PathToRemove in $CleanTargets) {
        if (Test-Path $PathToRemove) { Remove-Item $PathToRemove -Recurse -Force }
    }
    foreach ($Artifact in @(
        (Join-Path $Dist "Spiker-Portable-$Version$ArtifactSuffix.zip"),
        (Join-Path $Dist "Spiker-Setup-$Version$ArtifactSuffix.exe")
    )) {
        if (Test-Path $Artifact) { Remove-Item $Artifact -Force }
    }
}
if ($Profile -eq 'Basic' -and (Test-Path $BuildDistPath)) {
    Remove-Item $BuildDistPath -Recurse -Force
}
if (-not (Test-Path $Python)) {
    if (Test-Path $BuildVenv) {
        Write-Warning 'Removing an incomplete build environment (python.exe is missing).'
        Remove-Item $BuildVenv -Recurse -Force
    }
    Write-Host 'Creating isolated build environment without implicit ensurepip...'
    # Some Windows Python installations create the venv directory but fail while
    # running ensurepip. --without-pip avoids that fragile stage; pip is bootstrapped below.
    & $PythonBaseExe -m venv --without-pip $BuildVenv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Python)) {
        throw 'Unable to create build venv. Verify that Python 3.11 x64 is a complete installation and that the build folder is writable.'
    }
}

# Bootstrap pip without invoking `python -m pip` while pip may be absent.
# In Windows PowerShell, stderr from a native process can become a terminating
# NativeCommandError when ErrorActionPreference=Stop. The previous probe
# (`python -m pip --version`) therefore aborted the build before fallback ran.
$PipBootstrapScript = Join-Path $Root 'scripts\bootstrap_build_pip.py'
if (-not (Test-Path -LiteralPath $PipBootstrapScript -PathType Leaf)) {
    throw "pip bootstrap helper is missing: $PipBootstrapScript"
}
Write-Host 'Checking and bootstrapping pip in the isolated build environment...'
& $Python $PipBootstrapScript
if ($LASTEXITCODE -ne 0) {
    throw 'Could not prepare pip in the isolated build environment. See bootstrap output above.'
}
# This verification is safe: the helper has already confirmed that `import pip`
# succeeds. Avoid asking PyPI to re-resolve the pinned version when it is already
# installed; this also lets a previously prepared build environment work offline.
$BuildPipVersion = (& $Python -c "import pip; print(pip.__version__)").Trim()
if ($LASTEXITCODE -ne 0) { throw 'The isolated build environment has no working pip after bootstrap.' }
Write-Host "Build pip: $BuildPipVersion"

Write-Host 'Installing runtime, packaging, and regression-test dependencies...'
if ($BuildPipVersion -ne '24.3.1') {
    & $Python -m pip install --upgrade pip==24.3.1
    if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
} else {
    Write-Host 'Pinned pip version is already installed; skipping network lookup.'
}
$RequiredBuildModules = @('PySide6', 'pyaudio', 'vosk', 'imageio_ffmpeg', 'pywhispercpp', 'keyring', 'docx', 'PyInstaller', 'PIL')
$ModuleNames = ($RequiredBuildModules | ForEach-Object { "'$_'" }) -join ','
$BuildProbe = "import importlib.util; names=($ModuleNames,); print('yes' if all(importlib.util.find_spec(x) for x in names) else 'no')"
$BuildEnvironmentPrepared = (& $Python -c $BuildProbe).Trim() -eq 'yes'
if ($BuildEnvironmentPrepared) {
    Write-Host 'All pinned build dependencies are present; using the local package cache only.'
    $env:PIP_NO_INDEX = '1'
}
& $Python -m pip install -r (Join-Path $Root 'res\requirements.txt') '-r' (Join-Path $Root 'res\requirements-build.txt') '-r' (Join-Path $Root 'res\requirements-test.txt')
$DependencyInstallExitCode = $LASTEXITCODE
if ($BuildEnvironmentPrepared) { Remove-Item Env:PIP_NO_INDEX -ErrorAction SilentlyContinue }
if ($DependencyInstallExitCode -ne 0) { throw 'Dependency installation failed.' }

Write-Host 'Preparing offline release models...'
$ReleaseModelArgs = @('--release-assets')
if ($WithFasterWhisperModel) { $ReleaseModelArgs += '--include-medium', '--include-faster-whisper' }
& $Python (Join-Path $Root 'scripts\download_release_models.py') @ReleaseModelArgs
if ($LASTEXITCODE -ne 0) { throw 'Offline model preparation failed.' }

if ($WithFasterWhisper) {
    $HasFasterWhisper = (& $Python -c "import importlib.util; print('yes' if importlib.util.find_spec('faster_whisper') else 'no')").Trim() -eq 'yes'
    if (-not $HasFasterWhisper) {
        Write-Host 'Installing optional faster-whisper/CTranslate2 runtime for this build...'
        & $Python -m pip install 'faster-whisper>=1.1,<2'
        if ($LASTEXITCODE -ne 0) { throw 'Optional faster-whisper installation failed.' }
    } else {
        Write-Host 'faster-whisper/CTranslate2 runtime is already installed; skipping pip resolution.'
    }
    $env:SPIKER_PACKAGE_FASTER_WHISPER = '1'
    if ($WithFasterWhisperModel) {
        Write-Host 'Verifying the pinned faster-whisper Small model for offline installation...'
        $RequiredFasterFiles = @('config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt')
        $MissingFasterFiles = @($RequiredFasterFiles | Where-Object { -not (Test-Path -LiteralPath (Join-Path $FasterWhisperModelDir $_) -PathType Leaf) })
        if ($MissingFasterFiles.Count -gt 0) { throw "faster-whisper Small is incomplete: $($MissingFasterFiles -join ', ')" }
        $ActualFasterHash = Get-Sha256Hex (Join-Path $FasterWhisperModelDir 'model.bin')
        if ($ActualFasterHash -ne $FasterWhisperModelSha256) { throw "faster-whisper Small SHA-256 mismatch: $ActualFasterHash" }
        Write-Host 'Bundling the pinned faster-whisper Small model for offline installation...'
        $env:SPIKER_PACKAGE_FASTER_WHISPER_MODEL = '1'
    } else {
        Remove-Item Env:SPIKER_PACKAGE_FASTER_WHISPER_MODEL -ErrorAction SilentlyContinue
    }
} else {
    Remove-Item Env:SPIKER_PACKAGE_FASTER_WHISPER -ErrorAction SilentlyContinue
    Remove-Item Env:SPIKER_PACKAGE_FASTER_WHISPER_MODEL -ErrorAction SilentlyContinue
}
if ($WithVoskModel) {
    Write-Host 'Downloading/verifying the Russian Vosk fallback model for offline installation...'
    & $Python (Join-Path $Root 'scripts\install_models.py') --vosk --target-root (Join-Path $Root 'models\vosk')
    if ($LASTEXITCODE -ne 0) { throw 'Russian Vosk model installation/verification failed.' }
    $env:SPIKER_PACKAGE_VOSK_MODEL = '1'
} else {
    Remove-Item Env:SPIKER_PACKAGE_VOSK_MODEL -ErrorAction SilentlyContinue
}
if ($WithLiveDictation) {
    $HasSherpaOnnx = (& $Python -c "import importlib.util; print('yes' if importlib.util.find_spec('sherpa_onnx') else 'no')").Trim() -eq 'yes'
    if (-not $HasSherpaOnnx) {
        Write-Host 'Installing optional sherpa-onnx runtime...'
        & $Python -m pip install 'sherpa-onnx>=1.12,<2'
        if ($LASTEXITCODE -ne 0) { throw 'Optional sherpa-onnx installation failed.' }
    } else {
        Write-Host 'sherpa-onnx runtime is already installed; skipping pip resolution.'
    }
    Write-Host 'Preparing Russian T-one streaming model...'
    & $Python (Join-Path $Root 'scripts\download_t_one_model.py') --target-root (Join-Path $Root 'models\sherpa-onnx')
    if ($LASTEXITCODE -ne 0) { throw 'Optional T-one model download failed.' }
    $env:SPIKER_PACKAGE_SHERPA = '1'
} else {
    Remove-Item Env:SPIKER_PACKAGE_SHERPA -ErrorAction SilentlyContinue
}

if (-not $SkipTests) {
    $PreviousPycachePrefix = $env:PYTHONPYCACHEPREFIX
    $env:PYTHONPYCACHEPREFIX = Join-Path $BuildWorkPath 'pycache'
    Write-Host 'Running unit tests...'
    & $Python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed; release build stopped.' }
    & $Python -m compileall -q scripts tests
    if ($LASTEXITCODE -ne 0) { throw 'Python syntax check failed.' }
    if ($null -eq $PreviousPycachePrefix) { Remove-Item Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue }
    else { $env:PYTHONPYCACHEPREFIX = $PreviousPycachePrefix }
}

if (-not $WithoutWhisperModel) {
    # Bundle one multilingual speech model so end users can install and transcribe offline.
    # The pinned Hugging Face revision and SHA-256 make this repeatable and verifiable.
    $WhisperDir = Join-Path $Root 'models\whisper'
    $WhisperModelPath = Join-Path $WhisperDir 'ggml-small.bin'
    $WhisperModelUrl = 'https://huggingface.co/ggerganov/whisper.cpp/resolve/90a64d80ea254cf67575b41a5971f972c79f7b45/ggml-small.bin'
    $WhisperModelSha256 = '1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b'
    New-Item -ItemType Directory -Path $WhisperDir -Force | Out-Null

    $NeedsWhisperDownload = $true
    if (Test-Path $WhisperModelPath) {
        $ExistingHash = Get-Sha256Hex $WhisperModelPath
        if ($ExistingHash -eq $WhisperModelSha256) {
            $NeedsWhisperDownload = $false
            Write-Host 'Verified existing Whisper Small model.'
        } else {
            Write-Warning 'Existing Whisper Small model has a different checksum; replacing it with the pinned release model.'
            Remove-Item $WhisperModelPath -Force
        }
    }

    if ($NeedsWhisperDownload) {
        Write-Host 'Downloading multilingual Whisper Small model for offline use (about 488 MB)...'
        $Curl = Get-Command 'curl.exe' -ErrorAction SilentlyContinue
        if (-not $Curl) { throw 'curl.exe is required to download the default Whisper model during release build.' }
        & $Curl.Source --location --fail --retry 3 --retry-delay 3 --output $WhisperModelPath $WhisperModelUrl
        if ($LASTEXITCODE -ne 0) {
            if (Test-Path $WhisperModelPath) { Remove-Item $WhisperModelPath -Force }
            throw 'Whisper model download failed. Check network access or pass -WithoutWhisperModel for a developer-only build.'
        }
        $DownloadedHash = Get-Sha256Hex $WhisperModelPath
        if ($DownloadedHash -ne $WhisperModelSha256) {
            Remove-Item $WhisperModelPath -Force
            throw "Whisper model checksum mismatch. Expected $WhisperModelSha256, got $DownloadedHash."
        }
        Write-Host 'Whisper Small model checksum verified.'
    }
} else {
    Write-Warning 'Building without the default Whisper model. The resulting app will require the user to supply a model before transcription.'
}

if ($Version -notmatch '^\d+\.\d+\.\d+(\.\d+)?$') {
    throw "VERSION must be major.minor.patch (optionally followed by a hotfix number), got '$Version'."
}
$VersionParts = @($Version.Split('.'))
if ($VersionParts.Count -eq 3) { $VersionParts += '0' }
$VersionTuple = "$([int]$VersionParts[0]), $([int]$VersionParts[1]), $([int]$VersionParts[2]), $([int]$VersionParts[3])"
$VersionInfoPath = Join-Path $Root 'build\version_info.txt'
New-Item -ItemType Directory -Path (Split-Path -Parent $VersionInfoPath) -Force | Out-Null
$VersionInfo = @"
VSVersionInfo(
 ffi=FixedFileInfo(filevers=($VersionTuple), prodvers=($VersionTuple), mask=0x3f, flags=0x0, OS=0x4, fileType=0x1, subtype=0x0, date=(0, 0)),
 kids=[StringFileInfo([StringTable('041904B0', [StringStruct('CompanyName', 'Ivasik'), StringStruct('FileDescription', 'Spiker offline transcription and AI processing'), StringStruct('FileVersion', '$Version'), StringStruct('InternalName', 'Spiker'), StringStruct('OriginalFilename', 'Spiker.exe'), StringStruct('ProductName', 'Spiker'), StringStruct('ProductVersion', '$Version')])]), VarFileInfo([VarStruct('Translation', [1049, 1200])])]
)
"@
$VersionInfo | Set-Content -Path $VersionInfoPath -Encoding ascii

Write-Host 'Building standalone application with PyInstaller...'
New-Item -ItemType Directory -Path $BuildDistPath -Force | Out-Null
& $Python -m PyInstaller --clean --noconfirm --distpath $BuildDistPath --workpath $BuildWorkPath (Join-Path $Root 'Spiker.spec')
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

$AppDir = Join-Path $BuildDistPath 'Spiker'
$Exe = Join-Path $AppDir 'Spiker.exe'
if (-not (Test-Path $Exe)) { throw "Expected executable not found: $Exe" }

Write-Host 'Running packaged executable smoke test...'
$env:SPIKER_DATA_DIR = Join-Path $AppDir '.smoke-user-data'
$SmokeArgs = @('--smoke-test')
if (-not $WithoutWhisperModel) { $SmokeArgs += '--require-whisper-model' }
if ($WithLiveDictation) { $SmokeArgs += '--require-live-dictation' }
if ($WithFasterWhisper) { $SmokeArgs += '--require-faster-whisper' }
if ($WithFasterWhisperModel) { $SmokeArgs += '--require-faster-whisper-model' }
if ($WithVoskModel) { $SmokeArgs += '--require-vosk-model' }
$SmokeProcess = Start-Process -FilePath $Exe -ArgumentList $SmokeArgs -PassThru
if (-not $SmokeProcess.WaitForExit(180000)) {
    & taskkill.exe /PID $SmokeProcess.Id /T /F 2>$null | Out-Null
    throw 'Packaged EXE smoke test timed out after 180 seconds.'
}
$SmokeProcess.WaitForExit()
$SmokeProcess.Refresh()
Remove-Item Env:SPIKER_DATA_DIR -ErrorAction SilentlyContinue
if ($SmokeProcess.ExitCode -ne 0) {
    $LogPath = Join-Path $AppDir '.smoke-user-data\logs\application.log'
    if (Test-Path $LogPath) { Get-Content $LogPath -Tail 80 }
    throw "Packaged EXE smoke test failed with exit code $($SmokeProcess.ExitCode)."
}
# Avoid a transient process/file lock when creating the portable archive.
Start-Sleep -Milliseconds 1200
# Don't ship diagnostics generated by the smoke test as if they were user data.
foreach ($RuntimeFolder in @('logs', 'data', 'results')) {
    $RuntimePath = Join-Path $AppDir $RuntimeFolder
    if (Test-Path $RuntimePath) { Remove-Item $RuntimePath -Recurse -Force }
}
$SmokeDataPath = Join-Path $AppDir '.smoke-user-data'
if (Test-Path $SmokeDataPath) { Remove-Item $SmokeDataPath -Recurse -Force }

$PortableZip = Join-Path $Dist "Spiker-Portable-$Version$ArtifactSuffix.zip"
if (Test-Path $PortableZip) { Remove-Item $PortableZip -Force }

# Keep model weights out of both the installer executable and portable app ZIP.
# The companion archive is distributed beside Setup.exe and unpacked by Setup.
$ModelStage = Join-Path $Dist '.model-package-stage'
$ModelArchive = Join-Path $Dist "Spiker-Models-$Version$ArtifactSuffix.zip"
if (Test-Path $ModelStage) { Remove-Item -LiteralPath $ModelStage -Recurse -Force }
if (Test-Path $ModelArchive) { Remove-Item -LiteralPath $ModelArchive -Force }
$ModelRelatives = @('models\whisper\ggml-small.bin', 'models\whisper\MODEL_SOURCE.md')
if ($WithFasterWhisperModel) { $ModelRelatives += 'models\faster-whisper\small' }
if ($WithFasterWhisperModel -and (Test-Path (Join-Path $Root 'models\faster-whisper\medium'))) { $ModelRelatives += 'models\faster-whisper\medium' }
if ($WithVoskModel) { $ModelRelatives += 'models\vosk\vosk-model-small-ru-0.22' }
if ($WithLiveDictation) {
    $ModelRelatives += 'models\sherpa-onnx\sherpa-onnx-streaming-t-one-russian-2025-09-08'
    $ModelRelatives += 'models\tts'
    $ModelRelatives += 'models\diarization'
}
foreach ($Relative in $ModelRelatives) {
    $SourceModel = Join-Path $AppDir $Relative
    if (-not (Test-Path -LiteralPath $SourceModel)) { continue }
    $StagePath = Join-Path $ModelStage $Relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $StagePath) -Force | Out-Null
    if (Test-Path -LiteralPath $SourceModel -PathType Container) {
        Copy-Item -LiteralPath $SourceModel -Destination $StagePath -Recurse -Force
    } else {
        Copy-Item -LiteralPath $SourceModel -Destination $StagePath -Force
    }
}
if (Test-Path -LiteralPath $ModelStage) {
    Compress-Archive -Path (Join-Path $ModelStage '*') -DestinationPath $ModelArchive -CompressionLevel Optimal
    Remove-Item -LiteralPath $ModelStage -Recurse -Force
}
foreach ($Relative in $ModelRelatives) {
    $BundledModel = Join-Path $AppDir $Relative
    if (Test-Path -LiteralPath $BundledModel) {
        Remove-Item -LiteralPath $BundledModel -Recurse -Force
    }
}

$PortableMarker = Join-Path $AppDir 'portable.flag'
Set-Content -LiteralPath $PortableMarker -Value 'Spiker portable data stays beside this application.' -Encoding ascii
$ArchiveCreated = $false
for ($ArchiveAttempt = 1; $ArchiveAttempt -le 5; $ArchiveAttempt++) {
    try {
        Compress-Archive -Path $AppDir -DestinationPath $PortableZip -CompressionLevel Optimal -ErrorAction Stop
        $ArchiveCreated = $true
        break
    } catch {
        if (Test-Path $PortableZip) { Remove-Item $PortableZip -Force -ErrorAction SilentlyContinue }
        if ($ArchiveAttempt -lt 5) {
            Write-Warning "Portable ZIP is temporarily unavailable (attempt $ArchiveAttempt of 5); retrying."
            Start-Sleep -Seconds (2 * $ArchiveAttempt)
        }
    }
}
if (-not $ArchiveCreated) {
    throw 'Portable ZIP creation failed after 5 attempts. Close any running Spiker.exe process from the dist folder and run the build again.'
}
Remove-Item -LiteralPath $PortableMarker -Force

if ($Installer) {
    Write-Host 'Building per-user installer...'
    if (-not (Test-Path -LiteralPath $ModelArchive)) { throw "Companion model archive was not created: $ModelArchive" }
    & $ISCC "/DAppVersion=$Version" "/DAppFlavor=$ArtifactSuffix" "/DAppFolder=$InnoAppFolder" (Join-Path $Root 'installer\Spiker.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compilation failed.' }
}

$ChecksumLines = @()
$ReleasePattern = "^Spiker-(Portable|Setup|Models)-$([regex]::Escape($Version))(-Basic|-Refresh)?\.(zip|exe)$"
foreach ($File in (Get-ChildItem $Dist -File | Where-Object { $_.Name -match $ReleasePattern })) {
    $Hash = Get-Sha256Hex $File.FullName
    $ChecksumLines += "$Hash  $($File.Name)"
}
$ChecksumPath = Join-Path $Dist 'SHA256SUMS.txt'
$ChecksumLines | Set-Content -Path $ChecksumPath -Encoding ascii

Write-Host ''
Write-Host "Build completed. Version: $Version"
Write-Host "Portable: $PortableZip"
Write-Host "Models: $ModelArchive"
if ($Installer) { Write-Host "Installer: $(Join-Path $Dist "Spiker-Setup-$Version$ArtifactSuffix.exe")" }
Write-Host "Checksums: $ChecksumPath"
