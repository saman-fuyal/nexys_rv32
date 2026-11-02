@echo off
rem ===========================================================================
rem program.bat - run fpga\scripts\program.tcl with Vivado 2018.2 in batch mode
rem Usage: fpga\program.bat [pipe^|mc]     (default core: params.json default_core)
rem Log  : fpga\build\program.log
rem ===========================================================================
setlocal
rem Double-clicked in Explorer: keep the window open at the end so the output can be read.
set "NRV_PAUSE="
echo %cmdcmdline% | findstr /i /c:"%~nx0" >nul && set "NRV_PAUSE=1"
cd /d "%~dp0.."
call fpga\vivado_env.bat || ((if defined NRV_PAUSE pause) & exit /b 1)
if not exist fpga\build mkdir fpga\build
call vivado -mode batch -nojournal -log fpga\build\program.log -source fpga\scripts\program.tcl -tclargs %1
if errorlevel 1 (
  echo program FAILED - see fpga\build\program.log
  ((if defined NRV_PAUSE pause) & exit /b 1)
)
set "NRV_RC=%errorlevel%"
if defined NRV_PAUSE pause
exit /b %NRV_RC%
