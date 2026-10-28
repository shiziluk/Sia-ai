@echo off
rem openclaw gateway service reinstall + start, run by schtasks as user
(
  echo === uninstall ===
  openclaw gateway uninstall
  echo === install ===
  openclaw gateway install
  echo === start ===
  openclaw gateway start
  echo === probe ===
  openclaw gateway status
) > F:\self_project\Sia-ai\_gw_start.log 2>&1
