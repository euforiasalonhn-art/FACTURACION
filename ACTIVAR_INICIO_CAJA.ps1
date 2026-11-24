# Opcional: inicia caja al entrar el usuario de Windows. No crea una segunda caja.
$ErrorActionPreference = 'Stop'
$posPython = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
if (!(Test-Path -LiteralPath $posPython)) { throw 'Abre INICIAR.bat una vez antes de configurar el inicio automatico.' }
$posShell = New-Object -ComObject WScript.Shell
$posStartup = [Environment]::GetFolderPath('Startup')
$posShortcut = $posShell.CreateShortcut((Join-Path $posStartup 'FRYChickenPOS.lnk'))
$posShortcut.TargetPath = $posPython
$posShortcut.Arguments = '"' + (Join-Path $PSScriptRoot 'desktop_main.py') + '"'
$posShortcut.WorkingDirectory = $PSScriptRoot
$posShortcut.Save()
Write-Host 'Caja iniciara al entrar este usuario de Windows.'
