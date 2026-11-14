@echo off
call "%~dp0installer\install.cmd" --serve --router auto --port 0 %*
