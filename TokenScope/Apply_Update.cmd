@echo off
setlocal
where py.exe >nul 2>nul
if errorlevel 1 goto python_path
py -3 "%~dp0tools\apply_update.py"
goto done
:python_path
python "%~dp0tools\apply_update.py"
:done
set "update_result=%errorlevel%"
pause
exit /b %update_result%
