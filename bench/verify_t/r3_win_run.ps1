# V-T3 Windows tracker one window. -Transport ws|http -Label x -Seconds 30 -Url ... -OutDir ... -Video path -Mode humanoid|panda -Tracker path
param([string]$Transport,[string]$Label,[double]$Seconds,[string]$Url,[string]$OutDir,[string]$Video,[string]$Mode="humanoid",[string]$Tracker,[switch]$NoLoop)
foreach($v in "PYTHONHOME","PYTHONPATH","VIRTUAL_ENV","PIP_PREFIX","PYTHONNOUSERSITE"){ Remove-Item "Env:$v" -ErrorAction SilentlyContinue }
$env:OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS="0"
New-Item -ItemType Directory -Force $OutDir | Out-Null
$py="C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe"
$sd="C:\Users\USER\Documents\sam_camera"
$a=@("-u",$Tracker,"--mode",$Mode,"--transport",$Transport,"--url",$Url,"--video",$Video,"--seconds",$Seconds,"--model","$sd\models\hand_landmarker.task","--pose-model","$sd\models\pose_landmarker_lite.task","--metrics-out","$OutDir\$Label.metrics.json")
if(-not $NoLoop){$a+="--loop-video"}
$p=Start-Process -FilePath $py -ArgumentList $a -PassThru -NoNewWindow -RedirectStandardOutput "$OutDir\$Label.stdout.txt" -RedirectStandardError "$OutDir\$Label.stderr.txt"
$t0=Get-Date; $sys=@(); $cpu=0
while(-not $p.HasExited){ try{ $pp=Get-Process -Id $p.Id -ErrorAction Stop; $cpu=$pp.TotalProcessorTime.TotalSeconds }catch{}; try{ $sys += (Get-Counter "\Processor(_Total)\% Processor Time" -SampleInterval 1 -MaxSamples 1).CounterSamples[0].CookedValue }catch{ Start-Sleep 1 } }
$p.WaitForExit(); $wall=((Get-Date)-$t0).TotalSeconds; $cores=[Environment]::ProcessorCount
$r=[ordered]@{label=$Label;exit=$p.ExitCode;wall_s=[math]::Round($wall,2);proc_cpu_s_last_sample=[math]::Round($cpu,2);logical_cores=$cores;proc_cpu_pct_of_1core=[math]::Round($cpu/$wall*100,1);sys_cpu_mean_pct=if($sys.Count){[math]::Round(($sys|Measure-Object -Average).Average,1)}else{$null};sys_samples=$sys.Count}
$r | ConvertTo-Json | Set-Content "$OutDir\$Label.wincpu.json"
