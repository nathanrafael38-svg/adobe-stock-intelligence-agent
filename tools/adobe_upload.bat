@echo off
rem Adobe Stock SFTP upload, run by Windows Task Scheduler.
rem Orchestrator writes a batch into _UPLOAD_QUEUE\_incoming\ and writes
rem READY.flag LAST. Only then are the files moved (same-volume rename,
rem atomic per file) into the queue root that WinSCP uploads. A half-written
rem batch is therefore never uploaded. Files left in the root after a failed
rem upload are retried on the next run.
setlocal
set "BASE=F:\2. Microstock\2. Setelah Edit\1. Gambar\1. Dari Claude"
set "Q=%BASE%\_UPLOAD_QUEUE"
set "IN=%Q%\_incoming"
set "RUNLOG=%BASE%\_logs\upload_runs.log"
if not exist "%BASE%\_logs" mkdir "%BASE%\_logs"
if not exist "%IN%" mkdir "%IN%"

if not exist "%IN%\READY.flag" goto upload
if not exist "%IN%\*.jpg" goto clearflag
move /Y "%IN%\*.jpg" "%Q%\" >nul
if errorlevel 1 goto movefailed
>>"%RUNLOG%" echo %date% %time% promoted batch from _incoming
:clearflag
del "%IN%\READY.flag"
goto upload

:movefailed
>>"%RUNLOG%" echo %date% %time% ERROR move from _incoming failed, READY.flag kept
exit /b 2

:upload
if not exist "%Q%\*.jpg" (
  >>"%RUNLOG%" echo %date% %time% nothing to upload
  exit /b 0
)
"C:\Program Files (x86)\WinSCP\WinSCP.com" /log="%BASE%\_logs\winscp.log" /script="%BASE%\_tools\adobe_upload.txt"
set "RC=%ERRORLEVEL%"
>>"%RUNLOG%" echo %date% %time% winscp exit %RC%
exit /b %RC%
