@echo off
setlocal
chcp 65001 >nul 2>&1

rem Thin wrapper: resolves its own directory (works with spaces and
rem parentheses in the path, e.g. "...My Drive (rolevc@gmail.com)...")
rem and hands off to the real logic in scripts\Start-RoleOS.ps1.
set "SCRIPT_DIR=%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%scripts\Start-RoleOS.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo ROLE OS failed to start. See the message above, or check:
    echo   "%SCRIPT_DIR%dashboard\var\role_os_dashboard\launcher.log"
    echo.
    pause
)

exit /b %EXIT_CODE%
