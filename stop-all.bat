@echo off
chcp 65001 >nul
echo Stopping all services...
taskkill /F /IM python.exe 2>nul
taskkill /F /IM node.exe 2>nul
echo All services stopped!
pause
