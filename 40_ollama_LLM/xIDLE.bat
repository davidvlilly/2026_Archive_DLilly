@echo off
REM ============================================================
REM xIDLE.bat - Launch Python IDLE with venv00 activated,
REM             working directory set to dispGrabTool.
REM ============================================================

cd /d C:\Users\david\_Main\30_WinGrab_Tool\dispGrabTool
call C:\Users\david\_Main\_python\venv00\Scripts\activate.bat
start pythonw -m idlelib.idle
