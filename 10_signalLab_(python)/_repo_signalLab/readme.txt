================================================================================
  SignalLab - Project Reference
================================================================================

  Description:
    Python GUI tool for viewing, editing, and analyzing IVRB (Intravenous
    RF Blood) system signals used to detect blood clot formations.
    Built with Tkinter and Matplotlib.

  Virtual Environment:
    C:\Users\david\_Main\_python\venv00  (Python 3.12.8)

================================================================================
  BATCH FILES
================================================================================

  xDOS.bat
    Opens a CMD terminal with venv00 activated, working directory set to
    this project folder. Run the app with: python signalLab.py

  xIDLE.bat
    Launches Python IDLE with venv00 activated, working directory set to
    this project folder. Useful for interactive development and debugging.

================================================================================
  PYTHON LIBRARIES (installed in venv00)
================================================================================

  numpy 1.26.3
    Numerical array operations. Used for all signal data storage and
    manipulation (magR, time_S, tag_state arrays).

  h5py 3.15.1
    HDF5 file I/O. Used to read and write .f5b signal files containing
    signal magnitude, time series, and state annotations.

  matplotlib 3.10.8
    Plotting and visualization. Provides the embedded plot canvas in the
    main window, all time-series plots, and scatter plots.

  scipy 1.16.3
    Scientific computing. Used for linear regression in Higuchi fractal
    dimension calculations and sinusoidal curve fitting (L-BFGS-B optimizer).

  tkinter (built-in)
    GUI framework. Provides the main window, menus, toolbar buttons,
    and dialog boxes. Included with Python, no separate install needed.

================================================================================
