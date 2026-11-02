@echo off
rem preflight.bat - check this PC for board day (changes nothing). See docs\BRINGUP.md
setlocal
rem Double-clicked in Explorer: keep the window open at the end so the output can be read.
set "NRV_PAUSE="
echo %cmdcmdline% | findstr /i /c:"%~nx0" >nul && set "NRV_PAUSE=1"
where iverilog >nul 2>nul || if exist C:\iverilog\bin\iverilog.exe set "PATH=C:\iverilog\bin;%PATH%"
py "%~dp0tools\preflight.py" %*
set "NRV_RC=%errorlevel%"
if defined NRV_PAUSE pause
exit /b %NRV_RC%
