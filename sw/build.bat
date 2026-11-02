@echo off
rem build.bat - build the boot ROM and the C programs on Windows (no make needed)
rem Usage: sw\build.bat [target ...]   targets: boot hello switches_leds seg7_counter timer_irq dhrystone coremark
setlocal
rem Double-clicked in Explorer: keep the window open at the end so the output can be read.
set "NRV_PAUSE="
echo %cmdcmdline% | findstr /i /c:"%~nx0" >nul && set "NRV_PAUSE=1"
py "%~dp0build.py" %*
set "NRV_RC=%errorlevel%"
if defined NRV_PAUSE pause
exit /b %NRV_RC%
