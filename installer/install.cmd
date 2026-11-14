@echo off
setlocal
pushd "%~dp0.."
where py.exe >nul 2>nul
if errorlevel 1 (
    python.exe -X utf8 -m tehnet.cli %*
) else (
    py.exe -3 -X utf8 -m tehnet.cli %*
)
set "TEHNET_EXIT=%ERRORLEVEL%"
popd
exit /b %TEHNET_EXIT%
