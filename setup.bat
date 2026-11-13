@echo off
rem Create .venv and install dependencies (Windows).
rem PyPI's torch for Windows is the CPU build. For an NVIDIA GPU, install torch from
rem https://pytorch.org/get-started/locally/ into .venv afterwards.
cd /d "%~dp0"
py -3 -m venv .venv || python -m venv .venv || goto :error
.venv\Scripts\python.exe -m pip install -U pip || goto :error
.venv\Scripts\python.exe -m pip install -r requirements.txt || goto :error
echo Done. Start with run.bat
exit /b 0
:error
echo Setup failed.
exit /b 1
