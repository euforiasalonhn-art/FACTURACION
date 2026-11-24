# Ejecutar como administrador, solamente en la PC receptora.
$ErrorActionPreference = 'Stop'
$receiverRoot = $PSScriptRoot
$receiverPython = Join-Path $receiverRoot '.venv\Scripts\pythonw.exe'
$receiverData = Join-Path $env:LOCALAPPDATA 'FRYChickenBackup'
$receiverConfig = Join-Path $receiverData 'receptor.json'
if (!(Test-Path -LiteralPath $receiverPython) -or !(Test-Path -LiteralPath $receiverConfig)) { throw 'Ejecuta primero CONFIGURAR_RESPALDO.bat con tu usuario de Windows.' }
$receiverAction = New-ScheduledTaskAction -Execute $receiverPython -Argument ('"' + (Join-Path $receiverRoot 'backup_receiver.py') + '" --data "' + $receiverData + '"') -WorkingDirectory $receiverRoot
$receiverTrigger = New-ScheduledTaskTrigger -AtStartup
$receiverPrincipal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$receiverSettings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'FRYChickenBackupReceptor' -Action $receiverAction -Trigger $receiverTrigger -Principal $receiverPrincipal -Settings $receiverSettings -Force | Out-Null
if (!(Get-NetFirewallRule -Name 'FRYChickenBackupTailscale' -ErrorAction SilentlyContinue)) {
 New-NetFirewallRule -Name 'FRYChickenBackupTailscale' -DisplayName 'FRY Chicken respaldo cifrado LAN y Tailscale' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5058 -RemoteAddress @('LocalSubnet','100.64.0.0/10') -Program $receiverPython -Profile Any | Out-Null
}
Start-ScheduledTask -TaskName 'FRYChickenBackupReceptor'
Write-Host 'Receptor registrado para iniciar con Windows, sin iniciar sesion. Puerto 5058 limitado a red local y Tailscale.'
