@echo off
rem Dreamstime FTP upload. Double-click to run, or run from Task Scheduler.
rem Files to send sit in _UPLOAD_QUEUE_DT\ (JPGs) and _UPLOAD_QUEUE_DT\csv\ (dreamstime-metadata.csv).
rem Login is a site saved in WinSCP named "Dreamstime" (FTP, passive, host upload.dreamstime.com).
rem No password is in any file here or in the repo.
rem Order (Dreamstime rule): JPGs first, wait 5 minutes until they reach "Unfinished", then the CSV.
setlocal
set "BASE=F:\2. Microstock\2. Setelah Edit\1. Gambar\1. Dari Claude"
set "Q=%BASE%\_UPLOAD_QUEUE_DT"
set "RUNLOG=%BASE%\_logs\dreamstime_runs.log"
set "WINSCP=C:\Program Files (x86)\WinSCP\WinSCP.com"
if not exist "%BASE%\_logs" mkdir "%BASE%\_logs"
if not exist "%Q%\_sent" mkdir "%Q%\_sent"
if not exist "%Q%\csv" mkdir "%Q%\csv"
if not exist "%Q%\*.jpg" if not exist "%Q%\csv\*.csv" (
  >>"%RUNLOG%" echo %date% %time% nothing to upload
  echo Tidak ada file di _UPLOAD_QUEUE_DT
  pause
  exit /b 0
)
if exist "%Q%\*.jpg" (
  "%WINSCP%" /log="%BASE%\_logs\dreamstime_winscp.log" /script="%BASE%\_tools\dreamstime_jpg.txt"
  if errorlevel 1 (
    >>"%RUNLOG%" echo %date% %time% ERROR jpg upload failed
    echo Upload JPG gagal. Lihat _logs\dreamstime_winscp.log
    pause
    exit /b 1
  )
  move /Y "%Q%\*.jpg" "%Q%\_sent\" >nul
  >>"%RUNLOG%" echo %date% %time% jpg uploaded, waiting 300 s before csv
  echo JPG terkirim. Menunggu 5 menit sebelum CSV...
  timeout /t 300 /nobreak >nul
)
if exist "%Q%\csv\*.csv" (
  "%WINSCP%" /log="%BASE%\_logs\dreamstime_winscp.log" /script="%BASE%\_tools\dreamstime_csv.txt"
  if errorlevel 1 (
    >>"%RUNLOG%" echo %date% %time% ERROR csv upload failed
    echo Upload CSV gagal. Lihat _logs\dreamstime_winscp.log
    pause
    exit /b 2
  )
  move /Y "%Q%\csv\*.csv" "%Q%\_sent\" >nul
  >>"%RUNLOG%" echo %date% %time% csv uploaded
)
echo Upload Dreamstime selesai.
pause
exit /b 0
