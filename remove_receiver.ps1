$ErrorActionPreference='Stop'
Stop-ScheduledTask -TaskName 'FRYChickenBackupReceptor' -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName 'FRYChickenBackupReceptor' -Confirm:$false -ErrorAction SilentlyContinue
foreach($rule in @('FRYChickenBackupTCP','FRYChickenBackupDiscovery')){Remove-NetFirewallRule -Name $rule -ErrorAction SilentlyContinue}
# Los respaldos y la clave se conservan deliberadamente.
