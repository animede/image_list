@echo off
rem Start the server, then open http://127.0.0.1:7870 in a browser.
rem   PowerShell needs ".\": .\run.bat  /  set variables with $env:NAME = "value"
rem   CPU (default):  run.bat            (below-normal priority, 8 threads, 140 image tokens)
rem   GPU:            set CUDA_VISIBLE_DEVICES=0 ^& run.bat
rem   Folders:        set IMAGE_ROOTS=C:\Users\me\Pictures;D:\photos ^& run.bat
rem   CPU cores:      set CPU_AFFINITY=FF ^& run.bat   (hex mask; FF = first 8 logical CPUs)
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist .venv\Scripts\uvicorn.exe (
  echo Run setup.bat first.
  exit /b 1
)
if not defined PORT set PORT=7870
if defined CUDA_VISIBLE_DEVICES goto :gpu
rem Hide GPUs so the CPU is used.
set CUDA_VISIBLE_DEVICES=-1
if not defined EMBED_THREADS set EMBED_THREADS=8
set OMP_NUM_THREADS=%EMBED_THREADS%
rem Priority and CPU_AFFINITY are applied inside Python (embedder.py).
rem "start /b /low" is not used because it makes Ctrl+C stop working.
.venv\Scripts\uvicorn.exe server:app --host 127.0.0.1 --port %PORT%
exit /b %errorlevel%
:gpu
.venv\Scripts\uvicorn.exe server:app --host 127.0.0.1 --port %PORT%
