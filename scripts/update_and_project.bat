@echo off
REM Tier 1 (Windows): double-click to run update then project.
REM Place this file inside the repo at scripts\update_and_project.bat
REM (or keep a Desktop shortcut that sets the working directory to the repo root).
REM Double-click in Explorer. The console stays open with the output.

cd /d "%~dp0.."
echo === WNBA props: update + project ===
echo Repo: %CD%
echo.

where uv >nul 2>&1
if errorlevel 1 (
  echo ERROR: uv not found on PATH. Install from https://docs.astral.sh/uv/ then retry.
  pause
  exit /b 1
)

echo --- uv run python run.py update ---
uv run python run.py update
if errorlevel 1 goto :fail

echo.
echo --- uv run python run.py check-staleness ---
uv run python run.py check-staleness
if errorlevel 1 goto :fail

echo.
echo --- uv run python run.py project ---
uv run python run.py project
if errorlevel 1 goto :fail

echo.
echo === Done ===
pause
exit /b 0

:fail
echo.
echo === FAILED (see messages above) ===
pause
exit /b 1
