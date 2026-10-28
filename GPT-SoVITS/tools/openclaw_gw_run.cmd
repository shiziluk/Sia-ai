@echo off
if "%minimized%"=="" (
  set minimized=true
  start /min cmd /c "%~f0"
  exit
)
openclaw gateway run --port 18789 >> F:\self_project\Sia-ai\_gw_run.log 2>&1
