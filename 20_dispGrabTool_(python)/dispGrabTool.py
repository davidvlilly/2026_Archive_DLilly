# dispGrabTool.py - Display Grab Tool
# Captures and displays the content of any selected open window.

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import win32gui
import win32con
import win32api
import dxcam
import pydirectinput
import ctypes
import time

class DispGrabTool:
    def __init__(self, root):
        self.root = root
        self.root.title("dispGrabTool")
        self.root.geometry("1200x800")
        self.root.configure(bg="#B0C4DE")

        # State
        self.target_hwnd = None
        self.target_title = ""
        self.photo = None  # prevent garbage collection

        # Menu bar
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)

        # Window menu (dynamic — refreshes when opened)
        self.window_menu = tk.Menu(self.menubar, tearoff=0,
                                   postcommand=self._refresh_window_menu)
        self.menubar.add_cascade(label="Window", menu=self.window_menu)

        # Grab menu
        self.grab_menu = tk.Menu(self.menubar, tearoff=0)
        self.grab_menu.add_command(label="Grab Window", command=self.grab_window)
        self.menubar.add_cascade(label="Grab", menu=self.grab_menu)

        # Action menu
        self.action_menu = tk.Menu(self.menubar, tearoff=0)
        self.action_menu.add_command(label="Mouse to Center", command=self.mouse_to_center)
        self.action_menu.add_command(label="Type Hello", command=self.type_hello)
        self.menubar.add_cascade(label="Action", menu=self.action_menu)

        # Main image canvas
        self.canvas = tk.Canvas(self.root, bg="#2B2B2B", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 0))

        # Status bar
        self.status_var = tk.StringVar(value="No window selected")
        self.status_bar = tk.Label(
            self.root, textvariable=self.status_var, bd=1,
            relief=tk.SUNKEN, anchor=tk.W, bg="#B0C4DE", padx=5
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)

    # ------------------------------------------------------------------
    # Window enumeration
    # ------------------------------------------------------------------
    def _get_windows(self):
        """Return list of real desktop windows (not hidden/background)."""
        windows = []
        def callback(hwnd, _):
            # Must be visible
            if not win32gui.IsWindowVisible(hwnd):
                return
            # Must have a title
            title = win32gui.GetWindowText(hwnd)
            if not title or title == self.root.title():
                return
            # Skip minimized windows
            if win32gui.IsIconic(hwnd):
                return
            # Must be a top-level app window (has WS_EX_APPWINDOW or no owner)
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if ex_style & win32con.WS_EX_TOOLWINDOW:
                return
            # Must have non-zero size
            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            if right <= left or bottom <= top:
                return
            # Skip off-screen windows (cloaked/virtual desktop)
            if right <= 0 or bottom <= 0:
                return
            windows.append({
                'hwnd': hwnd,
                'title': title,
                'rect': rect
            })
        win32gui.EnumWindows(callback, None)
        return windows

    def _refresh_window_menu(self):
        """Rebuild the Window menu with current visible windows."""
        self.window_menu.delete(0, tk.END)
        windows = self._get_windows()
        for w in windows:
            title = w['title']
            hwnd = w['hwnd']
            # Truncate long titles for the menu
            display = title if len(title) <= 60 else title[:57] + "..."
            self.window_menu.add_command(
                label=display,
                command=lambda h=hwnd, t=title: self._select_window(h, t)
            )

    def _select_window(self, hwnd, title):
        """Set the target window."""
        self.target_hwnd = hwnd
        self.target_title = title
        self.status_var.set(f"Selected: {title}")

    # ------------------------------------------------------------------
    # Grab
    # ------------------------------------------------------------------
    def grab_window(self):
        """Capture the target window and display in the canvas."""
        if not self.target_hwnd:
            messagebox.showinfo("Grab", "No window selected.\nUse Window menu first.")
            return

        try:
            rect = win32gui.GetWindowRect(self.target_hwnd)
        except Exception:
            messagebox.showerror("Grab", "Window no longer exists.")
            self.target_hwnd = None
            self.status_var.set("No window selected")
            return

        left, top, right, bottom = rect
        if right <= left or bottom <= top:
            messagebox.showerror("Grab", "Window has invalid size.")
            return

        camera = dxcam.create(region=(left, top, right, bottom))
        frame = None
        for _ in range(20):
            frame = camera.grab()
            if frame is not None:
                break
            time.sleep(0.05)
        del camera

        if frame is None:
            messagebox.showerror("Grab", "Failed to capture window.")
            return

        img = Image.fromarray(frame)

        # Scale to fit canvas while preserving aspect ratio
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw > 1 and ch > 1:
            img_w, img_h = img.size
            scale = min(cw / img_w, ch / img_h)
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
            img = img.resize((new_w, new_h), Image.LANCZOS)

        self.photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(
            cw // 2, ch // 2, anchor=tk.CENTER, image=self.photo
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def mouse_to_center(self):
        """Move the mouse to the center of the target window."""
        if not self.target_hwnd:
            messagebox.showinfo("Action", "No window selected.\nUse Window menu first.")
            return

        try:
            left, top, right, bottom = win32gui.GetWindowRect(self.target_hwnd)
        except Exception:
            messagebox.showerror("Action", "Window no longer exists.")
            self.target_hwnd = None
            self.status_var.set("No window selected")
            return

        cx = (left + right) // 2
        cy = (top + bottom) // 2
        pydirectinput.moveTo(cx, cy)
        self.status_var.set(f"Mouse moved to center of: {self.target_title}")

    def _force_foreground(self, hwnd):
        """Force a window to the foreground (works around Windows restrictions)."""
        # Restore if minimized
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        # Attach to the foreground thread to gain permission
        fore_thread = ctypes.windll.user32.GetWindowThreadProcessId(
            ctypes.windll.user32.GetForegroundWindow(), None
        )
        app_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        if fore_thread != app_thread:
            ctypes.windll.user32.AttachThreadInput(fore_thread, app_thread, True)
            win32gui.SetForegroundWindow(hwnd)
            ctypes.windll.user32.AttachThreadInput(fore_thread, app_thread, False)
        else:
            win32gui.SetForegroundWindow(hwnd)

    def type_hello(self):
        """Bring target window to front and type 'hello'."""
        if not self.target_hwnd:
            messagebox.showinfo("Action", "No window selected.\nUse Window menu first.")
            return

        try:
            self._force_foreground(self.target_hwnd)
        except Exception:
            messagebox.showerror("Action", "Could not focus window.")
            return

        time.sleep(0.5)
        # Use Win32 keybd_event for regular Windows apps (DirectInput won't work)
        for char in 'hello':
            vk = win32api.VkKeyScan(char) & 0xFF
            scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
            ctypes.windll.user32.keybd_event(vk, scan, 0, 0)
            time.sleep(0.03)
            ctypes.windll.user32.keybd_event(vk, scan, 2, 0)  # KEYEVENTF_KEYUP
            time.sleep(0.03)
        self.status_var.set(f"Typed 'hello' to: {self.target_title}")


def main():
    root = tk.Tk()
    app = DispGrabTool(root)
    root.mainloop()

if __name__ == "__main__":
    main()
