@echo off
rem RVC convert chain: wait train done -> convert 20 sentences -> score
if "%minimized%"=="" (
  set minimized=true
  start /min cmd /c "%~f0"
  exit
)
set PY=F:\self_project\Sia-ai\RVC\pkg\RVC20260718Nvidia\runtime\python.exe
set LOG=F:\self_project\Sia-ai\RVC\convert_log.txt
echo [%date% %time%] start convert chain >> %LOG%
%PY% F:\self_project\Sia-ai\GPT-SoVITS\tools\chain_svc_convert.py >> %LOG% 2>&1
echo [%date% %time%] chain exit >> %LOG%
