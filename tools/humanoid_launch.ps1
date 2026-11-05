param([int]$Port=5091,[switch]$DryRun,[string]$Python='python',[string]$TrackerRoot="$env:USERPROFILE\Documents\sam_camera")
$ErrorActionPreference='Stop'
if($Port -eq 5080){throw '5080 is reserved for the user server'}
if($Port -lt 1024 -or $Port -gt 65535){throw 'Invalid port'}
$repo='/home/user/work/robot_percept'
$tracker=Join-Path $TrackerRoot 'teleop_tracker_win.py'
$server="source /home/user/anaconda3/etc/profile.d/conda.sh; conda activate robot_percept; cd $repo; source sim_test/gl_env.sh; export HOST=0.0.0.0 PYTHONPATH=`$PWD; if ss -ltn | grep -q ':$Port '; then echo 'Port occupied, refusing duplicate'; read -r; exit 1; fi; PORT=$Port PERCEPTION=stub python -m web.app"
$trackerCommand="& '$($Python.Replace("'","''"))' '$($tracker.Replace("'","''"))' --url http://localhost:$Port --mode humanoid --seconds 0"
if($DryRun){Write-Output "SERVER: wsl -d Ubuntu-24.04 -- bash -lc $server";Write-Output "TRACKER: $trackerCommand";Write-Output "Tracker exists: $(Test-Path -LiteralPath $tracker)";exit 0}
if(!(Test-Path -LiteralPath $tracker)){throw "Missing tracker: $tracker. Copy tools/teleop_tracker_win.py here first."}
$encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes("wsl -d Ubuntu-24.04 -- bash -lc '"+$server.Replace("'","''")+"'"))
Start-Process powershell.exe -ArgumentList '-NoExit','-EncodedCommand',$encoded
$encodedTracker=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($trackerCommand))
Start-Process powershell.exe -ArgumentList '-NoExit','-EncodedCommand',$encodedTracker