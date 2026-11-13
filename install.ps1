# Sets up DWG to PDF for the current Windows user (no admin needed):
#   - installs pypdf for your Python
#   - adds a "DWG to PDF" shortcut to the Desktop and Start menu
#   - adds it to the right-click "Send to" menu (right-click a folder > Send to > DWG to PDF)
# Run:  powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = 'Stop'
$app = $PSScriptRoot
$script = Join-Path $app 'dwg_to_pdf.py'

$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { throw 'Python not found. Install Python 3 from python.org (tick "Add to PATH").' }
$pyw = Join-Path (Split-Path $py) 'pythonw.exe'
if (-not (Test-Path $pyw)) { $pyw = $py }

& $py -m pip install --user --quiet --upgrade -r (Join-Path $app 'requirements.txt')

$shell = New-Object -ComObject WScript.Shell
$targets = @(
  [Environment]::GetFolderPath('Desktop'),
  (Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'),
  [Environment]::GetFolderPath('SendTo')
)
foreach ($dir in $targets) {
  $lnk = $shell.CreateShortcut((Join-Path $dir 'DWG to PDF.lnk'))
  $lnk.TargetPath = $pyw
  $lnk.Arguments = "`"$script`""
  $lnk.WorkingDirectory = $app
  $lnk.IconLocation = "$env:SystemRoot\System32\imageres.dll,68"
  $lnk.Description = 'Plot every DWG in a folder into one PDF'
  $lnk.Save()
  "Shortcut: $($lnk.FullName)"
}
'Done.'
