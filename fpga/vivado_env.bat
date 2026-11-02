@echo off
rem ===========================================================================
rem vivado_env.bat - find Vivado 2018.2 and put it on PATH for this window
rem ---------------------------------------------------------------------------
rem Set VIVADO_DIR yourself if Vivado is not in C:\Xilinx\Vivado\2018.2.
rem ===========================================================================
if "%VIVADO_DIR%"=="" set "VIVADO_DIR=C:\Xilinx\Vivado\2018.2"
if not exist "%VIVADO_DIR%\settings64.bat" (
  echo ERROR: %VIVADO_DIR%\settings64.bat not found. Set VIVADO_DIR first, e.g.
  echo        set VIVADO_DIR=D:\Xilinx\Vivado\2018.2
  exit /b 1
)
call "%VIVADO_DIR%\settings64.bat"
