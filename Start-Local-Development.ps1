param([switch]$NoBrowser)
$ErrorActionPreference='Stop'
$taskRoot=$PSScriptRoot
$taskData=Join-Path $taskRoot '.local-data'
[IO.Directory]::CreateDirectory($taskData)|Out-Null
function Task-Runtime([string]$Name,[string]$Bundled){
 if(Test-Path -LiteralPath $Bundled){return $Bundled}
 $taskCommand=Get-Command $Name -ErrorAction SilentlyContinue
 if($taskCommand){return $taskCommand.Source}
 throw "$Name is required for local development."
}
try {
 $taskNode=Task-Runtime 'node.exe' (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')
 $taskPython=Task-Runtime 'python.exe' (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
 $taskVite=Join-Path $taskRoot 'node_modules\vite\bin\vite.js'
 if(!(Test-Path -LiteralPath $taskVite)){throw 'Install dependencies first: open a terminal in Online and run npm ci.'}
 $taskSeed=[IO.Path]::GetFullPath((Join-Path $taskRoot '..\..\Version B'))
 if(!(Test-Path -LiteralPath (Join-Path $taskSeed 'Trident-Quote-Settings.xlsx'))){$taskSeed=[IO.Path]::GetFullPath((Join-Path $taskRoot '..'))}
 $taskApiReady=$false
 try{$taskHealth=Invoke-RestMethod 'http://127.0.0.1:18782/api/health' -TimeoutSec 2;if($taskHealth.mode -ne 'local-development' -or $taskHealth.data -ne $taskData){throw 'Another app uses the local API port.'};$taskApiReady=$true}catch{if($_.Exception.Message -eq 'Another app uses the local API port.'){throw}}
 if(!$taskApiReady){
  $taskArguments=@(('"'+(Join-Path $taskRoot 'backend\dev_server.py')+'"'),'--data',('"'+$taskData+'"'),'--seed-folder',('"'+$taskSeed+'"'))
  $taskBackend=Start-Process -FilePath $taskPython -WindowStyle Hidden -WorkingDirectory $taskRoot -ArgumentList $taskArguments -PassThru -RedirectStandardError (Join-Path $taskData 'api-accounts-error.log') -RedirectStandardOutput (Join-Path $taskData 'api-accounts.log')
  $taskBackend.Id|Set-Content -LiteralPath (Join-Path $taskData 'api-accounts.pid')
 }
 $taskFrontendReady=$false
 try{$taskResponse=Invoke-WebRequest 'http://127.0.0.1:18780/' -UseBasicParsing -TimeoutSec 2;if($taskResponse.Content -notmatch '/@vite/client'){throw 'Another app uses the frontend port.'};$taskFrontendReady=$true}catch{if($_.Exception.Message -eq 'Another app uses the frontend port.'){throw}}
 if(!$taskFrontendReady){
  $taskFrontend=Start-Process -FilePath $taskNode -WindowStyle Hidden -WorkingDirectory $taskRoot -ArgumentList @(('"'+$taskVite+'"'),'--host','127.0.0.1','--port','18780','--strictPort') -PassThru -RedirectStandardError (Join-Path $taskData 'frontend-error.log') -RedirectStandardOutput (Join-Path $taskData 'frontend.log')
  $taskFrontend.Id|Set-Content -LiteralPath (Join-Path $taskData 'frontend.pid')
 }
 for($taskAttempt=0;$taskAttempt -lt 40;$taskAttempt++){
  try{$null=Invoke-RestMethod 'http://127.0.0.1:18782/api/health' -TimeoutSec 1;$null=Invoke-WebRequest 'http://127.0.0.1:18780/' -UseBasicParsing -TimeoutSec 1;if(!$NoBrowser){Start-Process 'http://127.0.0.1:18780/'};exit 0}catch{Start-Sleep -Milliseconds 250}
 }
 throw 'Local development did not start. Check the logs in Online\.local-data.'
}catch{
 Add-Type -AssemblyName System.Windows.Forms
 [Windows.Forms.MessageBox]::Show($_.Exception.Message,'Trident local development')|Out-Null
 exit 1
}
