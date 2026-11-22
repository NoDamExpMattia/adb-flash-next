# Builds:  dist\ADB Flash Next\ADB Flash Next.exe
# Run from anywhere:  .\tools\build_exe.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$py = ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "The virtual environment .venv was not found in $(Get-Location)." }

New-Item -ItemType Directory -Force assets | Out-Null
& $py -m pip install --quiet -r requirements.txt -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Installing the build tools failed." }

# Use a ready-made assets\app.ico if there is one, otherwise create it from assets\logo.png.
if (-not (Test-Path "assets\app.ico")) {
    if (Test-Path "assets\logo.png") {
        & $py tools\make_icon.py
        if ($LASTEXITCODE -ne 0) { throw "Creating the icon failed." }
    } else {
        Write-Warning "No assets\app.ico and no assets\logo.png: the exe will get the default icon."
    }
}
$iconArgs = @()
if (Test-Path "assets\app.ico") { $iconArgs = @("--icon", "assets\app.ico") }

& $py -m PyInstaller --noconfirm --clean --windowed --name "ADB Flash Next" @iconArgs `
    --add-data "assets;assets" --paths src main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

$exe = "dist\ADB Flash Next\ADB Flash Next.exe"
if (-not (Test-Path $exe)) { throw "The build finished but $exe was not created." }
Write-Host ""
Write-Host "Done: $((Resolve-Path $exe).Path)" -ForegroundColor Green
