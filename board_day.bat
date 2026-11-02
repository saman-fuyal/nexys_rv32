@echo off
rem ===========================================================================
rem board_day.bat - the board-day sequence in one window, stopping at the first
rem problem. Usage: board_day.bat [pipe^|mc]   (default pipe)
rem Before: fpga\build.bat pipe has made the bitstream; board on, JP1 on JTAG,
rem cable in J6 PROG/UART, SW15 down. Details: docs\BRINGUP.md
rem ===========================================================================
setlocal
rem Double-clicked in Explorer: keep the window open at the end so the output can be read.
set "NRV_PAUSE="
echo %cmdcmdline% | findstr /i /c:"%~nx0" >nul && set "NRV_PAUSE=1"
cd /d "%~dp0"
set CORE=%1
if "%CORE%"=="" set CORE=pipe

echo === 1/5 preflight
py tools\preflight.py
if errorlevel 1 (
  echo Fix the MISSING lines above, then run board_day.bat again.
  ((if defined NRV_PAUSE pause) & exit /b 1)
)

echo === 2/5 program the FPGA with the %CORE% core
call fpga\program.bat %CORE% || goto fail
echo The 7-segment display should now show B0070001 and LED15 should be on.
pause

echo === 3/5 first program: hello
py host\rvload.py sw\prebuilt\hello.elf --port auto --expect "Hello from nexys_rv32!" --timeout 15 || goto fail
echo The display should now show 00C0FFEE.

echo === 4/5 measurements: hello, timer_irq, dhrystone, coremark (about 2 minutes)
py host\board_bench.py --port auto || goto fail
echo === 4b/5 on-board self-test against the golden model (about 10 minutes)
py host\board_hil.py --port auto || goto fail

echo === 5/5 rebuild the numbers and documents
call update_docs.bat || goto fail
echo.
echo board_day: ALL DONE.
((if defined NRV_PAUSE pause) & exit /b 0)
:fail
echo.
echo board_day: stopped. Look up the last message in docs\BRINGUP.md, section "If something fails".
((if defined NRV_PAUSE pause) & exit /b 1)
