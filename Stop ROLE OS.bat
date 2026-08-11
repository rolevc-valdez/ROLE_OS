@echo off
setlocal
chcp 65001 >nul 2>&1

rem Thin wrapper: resolves its own directory (works with spaces and
rem parentheses in the path) and hands off to scripts\Stop-RoleOS.ps1.
set "SCRIPT_DIR=%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%scripts\Stop-RoleOS.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
pause

exit /b %EXIT_CODE%
