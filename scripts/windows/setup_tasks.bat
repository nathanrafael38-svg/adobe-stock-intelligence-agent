@echo off
rem One-time setup, double-click as Nathan (no admin needed). Touches only the items below.
rem 1) "Adobe Stock SFTP Upload": keep daily 09:30 start, repeat every 15 minutes for 24h.
rem 2) "Microstock Upscale Watch": new task, every 15 minutes, interactive (Upscayl needs the GPU).
rem 3) Startup-folder entry "Microstock autostart.bat": at logon, opens Claude desktop and Edge.
set "BASE=F:\2. Microstock\2. Setelah Edit\1. Gambar\1. Dari Claude"
set "LOG=%BASE%\_logs\setup_tasks.txt"
> "%LOG%" echo === setup %date% %time%
schtasks /Change /TN "Adobe Stock SFTP Upload" /RI 15 /DU 24:00 >>"%LOG%" 2>&1
>>"%LOG%" echo upload_change_exit=%ERRORLEVEL%
schtasks /Create /F /TN "Microstock Upscale Watch" /TR "\"%BASE%\_tools\upscale_watch.bat\"" /SC MINUTE /MO 15 /IT >>"%LOG%" 2>&1
>>"%LOG%" echo upscale_create_exit=%ERRORLEVEL%
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
> "%STARTUP%\Microstock autostart.bat" echo @call "%BASE%\_tools\autostart.bat"
>>"%LOG%" echo autostart_entry_exit=%ERRORLEVEL% in %STARTUP%
schtasks /Query /TN "Adobe Stock SFTP Upload" /V /FO LIST | findstr /I "TaskName Repeat Next Status Logon" >>"%LOG%" 2>&1
schtasks /Query /TN "Microstock Upscale Watch" /V /FO LIST | findstr /I "TaskName Repeat Next Status Logon" >>"%LOG%" 2>&1
dir /b "%STARTUP%\Microstock autostart.bat" >>"%LOG%" 2>&1
call "%BASE%\_tools\autostart.bat"
>>"%LOG%" echo autostart_test_run_done
>>"%LOG%" echo === done
echo Selesai. Hasil di %LOG%
pause
