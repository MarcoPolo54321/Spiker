$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
if ($env:SPIKER_DATA_DIR) {
    [IO.Path]::GetFullPath($env:SPIKER_DATA_DIR)
} else {
    $Documents = [Environment]::GetFolderPath('MyDocuments')
    if ([string]::IsNullOrWhiteSpace($Documents)) { throw 'Documents folder is unavailable.' }
    Join-Path $Documents 'Spiker'
}
