@echo off
rem Final audition chain: wait e8 -> synth 4 rounds -> auto shutdown
if "%minimized%"=="" (
  set minimized=true
  start /min cmd /c "%~f0"
  exit
)
"F:\self_project\Sia-ai\GPT-SoVITS\GPT-SoVITS-v2pro-20261006\runtime\python.exe" "F:\self_project\Sia-ai\GPT-SoVITS\tools\final_audition_and_shutdown.py" >> "F:\self_project\Sia-ai\GPT-SoVITS\_training\final_audition_log.txt" 2>&1
