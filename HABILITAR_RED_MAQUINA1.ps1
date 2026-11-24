# Ejecutar solo en PC 1, desde PowerShell como administrador.
$ErrorActionPreference='Stop'
$centralPython=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if(!(Test-Path -LiteralPath $centralPython)){throw 'Abre INICIAR.bat una vez antes de habilitar la red.'}
$centralRuntimeJson = & $centralPython -c 'import sys,json; print(json.dumps([sys.executable,sys._base_executable]))'
if($LASTEXITCODE -ne 0){throw 'No se pudo identificar Python para configurar el firewall.'}
$centralPaths = @($centralRuntimeJson | ConvertFrom-Json)
$centralPaths += $centralPaths | ForEach-Object { Join-Path (Split-Path $_ -Parent) 'pythonw.exe' }
$centralPaths = @($centralPaths | Sort-Object -Unique | Where-Object { Test-Path -LiteralPath $_ })
Get-NetFirewallRule -Name 'FRYCentralPython*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
$centralRuleIndex=0
foreach($centralExe in $centralPaths){
 New-NetFirewallRule -Name ('FRYCentralPython'+$centralRuleIndex) -DisplayName 'FRY Chicken servidor central' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5060 -RemoteAddress @('LocalSubnet','100.64.0.0/10') -Program $centralExe -Profile Any | Out-Null
 $centralRuleIndex++
}
Write-Host 'Puerto 5060 habilitado para red local y Tailscale. Reserva la IP de PC 1 en tu router.'
