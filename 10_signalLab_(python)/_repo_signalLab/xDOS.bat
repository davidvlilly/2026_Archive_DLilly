@echo off
REM ============================================================
REM xDOS.bat - Open a new DOS terminal with the Python virtual
REM            environment (venv00) activated.
REM ============================================================

start cmd /k "call C:\Users\david\_Main\_python\venv00\Scripts\activate.bat && cd /d C:\Users\david\_Main\10_repo_2025\10_signalLab\_repo_signalLab"

:: Misc Command References
:: python --version
:: pip list
:: python.exe -m pip install --upgrade pip
:: pip install numpy==1.26.3 --only-binary=:all:
:: pip freeze > requirements.txt
