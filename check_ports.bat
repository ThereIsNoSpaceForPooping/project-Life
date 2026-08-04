@echo off
setlocal
echo === Port Check (8001 8002 8005 3000) ===
netstat -an | findstr LISTENING | findstr ":8001 :8002 :8005 :3000"
echo === Process Check (python node) ===
tasklist | findstr /i "python.exe node.exe"
