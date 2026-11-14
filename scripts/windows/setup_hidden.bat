@echo off
rem One-time, double-click as Nathan (no admin, no password). Makes both watcher tasks run HIDDEN (no pop-up window).
rem Same schedule as before: Upload Watch every 10 minutes, Upscale Watch every 15 minutes, interactive (/IT).
set "BASE=F:\2. Microstock\2. Setelah Edit\1. Gambar\1. Dari Claude"
set "LOG=%BASE%\_logs\setup_hidden.txt"
> "%LOG%" echo === setup_hidden %date% %time%
schtasks /Create /F /TN "Microstock Upload Watch" /TR "wscript.exe \"%BASE%\_tools\run_hidden.vbs\" \"%BASE%\_tools\upload_watch.bat\"" /SC MINUTE /MO 10 /IT >>"%LOG%" 2>&1
>>"%LOG%" echo upload_watch_exit=%ERRORLEVEL%
schtasks /Create /F /TN "Microstock Upscale Watch" /TR "wscript.exe \"%BASE%\_tools\run_hidden.vbs\" \"%BASE%\_tools\upscale_watch.bat\"" /SC MINUTE /MO 15 /IT >>"%LOG%" 2>&1
>>"%LOG%" echo upscale_watch_exit=%ERRORLEVEL%
schtasks /Query /TN "Microstock Upload Watch" /V /FO LIST | findstr /I "TaskName Task To Run Repeat Next" >>"%LOG%" 2>&1
>>"%LOG%" echo === done
echo Selesai. Jendela watcher tidak akan muncul lagi. Hasil di %LOG%
pause
