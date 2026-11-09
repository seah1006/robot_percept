param([string]$Server,[string]$Out,[string]$Tracker,[string]$Video,[double]$Bs,[double]$Be,[double]$Secs,[string]$Label)
foreach($v in "PYTHONHOME","PYTHONPATH","VIRTUAL_ENV","PIP_PREFIX","PYTHONNOUSERSITE"){ Remove-Item "Env:$v" -ErrorAction SilentlyContinue }
$py="C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe"
& $py "C:\Users\USER\AppData\Local\Temp\vt3\bin\r3_recover.py" --server $Server --out $Out --tracker $Tracker --video $Video --bs $Bs --be $Be --secs $Secs --label $Label
