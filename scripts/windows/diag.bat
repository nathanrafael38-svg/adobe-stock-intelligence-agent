@echo off
rem Read-only diagnostics for microstock pipeline setup. Writes to _logs\diag_*.txt
set "BASE=F:\2. Microstock\2. Setelah Edit\1. Gambar\1. Dari Claude"
set "OUT=%BASE%\_logs\diag.txt"
> "%OUT%" echo === diag %date% %time%
>>"%OUT%" echo === whoami
whoami >>"%OUT%" 2>&1
>>"%OUT%" echo === ver
ver >>"%OUT%" 2>&1
>>"%OUT%" echo === where python/py/exiftool/winget/upscayl
where python py exiftool winget >>"%OUT%" 2>&1
python --version >>"%OUT%" 2>&1
py -0p >>"%OUT%" 2>&1
>>"%OUT%" echo === upscayl candidates
dir /b "%LOCALAPPDATA%\Programs\Upscayl" >>"%OUT%" 2>&1
dir /b "C:\Program Files\Upscayl" >>"%OUT%" 2>&1
dir /s /b "%LOCALAPPDATA%\Programs\Upscayl\resources\bin" >>"%OUT%" 2>&1
dir /s /b "C:\Program Files\Upscayl\resources\bin" >>"%OUT%" 2>&1
>>"%OUT%" echo === WinSCP
dir /b "C:\Program Files (x86)\WinSCP\WinSCP.com" >>"%OUT%" 2>&1
>>"%OUT%" echo === Downloads (Flow 2K files, names only, newest 15)
dir /b /o-d "%USERPROFILE%\Downloads\*_2K_*.jpg" 2>nul | more +0 > "%TEMP%\dl.txt"
powershell -NoProfile -Command "Get-Content $env:TEMP\dl.txt -TotalCount 15" >>"%OUT%" 2>&1
>>"%OUT%" echo === power settings (sleep)
powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE >>"%OUT%" 2>&1
>>"%OUT%" echo === scheduled tasks (verbose CSV, non-Microsoft)
schtasks /query /fo csv /v > "%BASE%\_logs\diag_tasks.csv" 2>&1
>>"%OUT%" echo === done
