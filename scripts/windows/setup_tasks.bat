@echo off
rem One-time setup, double-click as Nathan (no admin needed). Touches only the items below.
rem 1) (removed) changing the existing Adobe task asked for the Windows password. Adobe is now sent by "Microstock Upload Watch".
rem 2) "Microstock Upscale Watch": new task, every 15 minutes, interactive (Upscayl needs the GPU).
rem 3) "Microstock Upload Watch": new task, every 10 minutes, interactive (no password), sends Adobe, Vecteezy and Dreamstime when their READY.flag exists.
rem 4) Startup-folder entry "Microstock autostart.bat": at logon, opens Claude desktop and Edge.
set "BASE=F:\2. Microstock\2. Setelah Edit\1. Gambar\1. Dari Claude"
set "LOG=%BASE%\_logs\setup_tasks.txt"
> "%LOG%" echo === setup %date% %time%
schtasks /Create /F /TN "Microstock Upscale Watch" /TR "\"%BASE%\_tools\upscale_watch.bat\"" /SC MINUTE /MO 15 /IT >>"%LOG%" 2>&1
>>"%LOG%" echo upscale_create_exit=%ERRORLEVEL%
schtasks /Create /F /TN "Microstock Upload Watch" /TR "\"%BASE%\_tools\upload_watch.bat\"" /SC MINUTE /MO 10 /IT >>"%LOG%" 2>&1
>>"%LOG%" echo upload_watch_create_exit=%ERRORLEVEL%
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
> "%STARTUP%\Microstock autostart.bat" echo @call "%BASE%\_tools\autostart.bat"
>>"%LOG%" echo autostart_entry_exit=%ERRORLEVEL% in %STARTUP%
schtasks /Query /TN "Microstock Upload Watch" /V /FO LIST | findstr /I "TaskName Repeat Next Status Logon" >>"%LOG%" 2>&1
schtasks /Query /TN "Microstock Upscale Watch" /V /FO LIST | findstr /I "TaskName Repeat Next Status Logon" >>"%LOG%" 2>&1
dir /b "%STARTUP%\Microstock autostart.bat" >>"%LOG%" 2>&1
call "%BASE%\_tools\autostart.bat"
>>"%LOG%" echo autostart_test_run_done
>>"%LOG%" echo === done
echo Selesai. Hasil di %LOG%
pause
