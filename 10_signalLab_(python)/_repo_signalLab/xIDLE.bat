@echo off
REM ============================================================
REM xIDLE.bat - Launch Python IDLE with venv00 activated,
REM             working directory set to the signalLab project.
REM ============================================================

cd /d C:\Users\david\_Main\10_repo_2025\10_signalLab\_repo_signalLab
call C:\Users\david\_Main\_python\venv00\Scripts\activate.bat
start pythonw -m idlelib.idle
