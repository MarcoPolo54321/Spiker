[CmdletBinding()]
param(
    [switch]$Installer,
    [switch]$Clean,
    [switch]$SkipTests,
    [switch]$WithoutWhisperModel
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Version = (Get-Content (Join-Path $Root 'VERSION') -Raw).Trim()
if (-not $Version) { throw 'VERSION is empty.' }
$RuntimeVersion = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
$PythonArchitecture = (& python -c "import platform; print(platform.machine().lower())").Trim()
if ($RuntimeVersion -ne '3.11' -or $PythonArchitecture -notin @('amd64', 'x86_64')) {
    throw "Python 3.11 x64 is required for the release build; detected Python $RuntimeVersion ($PythonArchitecture). On GitHub Actions use the configured 3.11 runner."
}

if ($env:GITHUB_REF_TYPE -eq 'tag') {
    $ExpectedTag = "v$Version"
    if ($env:GITHUB_REF_NAME -ne $ExpectedTag) {
        throw "Git tag '$env:GITHUB_REF_NAME' does not match VERSION '$Version'. Expected $ExpectedTag."
    }
}

$BuildVenv = Join-Path $Root '.build-venv'
$Python = Join-Path $BuildVenv 'Scripts\python.exe'
if ($Clean) {
    foreach ($PathToRemove in @((Join-Path $Root 'build'), (Join-Path $Root 'dist'))) {
        if (Test-Path $PathToRemove) { Remove-Item $PathToRemove -Recurse -Force }
    }
}
if (-not (Test-Path $Python)) {
    Write-Host 'Creating isolated build environment...'
    & python -m venv $BuildVenv
    if ($LASTEXITCODE -ne 0) { throw 'Unable to create build venv. Install Python 3.11 x64 first.' }
}

Write-Host 'Installing runtime and packaging dependencies...'
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
& $Python -m pip install -r (Join-Path $Root 'res\requirements.txt') '-r' (Join-Path $Root 'res\requirements-build.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }

if (-not $SkipTests) {
    Write-Host 'Running unit tests...'
    & $Python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed; release build stopped.' }
    & $Python -m compileall -q scripts tests
    if ($LASTEXITCODE -ne 0) { throw 'Python syntax check failed.' }
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
        $ExistingHash = (Get-FileHash $WhisperModelPath -Algorithm SHA256).Hash.ToLowerInvariant()
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
        $DownloadedHash = (Get-FileHash $WhisperModelPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($DownloadedHash -ne $WhisperModelSha256) {
            Remove-Item $WhisperModelPath -Force
            throw "Whisper model checksum mismatch. Expected $WhisperModelSha256, got $DownloadedHash."
        }
        Write-Host 'Whisper Small model checksum verified.'
    }
} else {
    Write-Warning 'Building without the default Whisper model. The resulting app will require the user to supply a model before transcription.'
}

if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "VERSION must be a simple major.minor.patch value, got '$Version'."
}
$VersionParts = $Version.Split('.')
$VersionTuple = "$([int]$VersionParts[0]), $([int]$VersionParts[1]), $([int]$VersionParts[2]), 0"
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
& $Python -m PyInstaller --clean --noconfirm --distpath (Join-Path $Root 'dist') --workpath (Join-Path $Root 'build\pyinstaller') (Join-Path $Root 'Spiker.spec')
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

$Dist = Join-Path $Root 'dist'
$AppDir = Join-Path $Dist 'Spiker'
$Exe = Join-Path $AppDir 'Spiker.exe'
if (-not (Test-Path $Exe)) { throw "Expected executable not found: $Exe" }

Write-Host 'Running packaged executable smoke test...'
$SmokeArgs = @('--smoke-test')
if (-not $WithoutWhisperModel) { $SmokeArgs += '--require-whisper-model' }
& $Exe @SmokeArgs
if ($LASTEXITCODE -ne 0) {
    $LogPath = Join-Path $AppDir 'logs\application.log'
    if (Test-Path $LogPath) { Get-Content $LogPath -Tail 80 }
    throw "Packaged EXE smoke test failed with exit code $LASTEXITCODE."
}
# Don't ship diagnostics generated by the smoke test as if they were user data.
foreach ($RuntimeFolder in @('logs', 'data', 'results')) {
    $RuntimePath = Join-Path $AppDir $RuntimeFolder
    if (Test-Path $RuntimePath) { Remove-Item $RuntimePath -Recurse -Force }
}

$PortableZip = Join-Path $Dist "Spiker-Portable-$Version.zip"
if (Test-Path $PortableZip) { Remove-Item $PortableZip -Force }
Compress-Archive -Path $AppDir -DestinationPath $PortableZip -CompressionLevel Optimal

if ($Installer) {
    $CompilerCandidates = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
    )
    $ISCC = $CompilerCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if (-not $ISCC) {
        $Command = Get-Command 'ISCC.exe' -ErrorAction SilentlyContinue
        if ($Command) { $ISCC = $Command.Source }
    }
    if (-not $ISCC) { throw 'Inno Setup 6 was not found. Install it or build without -Installer.' }
    Write-Host 'Building per-user installer...'
    & $ISCC "/DAppVersion=$Version" (Join-Path $Root 'installer\Spiker.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compilation failed.' }
}

$ChecksumLines = @()
foreach ($File in (Get-ChildItem $Dist -File | Where-Object { $_.Name -like "Spiker-Portable-$Version.zip" -or $_.Name -like "Spiker-Setup-$Version.exe" })) {
    $Hash = (Get-FileHash $File.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $ChecksumLines += "$Hash  $($File.Name)"
}
$ChecksumPath = Join-Path $Dist 'SHA256SUMS.txt'
$ChecksumLines | Set-Content -Path $ChecksumPath -Encoding ascii

Write-Host ''
Write-Host "Build completed. Version: $Version"
Write-Host "Portable: $PortableZip"
if ($Installer) { Write-Host "Installer: $(Join-Path $Dist "Spiker-Setup-$Version.exe")" }
Write-Host "Checksums: $ChecksumPath"
