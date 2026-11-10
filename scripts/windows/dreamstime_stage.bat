@echo off
rem Copies the files named in _tools\dreamstime_list.txt from the Day folders into _UPLOAD_QUEUE_DT. Plain cmd, no PowerShell.
setlocal
set "BASE=F:\2. Microstock\2. Setelah Edit\1. Gambar\1. Dari Claude"
set /a ok=0
set /a miss=0
for /f "usebackq delims=" %%f in ("%BASE%\_tools\dreamstime_list.txt") do (
  set "found="
  for /d %%d in ("%BASE%\Day *") do if exist "%%d\%%f" (copy /Y "%%d\%%f" "%BASE%\_UPLOAD_QUEUE_DT\" >nul & set "found=1")
  if defined found (set /a ok+=1) else (echo TIDAK ADA: "%%f" & set /a miss+=1)
)
echo Disalin: %ok%   Tidak ada: %miss%
pause
