$ErrorActionPreference = "Stop"

python -m pip install -r requirements.txt
$env:PYTHONPATH = "$PSScriptRoot\src"
python -m nuitka `
  --standalone `
  --windows-console-mode=disable `
  --enable-plugin=tk-inter `
  --include-package=magic_dashboard `
  --include-package=win32com `
  --include-package=pythoncom `
  --include-package=pywintypes `
  --output-dir=dist `
  --output-filename=MagicDashboard.exe `
  main.py

Write-Host "Build complete: dist\main.dist\MagicDashboard.exe"
