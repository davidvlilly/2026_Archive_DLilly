================================================================================
  Retirement Simulation Tool
================================================================================

  Description:
    Generates year-by-year retirement financial projections based on
    input parameters. Allows comparison of two plans with graphical
    output and PDF report generation.

  Usage:
    1. Run xDOS.bat to open a terminal with the virtual environment
    2. python mainRetSim00.py

================================================================================
  PYTHON LIBRARIES
================================================================================

  PyQt5 5.15.11
    GUI framework. Provides the main window, input fields, buttons,
    group boxes, and layout management for the application interface.
    pip install PyQt5

  matplotlib 3.10.8
    Plotting library. Generates comparison charts of retirement
    projections embedded in the PyQt5 window via the Qt5Agg backend.
    pip install matplotlib

  reportlab 4.4.10
    PDF generation. Creates formatted PDF reports containing input
    parameters, comparison tables, and embedded plot images.
    pip install reportlab

  Built-in modules (no install needed):
    sys, csv, io

================================================================================
  VIRTUAL ENVIRONMENT
================================================================================

    Path: C:\Users\david\_Main\_python\venv00
    Python: 3.12.8

    Install all dependencies:
      pip install PyQt5 matplotlib reportlab

================================================================================
