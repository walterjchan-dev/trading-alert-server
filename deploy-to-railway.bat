@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo Deploy TradingView server to Railway
echo ========================================
echo.

where git >nul 2>nul
if errorlevel 1 (
    echo Git was not found. Install Git for Windows first.
    goto error
)

set "MESSAGE=%~1"
if not defined MESSAGE set "MESSAGE=Update TradingView Telegram server"

echo Adding server files...
git add main.py requirements.txt portfolio.json deploy-to-railway.bat
if errorlevel 1 goto error

git diff --cached --quiet
if errorlevel 1 (
    echo Creating deployment commit...
    git commit -m "%MESSAGE%"
    if errorlevel 1 goto error
) else (
    echo No new server changes need to be committed.
)

echo.
echo Syncing with GitHub...
git pull --rebase --autostash origin main
if errorlevel 1 goto error

echo.
echo Pushing to GitHub...
git push origin main
if errorlevel 1 goto error

echo.
echo Deployment pushed successfully.
echo Railway should redeploy automatically.
echo.
pause
exit /b 0

:error
echo.
echo Deployment did not complete.
echo Read the message above or send Codex a screenshot.
echo.
pause
exit /b 1
