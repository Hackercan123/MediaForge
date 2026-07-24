@echo off
rem MediaForge.exe derleme betigi (PyInstaller)
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name MediaForge ^
  --icon ikon.ico ^
  --add-data "ikon.ico;." ^
  MediaForge.py
echo.
echo Cikti: dist\MediaForge.exe
pause
