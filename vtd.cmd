@echo off
setlocal
where py >nul 2>&1
if not errorlevel 1 (
    py -3 "%~dp0vtd.py" %*
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo VTD requires Python 3.10+. Install Python and enable its launcher or PATH option.
        pause
        exit /b 1
    )
    python "%~dp0vtd.py" %*
)
set "vtd_result=%errorlevel%"
if "%~1"=="" pause
exit /b %vtd_result%
