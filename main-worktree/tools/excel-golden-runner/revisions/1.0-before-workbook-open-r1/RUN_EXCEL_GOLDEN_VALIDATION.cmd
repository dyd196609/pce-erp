@echo off
setlocal
chcp 65001 >nul
title PCE Excel Golden Validation
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_excel_golden_validation.ps1" %*
set "PCE_GOLDEN_EXIT=%ERRORLEVEL%"
exit /b %PCE_GOLDEN_EXIT%
