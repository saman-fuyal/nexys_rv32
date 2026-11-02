@echo off
rem run_sim.bat - regression on Windows. Extra arguments go to sim\run_sim.py, e.g. --quick
rem Icarus Verilog from C:\iverilog is added to PATH if it is not there already.
setlocal
rem Double-clicked in Explorer: keep the window open at the end so the output can be read.
set "NRV_PAUSE="
echo %cmdcmdline% | findstr /i /c:"%~nx0" >nul && set "NRV_PAUSE=1"
where iverilog >nul 2>nul || if exist C:\iverilog\bin\iverilog.exe set "PATH=C:\iverilog\bin;%PATH%"
py "%~dp0sim\run_sim.py" %*
set "NRV_RC=%errorlevel%"
if defined NRV_PAUSE pause
exit /b %NRV_RC%
