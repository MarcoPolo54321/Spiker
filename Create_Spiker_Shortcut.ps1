$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$vbs = Join-Path $root "SpikerLauncher.vbs"
$icon = Join-Path $root "Spiker.ico"
$desktop = [Environment]::GetFolderPath("Desktop")
$start = [Environment]::GetFolderPath("Programs")
$folder = Join-Path $start "Spiker"
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$wsh = New-Object -ComObject WScript.Shell
$targets = @((Join-Path $desktop "Spiker.lnk"), (Join-Path $folder "Spiker.lnk"))
foreach ($path in $targets) {
  $shortcut = $wsh.CreateShortcut($path)
  $shortcut.TargetPath = Join-Path $env:WINDIR "System32\wscript.exe"
  $shortcut.Arguments = '"' + $vbs + '"'
  $shortcut.WorkingDirectory = $root
  $shortcut.Description = "Spiker - local audio and video transcription"
  if (Test-Path $icon) { $shortcut.IconLocation = "$icon,0" }
  $shortcut.Save()
}
Write-Host "Spiker shortcuts created on the Desktop and in the Start Menu."
Write-Host "The initial dependency setup is visible and saved to logs\install.log."
pause
