@echo off
rem Copies the photos listed in _tools\vecteezy_list.txt from the Day folders into _UPLOAD_QUEUE_VZ.
rem Run once, then run vecteezy_upload.bat.
setlocal
set "BASE=F:\2. Microstock\2. Setelah Edit\1. Gambar\1. Dari Claude"
powershell -NoProfile -Command "$q='%BASE%\_UPLOAD_QUEUE_VZ'; $n=0; Get-Content '%BASE%\_tools\vecteezy_list.txt' | Where-Object { $_.Trim() } | ForEach-Object { $f=$_.Trim(); $p=Get-ChildItem '%BASE%\Day *' -Recurse -File -Filter $f | Where-Object { $_.DirectoryName -notmatch '_original|_sent' } | Select-Object -First 1; if ($p) { Copy-Item $p.FullName $q -Force; $n++ } else { Write-Host ('TIDAK ADA: ' + $f) } }; Write-Host ('Disalin: ' + $n)"
pause
