@echo off
rem ===========================================================================
rem update_docs.bat - rebuild the numbers, figures and README from results\
rem Run after fpga\build.bat, after host\board_bench.py, or after the regression.
rem ===========================================================================
setlocal
rem Double-clicked in Explorer: keep the window open at the end so the output can be read.
set "NRV_PAUSE="
echo %cmdcmdline% | findstr /i /c:"%~nx0" >nul && set "NRV_PAUSE=1"
cd /d "%~dp0"
py tools\collect_results.py || goto fail
py tools\make_figures.py    || goto fail
py tools\make_readme.py     || goto fail
echo.
echo update_docs: done. See docs\RESULTS.md and README.md
((if defined NRV_PAUSE pause) & exit /b 0)
:fail
echo update_docs: FAILED at the step above
((if defined NRV_PAUSE pause) & exit /b 1)
