# Windows 쪽 트래커 1창 실행. Aside 런타임 환경변수 제거, CPU% 기록.
param([string]$Transport,[string]$Label,[double]$Seconds,[string]$Url,[string]$OutDir)
foreach($v in "PYTHONHOME","PYTHONPATH","VIRTUAL_ENV","PIP_PREFIX","PYTHONNOUSERSITE"){ Remove-Item "Env:$v" -ErrorAction SilentlyContinue }
$env:OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS="0"
New-Item -ItemType Directory -Force $OutDir | Out-Null
$py="C:\Users\my\rp_tracker\venv\Scripts\python.exe"
$sd="C:\Users\my\Documents\sam_camera"
$args2=@("-u","$sd\teleop_tracker_win.py","--mode","humanoid","--transport",$Transport,"--url",$Url,"--video","$sd\stock\stock_person_720p30.mp4","--loop-video","--seconds",$Seconds,"--model","$sd\models\hand_landmarker.task","--pose-model","$sd\models\pose_landmarker_lite.task","--metrics-out","$OutDir\$Label.metrics.json")
$p=Start-Process -FilePath $py -ArgumentList $args2 -PassThru -NoNewWindow -RedirectStandardOutput "$OutDir\$Label.stdout.txt" -RedirectStandardError "$OutDir\$Label.stderr.txt"
$h=$p.Handle
$t0=Get-Date; $sys=@()
while(-not $p.HasExited){ try{ $sys += (Get-Counter "\Processor(_Total)\% Processor Time" -SampleInterval 1 -MaxSamples 1).CounterSamples[0].CookedValue }catch{ Start-Sleep 1 } }
$p.WaitForExit(); $wall=((Get-Date)-$t0).TotalSeconds
$cores=[Environment]::ProcessorCount
$cpu=$p.TotalProcessorTime.TotalSeconds
$r=[ordered]@{label=$Label;exit=$p.ExitCode;wall_s=[math]::Round($wall,2);proc_cpu_s=[math]::Round($cpu,2);logical_cores=$cores;proc_cpu_pct_of_total=[math]::Round($cpu/$wall/$cores*100,1);proc_cpu_pct_of_1core=[math]::Round($cpu/$wall*100,1);sys_cpu_mean_pct=if($sys.Count){[math]::Round(($sys|Measure-Object -Average).Average,1)}else{$null};sys_cpu_max_pct=if($sys.Count){[math]::Round(($sys|Measure-Object -Maximum).Maximum,1)}else{$null};sys_samples=$sys.Count}
$r | ConvertTo-Json | Set-Content "$OutDir\$Label.wincpu.json"
