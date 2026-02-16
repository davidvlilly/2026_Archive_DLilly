================================================================================
  dispGrabTool - Display Grab Tool
================================================================================

  Description:
    A Python GUI tool that captures and displays the screen content of
    any selected open window. Also provides mouse and keyboard control
    to interact with the selected window.

  Capability:
    - Lists all active, visible desktop windows in a pull-down menu
    - Captures a screenshot of the selected window using DirectX and
      displays it scaled in the main image area
    - Moves the mouse cursor to the center of the selected window
    - Sends keyboard input ('hello') to the selected window by
      forcing focus and simulating key presses
    - Status bar shows the currently selected window

  Usage:
    1. Run xDOS.bat to open a terminal with the virtual environment
    2. python dispGrabTool.py
    3. Window menu   -> select a target window
    4. Grab menu     -> capture and display its content
    5. Action menu   -> move mouse or type to the target window

================================================================================
  PYTHON LIBRARIES
================================================================================

  tkinter (built-in)
    GUI framework. Provides the main window, pull-down menus, canvas
    for image display, and status bar.

  Pillow (PIL)
    Image processing. Converts captured screen frames to Tkinter-
    compatible images. Handles scaling with LANCZOS resampling.
    pip install pillow

  pywin32 (win32gui, win32con, win32api)
    Windows API bindings. Used to enumerate open windows, get window
    positions and sizes, check window styles, force foreground focus,
    and simulate keyboard input via keybd_event.
    pip install pywin32

  dxcam
    DirectX-based screen capture. Captures window content as numpy
    arrays using GPU-accelerated DirectX duplication. Faster and more
    reliable than PIL-based screen capture.
    pip install dxcam

  pydirectinput
    DirectInput mouse control. Moves the mouse cursor to absolute
    screen coordinates. Uses DirectInput which works with both regular
    applications and games.
    pip install pydirectinput

  ctypes (built-in)
    Low-level Windows API access. Used for thread attachment to force
    window focus, and for MapVirtualKey / keybd_event calls to send
    keyboard input that regular Windows applications respond to.

================================================================================
  VIRTUAL ENVIRONMENT
================================================================================

    Path: C:\Users\david\_Main\_python\venv00
    Python: 3.12.8

    Install all dependencies:
      pip install pillow pywin32 dxcam pydirectinput

================================================================================
