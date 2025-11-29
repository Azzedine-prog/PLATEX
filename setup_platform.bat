@echo off
setlocal

set SCRIPT_DIR=%~dp0
set PS_SCRIPT=%SCRIPT_DIR%setup_platform.ps1

if not exist "%PS_SCRIPT%" (
  echo Cannot find setup_platform.ps1 next to this batch file. Please keep both files together.
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*
if %ERRORLEVEL% neq 0 (
  echo Installation failed. Please review the messages above.
  exit /b %ERRORLEVEL%
)

echo.
echo ========================================
echo Launch complete. Services should be starting.
echo Visit http://localhost:3000 after Docker finishes warming up.
echo ========================================
