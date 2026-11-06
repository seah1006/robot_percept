param([string]$Transport,[string]$Label,[double]$Seconds,[string]$Url,[string]$OutDir,[string[]]$Extra=@())
foreach($v in "PYTHONHOME","PYTHONPATH","VIRTUAL_ENV","PIP_PREFIX","PYTHONNOUSERSITE"){ Remove-Item "Env:$v" -ErrorAction SilentlyContinue }
$env:OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS="0"
New-Item -ItemType Directory -Force $OutDir | Out-Null
$py="C:\Users\my\rp_tracker\venv\Scripts\python.exe"; $sd="C:\Users\my\Documents\sam_camera"
$a=@("-u","C:\Users\my\rp_tracker\vj_new\teleop_tracker_win.py","--mode","humanoid","--url",$Url,"--video","$sd\stock\stock_person_720p30.mp4","--loop-video","--seconds",$Seconds,"--model","$sd\models\hand_landmarker.task","--pose-model","$sd\models\pose_landmarker_lite.task","--metrics-out","$OutDir\$Label.metrics.json")
if($Transport -ne "default"){ $a += @("--transport",$Transport) }
$a += $Extra
$p=Start-Process -FilePath $py -ArgumentList $a -PassThru -NoNewWindow -RedirectStandardOutput "$OutDir\$Label.stdout.txt" -RedirectStandardError "$OutDir\$Label.stderr.txt"
$p.WaitForExit(); "exit=$($p.ExitCode)" | Set-Content "$OutDir\$Label.exit.txt"
