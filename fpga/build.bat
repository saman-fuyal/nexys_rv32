@echo off
rem ===========================================================================
rem build.bat - run fpga\scripts\build.tcl with Vivado 2018.2 in batch mode
rem Usage: fpga\build.bat [pipe^|mc]     (default core: params.json default_core)
rem Log  : fpga\build\build.log
rem ===========================================================================
setlocal
rem Double-clicked in Explorer: keep the window open at the end so the output can be read.
set "NRV_PAUSE="
echo %cmdcmdline% | findstr /i /c:"%~nx0" >nul && set "NRV_PAUSE=1"
cd /d "%~dp0.."
call fpga\vivado_env.bat || ((if defined NRV_PAUSE pause) & exit /b 1)
if not exist fpga\build mkdir fpga\build
call vivado -mode batch -nojournal -log fpga\build\build.log -source fpga\scripts\build.tcl -tclargs %1
if errorlevel 1 (
  echo build FAILED - see fpga\build\build.log
  ((if defined NRV_PAUSE pause) & exit /b 1)
)
set "NRV_RC=%errorlevel%"
if defined NRV_PAUSE pause
exit /b %NRV_RC%
