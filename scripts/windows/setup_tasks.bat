@echo off
rem One-time setup, double-click as Nathan. Changes only these two tasks.
rem 1) "Adobe Stock SFTP Upload": keep daily 09:30 start, repeat every 15 minutes for 24h.
rem 2) "Microstock Upscale Watch": new task, every 15 minutes, interactive (Upscayl needs the GPU).
set "BASE=F:\2. Microstock\2. Setelah Edit\1. Gambar\1. Dari Claude"
set "LOG=%BASE%\_logs\setup_tasks.txt"
> "%LOG%" echo === setup %date% %time%
schtasks /Change /TN "Adobe Stock SFTP Upload" /RI 15 /DU 24:00 >>"%LOG%" 2>&1
>>"%LOG%" echo upload_change_exit=%ERRORLEVEL%
schtasks /Create /F /TN "Microstock Upscale Watch" /TR "\"%BASE%\_tools\upscale_watch.bat\"" /SC MINUTE /MO 15 /IT >>"%LOG%" 2>&1
>>"%LOG%" echo upscale_create_exit=%ERRORLEVEL%
schtasks /Query /TN "Adobe Stock SFTP Upload" /V /FO LIST | findstr /I "TaskName Repeat Next Status Logon" >>"%LOG%" 2>&1
schtasks /Query /TN "Microstock Upscale Watch" /V /FO LIST | findstr /I "TaskName Repeat Next Status Logon" >>"%LOG%" 2>&1
>>"%LOG%" echo === done
echo Selesai. Hasil di %LOG%
pause
