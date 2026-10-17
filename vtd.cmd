@echo off
setlocal
if not "%~1"=="" goto run
rem Keep the console open after success, failure or an unexpected script exit.
"%ComSpec%" /d /k ""%~f0" --vtd-console"
exit /b

:run
if not defined VTD_LOG_FILE set "VTD_LOG_FILE=%TEMP%\vtd-installer-%RANDOM%-%RANDOM%.log"
echo VTD local test installer - no Python required
echo Log file: "%VTD_LOG_FILE%"
set "vtd_powershell=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if exist "%vtd_powershell%" goto launch
echo VTD could not find Windows PowerShell. Run this tool on a supported Windows installation.
exit /b 1

:launch
if "%~1"=="--vtd-console" goto menu
"%vtd_powershell%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install-windows.ps1" %*
goto finished
:menu
"%vtd_powershell%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install-windows.ps1" --menu

:finished
set "vtd_result=%errorlevel%"
echo VTD finished with exit code %vtd_result%.
echo Log file: "%VTD_LOG_FILE%"
exit /b %vtd_result%
