@echo off
rem Upscale watcher, run by Windows Task Scheduler every 15 minutes (interactive
rem user session: Upscayl uses the GPU through Vulkan).
rem Orchestrator drops C{N}_kk.jpg into _UPSCALE\in ; this writes _UPSCALE\out\C{N}_kk.jpg
rem and moves the input to _UPSCALE\done. It never touches any other folder.
setlocal enabledelayedexpansion
set "BASE=F:\2. Microstock\2. Setelah Edit\1. Gambar\1. Dari Claude"
set "IN=%BASE%\_UPSCALE\in"
set "OUT=%BASE%\_UPSCALE\out"
set "DONE=%BASE%\_UPSCALE\done"
set "LOG=%BASE%\_logs\upscale_runs.log"
set "SCALE=2"
rem --- locate upscayl-bin (set UPSCAYL_DIR to override) ---
if not defined UPSCAYL_DIR set "UPSCAYL_DIR=%LOCALAPPDATA%\Programs\Upscayl\resources"
if not exist "%UPSCAYL_DIR%\bin\upscayl-bin.exe" set "UPSCAYL_DIR=C:\Program Files\Upscayl\resources"
if not exist "%UPSCAYL_DIR%\bin\upscayl-bin.exe" (
  >>"%LOG%" echo %date% %time% ERROR upscayl-bin.exe not found
  exit /b 3
)
if not defined UPSCAYL_MODEL set "UPSCAYL_MODEL=upscayl-standard-4x"
for %%D in ("%IN%" "%OUT%" "%DONE%") do if not exist "%%~D" mkdir "%%~D"
if not exist "%IN%\*.jpg" exit /b 0
for %%F in ("%IN%\*.jpg") do (
  if exist "%OUT%\%%~nxF" (
    >>"%LOG%" echo %date% %time% skip %%~nxF already in out
  ) else (
    "%UPSCAYL_DIR%\bin\upscayl-bin.exe" -i "%%~fF" -o "%OUT%\%%~nF.tmp.jpg" -s %SCALE% -m "%UPSCAYL_DIR%\models" -n %UPSCAYL_MODEL% -f jpg >>"%LOG%" 2>&1
    if errorlevel 1 (
      >>"%LOG%" echo %date% %time% ERROR upscale failed %%~nxF
    ) else (
      move /Y "%OUT%\%%~nF.tmp.jpg" "%OUT%\%%~nxF" >nul
      move /Y "%%~fF" "%DONE%\%%~nxF" >nul
      >>"%LOG%" echo %date% %time% upscaled %%~nxF x%SCALE% model %UPSCAYL_MODEL%
    )
  )
)
exit /b 0
