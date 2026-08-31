Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not [Environment]::Is64BitOperatingSystem) {
    throw "Esta v1 é suportada apenas no Windows x64."
}

$runtimeDir = if ($env:SPILBERG_RUNTIME_DIR) { $env:SPILBERG_RUNTIME_DIR } else { Join-Path $env:LOCALAPPDATA "Spilberg" }
$bootstrap = Join-Path $PSScriptRoot "bootstrap.py"
Write-Host "Instalando Spilberg Agent em runtime privado: $runtimeDir"
python $bootstrap --runtime-dir $runtimeDir
