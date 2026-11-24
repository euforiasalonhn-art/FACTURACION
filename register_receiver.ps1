param([string]$InstallDir,[string]$DataDir,[int]$AutoStart=1)
$ErrorActionPreference='Stop'
$exe=Join-Path $InstallDir 'FRYChickenBackup.exe'
$action=New-ScheduledTaskAction -Execute $exe -Argument ('--serve --data "'+$DataDir+'"') -WorkingDirectory $InstallDir
$principal=New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings=New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
Stop-ScheduledTask -TaskName 'FRYChickenBackupReceptor' -ErrorAction SilentlyContinue
if($AutoStart -eq 1){Register-ScheduledTask -TaskName 'FRYChickenBackupReceptor' -Action $action -Principal $principal -Settings $settings -Trigger (New-ScheduledTaskTrigger -AtStartup) -Force | Out-Null}
else{Register-ScheduledTask -TaskName 'FRYChickenBackupReceptor' -Action $action -Principal $principal -Settings $settings -Force | Out-Null}
foreach($rule in @('FRYChickenBackupTCP','FRYChickenBackupDiscovery')){Remove-NetFirewallRule -Name $rule -ErrorAction SilentlyContinue}
New-NetFirewallRule -Name 'FRYChickenBackupTCP' -DisplayName 'FRY Chicken respaldo cifrado' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5058 -RemoteAddress @('LocalSubnet','100.64.0.0/10') -Program $exe -Profile Any | Out-Null
New-NetFirewallRule -Name 'FRYChickenBackupDiscovery' -DisplayName 'FRY Chicken descubrimiento local' -Direction Inbound -Action Allow -Protocol UDP -LocalPort 5059 -RemoteAddress LocalSubnet -Program $exe -Profile Any | Out-Null
Start-ScheduledTask -TaskName 'FRYChickenBackupReceptor'
