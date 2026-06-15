@echo off
REM Runs the daily brief once (gather -> write -> post a Substack draft) and logs it.
REM This is what the scheduled task fires each weekday morning. Double-click to run by hand.
cd /d "%~dp0"
if not exist out mkdir out
echo. >> out\run.log
echo ===== %date% %time% ===== >> out\run.log
".venv\Scripts\python.exe" run.py --post >> out\run.log 2>&1
