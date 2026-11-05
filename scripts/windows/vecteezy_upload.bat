@echo off
rem Vecteezy SFTP upload. Double-click to run manually (test), or run from Task Scheduler later.
rem Photos only (Vecteezy takes no illustrations). Files to send sit in _UPLOAD_QUEUE_VZ\.
rem Login is a site saved in WinSCP (named Vecteezy). No password is in any file here or in the repo.
rem After a successful upload (WinSCP exit 0) the files move to _UPLOAD_QUEUE_VZ\_sent\.
setlocal
set "BASE=F:\2. Microstock\2. Setelah Edit\1. Gambar\1. Dari Claude"
set "Q=%BASE%\_UPLOAD_QUEUE_VZ"
set "RUNLOG=%BASE%\_logs\vecteezy_runs.log"
if not exist "%BASE%\_logs" mkdir "%BASE%\_logs"
if not exist "%Q%\_sent" mkdir "%Q%\_sent"
if not exist "%BASE%\_tools\vecteezy_site.txt" (
  >>"%RUNLOG%" echo %date% %time% ERROR _tools\vecteezy_site.txt not found
  echo vecteezy_site.txt tidak ditemukan di _tools
  pause
  exit /b 3
)
if not exist "%Q%\*.jpg" (
  >>"%RUNLOG%" echo %date% %time% nothing to upload
  echo Tidak ada file di _UPLOAD_QUEUE_VZ
  pause
  exit /b 0
)
"C:\Program Files (x86)\WinSCP\WinSCP.com" /log="%BASE%\_logs\vecteezy_winscp.log" /script="%BASE%\_tools\vecteezy_site.txt"
set "RC=%ERRORLEVEL%"
>>"%RUNLOG%" echo %date% %time% winscp exit %RC%
if "%RC%"=="0" (
  move /Y "%Q%\*.jpg" "%Q%\_sent\" >nul
  >>"%RUNLOG%" echo %date% %time% moved uploaded files to _sent
  echo Upload selesai.
) else (
  echo Upload gagal, kode %RC%. Lihat _logs\vecteezy_winscp.log
)
pause
exit /b %RC%
