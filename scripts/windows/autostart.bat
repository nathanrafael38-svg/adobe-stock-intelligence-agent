@echo off
rem Runs at Windows logon (task "Microstock Autostart"). Opens what the Claude runs need:
rem the Claude desktop app (file bridge) and Edge (Claude extension, Flow + Adobe sign-ins).
set "BASE=F:\2. Microstock\2. Setelah Edit\1. Gambar\1. Dari Claude"
set "LOG=%BASE%\_logs\autostart.log"
>>"%LOG%" echo %date% %time% logon
set "CLAUDE="
for %%P in ("%LOCALAPPDATA%\AnthropicClaude\claude.exe" "%LOCALAPPDATA%\Programs\Claude\Claude.exe" "%LOCALAPPDATA%\Programs\claude-desktop\Claude.exe" "%ProgramFiles%\Claude\Claude.exe") do (
  if not defined CLAUDE if exist "%%~P" set "CLAUDE=%%~P"
)
if defined CLAUDE (
  tasklist /FI "IMAGENAME eq claude.exe" | find /I "claude.exe" >nul || start "" "%CLAUDE%"
  >>"%LOG%" echo   claude: %CLAUDE%
) else (
  >>"%LOG%" echo   claude: NOT FOUND - start it manually once and tell Claude the path
)
tasklist /FI "IMAGENAME eq msedge.exe" | find /I "msedge.exe" >nul || start "" msedge
>>"%LOG%" echo   edge: started or already running
exit /b 0
