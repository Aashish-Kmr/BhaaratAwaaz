@echo off
REM ====================================================================
REM  BAIF Bhasha -- one-click start on Windows.
REM
REM  Double-click this file. It builds the container image if needed,
REM  starts the app, waits for it to answer, and opens the browser.
REM
REM  Requires Docker Desktop (WSL2 backend) to be installed and running.
REM ====================================================================

setlocal
cd /d "%~dp0"

docker version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   Docker isn't running.
    echo.
    echo   Start Docker Desktop, wait for the whale icon in the system tray
    echo   to stop animating, then run this file again.
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    echo.
    echo   No .env file found -- creating one from .env.example.
    copy /y ".env.example" ".env" >nul
    echo.
    echo   Open .env in Notepad and paste your Hugging Face token after
    echo   HF_TOKEN=  ^(see DOCKER.md^), then run this file again.
    echo.
    notepad ".env"
    pause
    exit /b 1
)

set BAIF_HOST_PORT=8000
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /i "%%A"=="BAIF_HOST_PORT" set BAIF_HOST_PORT=%%B
)

echo.
echo   Building and starting BAIF Bhasha...
echo   The first run downloads several GB of models -- it can take a while.
echo.

REM /k, not /c: if the build fails, the window has to stay open long
REM enough to read why.
start "BAIF Bhasha" cmd /k "docker compose up --build"

echo   Waiting for the app to come up on http://localhost:%BAIF_HOST_PORT% ...
for /l %%i in (1,1,240) do (
    curl -s -o nul http://localhost:%BAIF_HOST_PORT%/api/health && goto :ready
    timeout /t 5 /nobreak >nul
)

echo.
echo   Still not answering. Check the other window for what it's doing --
echo   a first-run model download legitimately takes 10-40 minutes.
pause
exit /b 1

:ready
echo   Ready. Opening the browser.
start "" http://localhost:%BAIF_HOST_PORT%
exit /b 0
