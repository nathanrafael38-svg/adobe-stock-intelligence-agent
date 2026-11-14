@echo off
rem Microstock upload watcher (Task Scheduler "Microstock Upload Watch", every 10 minutes).
rem The orchestrator (/upload) copies photos into _UPLOAD_QUEUE_VZ and _UPLOAD_QUEUE_DT and writes
rem READY.flag in that queue LAST. This script sees the flag and runs the existing upload script.
rem Adobe has its own task ("Adobe Stock SFTP Upload") and is not touched here.
rem No password is in this file: logins are the sites saved in WinSCP.
setlocal
set "BASE=F:\2. Microstock\2. Setelah Edit\1. Gambar\1. Dari Claude"
set "RUNLOG=%BASE%\_logs\upload_watch.log"
set "NOPAUSE=1"
if not exist "%BASE%\_logs" mkdir "%BASE%\_logs"

if exist "%BASE%\_UPLOAD_QUEUE_VZ\READY.flag" (
  >>"%RUNLOG%" echo %date% %time% vecteezy: READY.flag found, starting upload
  call "%BASE%\_tools\vecteezy_upload.bat" >nul 2>&1
  if not exist "%BASE%\_UPLOAD_QUEUE_VZ\*.jpg" (
    del "%BASE%\_UPLOAD_QUEUE_VZ\READY.flag"
    >>"%RUNLOG%" echo %date% %time% vecteezy: queue empty, flag removed
  ) else (
    >>"%RUNLOG%" echo %date% %time% vecteezy: files left, flag kept for retry
  )
)

if exist "%BASE%\_UPLOAD_QUEUE_DT\READY.flag" (
  >>"%RUNLOG%" echo %date% %time% dreamstime: READY.flag found, starting upload
  call "%BASE%\_tools\dreamstime_upload.bat" >nul 2>&1
  if not exist "%BASE%\_UPLOAD_QUEUE_DT\*.jpg" if not exist "%BASE%\_UPLOAD_QUEUE_DT\csv\*.csv" (
    del "%BASE%\_UPLOAD_QUEUE_DT\READY.flag"
    >>"%RUNLOG%" echo %date% %time% dreamstime: queue empty, flag removed
  ) else (
    >>"%RUNLOG%" echo %date% %time% dreamstime: files left, flag kept for retry
  )
)
exit /b 0
