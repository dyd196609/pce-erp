@echo off
chcp 65001 >nul
setlocal
set "SCRIPT_DIR=%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start_schema_rehearsal.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo SCHEMA REHEARSAL ENVIRONMENT = READY
) else (
  echo SCHEMA REHEARSAL ENVIRONMENT = BLOCKED
)
echo.
pause
exit /b %EXIT_CODE%
