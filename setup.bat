@echo off
rem Create .venv and install dependencies (Windows).
rem torch is installed from the CPU-only index. For an NVIDIA GPU:
rem   $env:TORCH_INDEX = "https://download.pytorch.org/whl/cu128"; .\setup.bat
setlocal
cd /d "%~dp0"
if not defined TORCH_INDEX set TORCH_INDEX=https://download.pytorch.org/whl/cpu
py -3 -m venv .venv || python -m venv .venv || goto :error
.venv\Scripts\python.exe -m pip install -U pip || goto :error
.venv\Scripts\python.exe -m pip install torch torchvision --index-url %TORCH_INDEX% || goto :error
.venv\Scripts\python.exe -m pip install -r requirements.txt || goto :error
echo Done. Start with .\run.bat (PowerShell) or run.bat (cmd)
exit /b 0
:error
echo Setup failed.
exit /b 1
