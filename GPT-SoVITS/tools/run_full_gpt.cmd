@echo off
rem 全量 GPT 训练启动器(schtasks 用): 固化环境变量, 避免会话差异
rem 自最小化: 防止训练控制台窗口被误关(窗口关闭=训练进程被杀)
if "%minimized%"=="" (
  set minimized=true
  start /min cmd /c "%~f0"
  exit
)
set _CUDA_VISIBLE_DEVICES=0
set hz=25hz
set TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1
cd /d F:\self_project\Sia-ai\GPT-SoVITS\GPT-SoVITS-v2pro-20261006
"runtime\python.exe" -s GPT_SoVITS/s1_train.py --config_file tmp_s1_full.yaml >> F:\self_project\Sia-ai\GPT-SoVITS\_training\gpt_full_log.txt 2>> F:\self_project\Sia-ai\GPT-SoVITS\_training\gpt_full_err.txt
