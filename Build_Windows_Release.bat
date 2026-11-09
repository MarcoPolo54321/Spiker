@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0Build_Spiker_Windows_Installer.bat"
exit /b %ERRORLEVEL%
