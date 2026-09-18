@echo off
python -m PyInstaller --clean --noconfirm --onefile --windowed --name "IG Compare" --distpath . --workpath build --specpath build --add-data "%~dp0lang;lang" main.py
