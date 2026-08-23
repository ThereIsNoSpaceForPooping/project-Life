$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$base = "e:\008其他\桌面\WEB\project-Life\简历"

& $chrome --headless --disable-gpu --print-to-pdf="$base\杨泽众-Agent-v1.pdf" --no-margins --run-all-compositor-stages-before-draw "file:///e:/008其他/桌面/WEB/project-Life/简历/杨泽众-Agent-v1-backup.html" 2>&1
Write-Host "v1 done"

& $chrome --headless --disable-gpu --print-to-pdf="$base\杨泽众-Agent-v2.pdf" --no-margins --run-all-compositor-stages-before-draw "file:///e:/008其他/桌面/WEB/project-Life/简历/杨泽众-Agent-双栏-backup.html" 2>&1
Write-Host "v2 done"
