@echo off
rem RVC maya voice model train chain (unattended)
rem Preprocess/f0/hubert-feature already done manually (logs/maya_svc ready)
rem Step0: wait for GPU free (eval chain done, s1_train exited)
rem Step1: train 200 epochs (v2 40k, bs4)
rem Step2: build faiss index
if "%minimized%"=="" (
  set minimized=true
  start /min cmd /c "%~f0"
  exit
)
set PKG=F:\self_project\Sia-ai\RVC\pkg\RVC20260718Nvidia
set LOG=F:\self_project\Sia-ai\RVC\train_log.txt
set PY=%PKG%\runtime\python.exe
set EXP=maya_svc
cd /d %PKG%

echo [%date% %time%] step0 wait gpu >> %LOG%
%PY% F:\self_project\Sia-ai\GPT-SoVITS\tools\wait_rvc_gpu.py >> %LOG% 2>&1

echo [%date% %time%] step1 train 200ep >> %LOG%
%PY% train/train.py -e %EXP% -sr 40k -f0 1 -bs 4 -te 200 -se 50 -pg assets/pretrained_v2/f0G40k.pth -pd assets/pretrained_v2/f0D40k.pth -l 1 -c 0 -sw 1 -v v2 >> %LOG% 2>&1
if errorlevel 1 goto :fail

echo [%date% %time%] step2 index >> %LOG%
%PY% train/train_index.py %EXP% v2 logs 4 >> %LOG% 2>&1

echo [%date% %time%] ALL DONE >> %LOG%
exit /b 0

:fail
echo [%date% %time%] FAILED (see log above) >> %LOG%
exit /b 1
