@echo off
rem Copies the files listed in _UPLOAD_QUEUE_DT\csv\dreamstime-all.csv from the Day folders into _UPLOAD_QUEUE_DT.
rem Run once, then run dreamstime_upload.bat. Nothing is deleted from the Day folders.
setlocal
set "BASE=F:\2. Microstock\2. Setelah Edit\1. Gambar\1. Dari Claude"
powershell -NoProfile -Command "$q='%BASE%\_UPLOAD_QUEUE_DT'; $n=0; Import-Csv '%BASE%\_UPLOAD_QUEUE_DT\csv\dreamstime-all.csv' | ForEach-Object { $f=$_.Filename; $p=Get-ChildItem '%BASE%\Day *' -Recurse -File -Filter $f | Where-Object { $_.DirectoryName -notmatch '_original|_sent' } | Select-Object -First 1; if ($p) { Copy-Item $p.FullName $q -Force; $n++ } else { Write-Host ('TIDAK ADA: ' + $f) } }; Write-Host ('Disalin: ' + $n)"
pause
