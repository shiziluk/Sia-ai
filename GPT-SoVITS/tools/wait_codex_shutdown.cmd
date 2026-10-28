@echo off
rem Watch codex++ task, shutdown when idle / exited / 120min cap
if "%minimized%"=="" (
  set minimized=true
  start /min cmd /c "%~f0"
  exit
)
"F:\self_project\Sia-ai\GPT-SoVITS\GPT-SoVITS-v2pro-20261006\runtime\python.exe" "F:\self_project\Sia-ai\GPT-SoVITS\tools\wait_codex_then_shutdown.py" >> "F:\self_project\Sia-ai\GPT-SoVITS\_training\wait_codex_log.txt" 2>&1
