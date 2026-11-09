param([string]$Url,[string]$Mode,[string]$OutDir,[string]$Label)
foreach($v in "PYTHONHOME","PYTHONPATH","VIRTUAL_ENV","PIP_PREFIX","PYTHONNOUSERSITE"){ Remove-Item "Env:$v" -ErrorAction SilentlyContinue }
$env:OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS="0"
New-Item -ItemType Directory -Force $OutDir | Out-Null
$py="C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe"
& $py "C:\Users\USER\AppData\Local\Temp\vt3\bin\camera_acceptance.py" --url $Url --mode $Mode --seconds 30 --output "$OutDir\$Label.json"
