<#
    Builds a standalone Windows executable for File Control.

    Usage (right-click > Run with PowerShell, or from a terminal):
        powershell -ExecutionPolicy Bypass -File build_exe.ps1

    The result is produced in the "dist" folder:
        dist\FileControl.exe

    This .exe runs with a simple double-click, without Python or VS Code.
#>

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "== Building the File Control executable ==" -ForegroundColor Cyan

# 1. Make sure PyInstaller is installed (idempotent).
Write-Host "Installing / updating PyInstaller..." -ForegroundColor Yellow
python -m pip install --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) {
    Write-Host "Could not install PyInstaller." -ForegroundColor Red
    exit 1
}

# 2. Clean previous builds.
foreach ($dir in @("build", "dist")) {
    if (Test-Path $dir) { Remove-Item -Recurse -Force $dir }
}
if (Test-Path "FileControl.spec") { Remove-Item -Force "FileControl.spec" }

# 3. Build a windowed, single-file executable.
#    --add-data bundles config.json next to the program (';' separator on Windows).
python -m PyInstaller `
    --name "FileControl" `
    --onefile `
    --windowed `
    --add-data "config.json;." `
    --collect-submodules filecontrol `
    main.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed." -ForegroundColor Red
    exit 1
}

# 4. Copy config.json next to the executable so the user can edit it.
Copy-Item -Path "config.json" -Destination "dist\config.json" -Force

# 5. Copy the end-user guide next to the executable, if present.
if (Test-Path "USER_GUIDE.txt") {
    Copy-Item -Path "USER_GUIDE.txt" -Destination "dist\README.txt" -Force
}

Write-Host ""
Write-Host "Done. Executable available at: dist\FileControl.exe" -ForegroundColor Green
Write-Host "You can copy the whole 'dist' folder to the user's machine." -ForegroundColor Green
