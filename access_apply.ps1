param([Parameter(Mandatory=$true)][string]$InputPath,[Parameter(Mandatory=$true)][string]$AccessPath)
$ErrorActionPreference='Stop'
$payload=Get-Content -LiteralPath $InputPath -Raw -Encoding UTF8 | ConvertFrom-Json
$engine=$null;$workspace=$null;$db=$null;$transaction=$false
function Quote-Key([string]$value){return "'"+$value.Replace("'","''")+"'"}
function Set-Field($record,[string]$name,$value){
 $target=$record.Fields.Item($name)
 [void]$target.GetType().InvokeMember('Value',[Reflection.BindingFlags]::SetProperty,$null,$target,[object[]]@($value))
}
try {
 $engine=New-Object -ComObject DAO.DBEngine.120
 $workspace=$engine.Workspaces.Item(0)
 $db=$engine.OpenDatabase([IO.Path]::GetFullPath($AccessPath),$false,$false)
 $control=$db.OpenRecordset('SELECT * FROM ControlSincronizacion',4)
 if (!$control.EOF) {
  $previous=[string]$control.Fields.Item('Origen').Value
  if ($previous -and $previous -ne [string]$payload.origin){throw 'El archivo Access pertenece a otra instalacion. No se mezclaron datos.'}
  $last=[int]$control.Fields.Item('UltimaFactura').Value
  $current=[int]$payload.tables.ControlSincronizacion[0].values.UltimaFactura
  if ($current -lt $last){throw 'La base del POS tiene menos historial que Access. Revisa la restauracion antes de sincronizar.'}
 }
 $control.Close()
 $workspace.BeginTrans();$transaction=$true;$changes=0;$deleted=0
 foreach($table in $payload.schema.PSObject.Properties){
  $name=$table.Name
  if ($name -notmatch '^[A-Za-z]+$'){throw 'Nombre de tabla invalido'}
  $hashes=@{};$rs=$db.OpenRecordset("SELECT Clave,Huella FROM SincronizacionFilas WHERE Tabla="+(Quote-Key $name),4)
  while(!$rs.EOF){$hashes[[string]$rs.Fields.Item('Clave').Value]=[string]$rs.Fields.Item('Huella').Value;$rs.MoveNext()};$rs.Close()
  $seen=@{}
  foreach($row in $payload.tables.$name){
   $key=[string]$row.values.ClaveRegistro;$seen[$key]=$true
   if ($hashes.ContainsKey($key) -and $hashes[$key] -eq [string]$row.hash){continue}
   $rs=$db.OpenRecordset("SELECT * FROM [$name] WHERE ClaveRegistro="+(Quote-Key $key),2)
   $new=$rs.EOF
   if($new){$rs.AddNew()}else{$rs.Edit()}
   foreach($field in $table.Value.PSObject.Properties){
    try {
    $value=$row.values.($field.Name);$type=[string]$field.Value
    if($null -eq $value){Set-Field $rs $field.Name ([DBNull]::Value)}
    elseif($type -eq 'CURRENCY'){Set-Field $rs $field.Name ([decimal]::Parse([string]$value,[Globalization.CultureInfo]::InvariantCulture))}
    elseif($type -eq 'DATETIME'){
     if($value -is [datetime]){Set-Field $rs $field.Name $value}
     else{Set-Field $rs $field.Name ([datetime]::ParseExact([string]$value,'yyyy-MM-ddTHH:mm:ss',[Globalization.CultureInfo]::InvariantCulture))}
    }
    elseif($type -eq 'YESNO'){Set-Field $rs $field.Name ([bool]$value)}
    elseif($type -eq 'LONG'){Set-Field $rs $field.Name ([int]$value)}
    elseif($type -eq 'DOUBLE'){Set-Field $rs $field.Name ([double]$value)}
    else{Set-Field $rs $field.Name ([string]$value)}
    }catch{throw "Error en $name.$($field.Name) ($type): $($_.Exception.Message)"}
   }
   $rs.Update();$rs.Close()
   $db.Execute('DELETE FROM SincronizacionFilas WHERE Tabla='+(Quote-Key $name)+' AND Clave='+(Quote-Key $key),128)
   $db.Execute('INSERT INTO SincronizacionFilas(Tabla,Clave,Huella) VALUES('+(Quote-Key $name)+','+(Quote-Key $key)+','+(Quote-Key ([string]$row.hash))+')',128)
   $changes++
  }
  foreach($key in @($hashes.Keys)){
   if (!$seen.ContainsKey($key)){
    $db.Execute("DELETE FROM [$name] WHERE ClaveRegistro="+(Quote-Key $key),128)
    $db.Execute('DELETE FROM SincronizacionFilas WHERE Tabla='+(Quote-Key $name)+' AND Clave='+(Quote-Key $key),128);$deleted++
   }
  }
 }
 $workspace.CommitTrans(1);$transaction=$false
 Write-Output (@{ok=$true;changed=$changes;deleted=$deleted;event=$payload.last_event}|ConvertTo-Json -Compress)
}catch{
 if($transaction){try{$workspace.Rollback()}catch{}}
 [Console]::Error.WriteLine($_.Exception.Message);exit 1
}finally{
 if($db){try{$db.Close()}catch{};[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($db)}
 if($workspace){[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($workspace)}
 if($engine){[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($engine)}
}
