$d='\\wsl.localhost\Ubuntu-24.04\home\user\work\robot_percept\bench\verify_t'
$py='C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe'
foreach($v in "PYTHONHOME","PYTHONPATH","VIRTUAL_ENV","PIP_PREFIX","PYTHONNOUSERSITE"){ Remove-Item "Env:$v" -ErrorAction SilentlyContinue }; $env:OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS="0"
$srv=Start-Process $py -ArgumentList "$d\r3_dummy_server.py",5199 -PassThru -WindowStyle Hidden; Start-Sleep 2
$sd='C:\Users\USER\Documents\sam_camera'; $T='C:\Users\USER\AppData\Local\Temp\vt3\ver'; $out="$d\out_r3\hand_regress"
foreach($n in 'teleop_round3','teleop_round3_direct','teleop_round3_hand_reprocess','teleop_test','teleop_test_fast'){
 foreach($m in 'humanoid'){
  $o = & $py -u "$T\t_cur.py" --mode $m --video "$sd\$n.mp4" --url http://127.0.0.1:5199 --model "$sd\models\hand_landmarker.task" --pose-model "$sd\models\pose_landmarker_lite.task" 2>$null
  $j = ($o | ? { $_ -like '{*' } | select -Last 1) | ConvertFrom-Json
  "{0}.mp4 {1} frames={2} hand={3:N1}% pose={4:N1}%" -f $n,$m,$j.updates,(100*$j.hand_detection_rate),(100*$j.pose_detection_rate) | Out-File -Append "$out\pipeline_rates.txt"
 }}
Stop-Process -Id $srv.Id
