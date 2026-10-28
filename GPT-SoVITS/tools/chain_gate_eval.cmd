@echo off
rem Auto eval chain after e16: synth 4 tags x 20 sentences + 3-gate scoring
if "%minimized%"=="" (
  set minimized=true
  start /min cmd /c "%~f0"
  exit
)
"F:\self_project\Sia-ai\GPT-SoVITS\GPT-SoVITS-v2pro-20261006\runtime\python.exe" "F:\self_project\Sia-ai\GPT-SoVITS\tools\chain_gate_eval.py" >> "F:\self_project\Sia-ai\GPT-SoVITS\_training\gate_chain_log.txt" 2>&1
