@echo off
rem dist\ klasorunu paylasilabilir tek zip'e cevirir
cd /d "%~dp0"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\*' -DestinationPath 'MediaForge-portable.zip' -Force"
echo.
echo Cikti: MediaForge-portable.zip
pause
