@echo off
setlocal
set "ROOT=%~dp0.."
set "STATE=%LOCALAPPDATA%\dsh-multicad"
set "VENV=%STATE%\venv"

if not exist "%STATE%" mkdir "%STATE%" >nul 2>&1

if not exist "%VENV%\Scripts\python.exe" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\bin\setup.ps1" >> "%STATE%\setup.log" 2>&1
)

if not exist "%VENV%\Scripts\python.exe" (
  echo multicad: Python environment setup failed. See "%STATE%\setup.log" 1>&2
  exit /b 1
)

"%VENV%\Scripts\python.exe" "%ROOT%\python\src\server.py"
