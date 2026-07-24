@echo off
rem dist\ icerigini paylasilabilir zip'e cevirir (ayarlar.json haric —
rem kisisel yol/tercih icerir, pakete girmemeli)
cd /d "%~dp0"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\MediaForge.exe','dist\bin' -DestinationPath 'MediaForge-portable.zip' -Force"
echo.
echo Cikti: MediaForge-portable.zip
pause
