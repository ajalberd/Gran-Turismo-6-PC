# Build the Windows version of GT6 Launcher (run on Windows 10/11, x64, PowerShell 5+).
#
#   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
#
# Output: launcher\dist\GT6-Launcher-win64.zip  (portable folder, GT6-Launcher.exe inside)
#
# RPCS3 is baked in (launcher\rpcs3\rpcs3.exe inside the zip): the pinned build, SHA-256 checked
# at build time. To ship the GT6-patched Windows RPCS3 instead, set $env:GT6L_BUNDLE_RPCS3_DIR to
# a folder containing rpcs3.exe. All launcher and emulator data lives in the package's data\ folder.
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $PSScriptRoot          # launcher\
$Work = Join-Path $Here "build-win"
$Dist = Join-Path $Here "dist"
Remove-Item -Recurse -Force $Work -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $Work, $Dist | Out-Null

# 1. Python environment
$Py = Join-Path $Work "venv\Scripts\python.exe"
python -m venv (Join-Path $Work "venv")   # the Python on PATH (actions/setup-python in CI)
& $Py -m pip install --upgrade pip
& $Py -m pip install PySide6-Essentials pyinstaller pyyaml pillow

# 2. Icon (.ico from the PNG)
$Ico = Join-Path $Work "gt6-launcher.ico"
& $Py -c "from PIL import Image; Image.open(r'$Here\gt6launcher\data\img\icon.png').save(r'$Ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"

# 3. Entry point
$Entry = Join-Path $Work "entry.py"
@"
import sys
from gt6launcher.__main__ import main
sys.exit(main())
"@ | Set-Content -Encoding UTF8 $Entry

# 3b. Resolve the emulator before packaging so calibration uses its exact SDL driver build.
$EmuDir = Join-Path $Work "rpcs3"
if ($env:GT6L_BUNDLE_RPCS3_DIR) {
    Copy-Item -Recurse $env:GT6L_BUNDLE_RPCS3_DIR $EmuDir
} else {
    # same pinned build as rpcs3.py WINDOWS_PINNED (keep in sync)
    $RpUrl = "https://github.com/RPCS3/rpcs3-binaries-win/releases/download/build-eee3f0f7c285f2b8aa18fec278a2146c5cd874eb/rpcs3-v0.0.43-20565-eee3f0f7_win64_msvc.7z"
    $RpSha = "FDEC321625C856DCF2D84EDA128F75F24A428230A233F1B2BF12C490882870E7"
    $Rp7z = Join-Path $Work "rpcs3.7z"
    Invoke-WebRequest $RpUrl -OutFile $Rp7z
    if ((Get-FileHash $Rp7z -Algorithm SHA256).Hash -ne $RpSha) { throw "RPCS3 download checksum mismatch" }
    New-Item -ItemType Directory -Force $EmuDir | Out-Null
    & 7z x -y "-o$EmuDir" $Rp7z | Out-Null   # 7-Zip is preinstalled on GitHub runners
    if (-not (Test-Path (Join-Path $EmuDir "rpcs3.exe"))) { throw "rpcs3.exe missing after extraction" }
}
$SdlDll = Get-ChildItem -Recurse $EmuDir -Filter SDL3.dll | Select-Object -First 1
if (-not $SdlDll) { throw "SDL3.dll is missing from the bundled RPCS3 build; wheel calibration must use the emulator's SDL version." }

# 4. PyInstaller (windowed; CLI sub-commands still work from a console)
$Args = @("--noconfirm", "--clean", "--onedir", "--windowed", "--name", "GT6-Launcher",
          "--icon", $Ico, "--paths", $Here,
          "--add-data", "$Here\gt6launcher\data;gt6launcher\data",
          "--exclude-module", "tkinter",
          "--add-binary", "$($SdlDll.FullName);.",
          "--distpath", (Join-Path $Work "pyi"), "--workpath", (Join-Path $Work "pyi-work"),
          "--specpath", $Work, $Entry)
& $Py -m PyInstaller @Args

$App = Join-Path $Work "pyi\GT6-Launcher"
# 4b. Bake the emulator in: players get one download, nothing is fetched on first start.
Copy-Item -Recurse $EmuDir (Join-Path $App "rpcs3")

# 5. Zip
$Zip = Join-Path $Dist "GT6-Launcher-win64.zip"
Remove-Item -Force $Zip -ErrorAction SilentlyContinue
Compress-Archive -Path $App -DestinationPath $Zip
Write-Host "Built $Zip"
