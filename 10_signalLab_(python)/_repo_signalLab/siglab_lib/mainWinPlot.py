# siglab_lib/mainWinPlot.py
import os
import tkinter as tk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk

class MainWindowPlotter:
    def __init__(self, app):
        """
        Initialize the plotter
        
        Parameters:
        - app: Main application instance
        """
        self.app = app

    def create_plot_area(self):
        """
        Create figure, canvas, and toolbar for the plot
        """
        # Create figure and canvas
        self.app.fig, self.app.ax = plt.subplots(figsize=(15, 8)) 
        self.app.fig.patch.set_facecolor('#B0C4DE') 
        self.app.ax.set_facecolor('#E6EDF3') 
        self.app.ax.grid(True,linestyle='--',color='darkgray') 
        
        self.app.canvas = FigureCanvasTkAgg(self.app.fig, master=self.app.root)
        self.app.canvas_widget = self.app.canvas.get_tk_widget()
        self.app.canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        
        # Add navigation toolbar
        self.app.toolbar = NavigationToolbar2Tk(self.app.canvas, self.app.root)
        
        # Remove the Zoom button
        for child in self.app.toolbar.winfo_children():
            if isinstance(child, tk.Checkbutton) and 'Zoom' in str(child):
                child.pack_forget()  # Hide the Zoom button
        
        self.app.toolbar.update()
        self.app.toolbar.pack(side=tk.TOP, fill=tk.X)

    def plot_data(self, rescale=True):
        """
        Plot signal data with optional rescaling
        
        Parameters:
        - rescale: Whether to reset view to full data range
        """
        # Capture current view limits before clearing
        current_xlim = self.app.ax.get_xlim()
        current_ylim = self.app.ax.get_ylim()

        self.app.ax.clear()

        # Plot main signal FIRST (gray line in the background)
        self.app.ax.plot(self.app.time_S, self.app.magR, color='gray', zorder=1)

        # Plot state markers ON TOP of the signal line
        for state_val, state_info in self.app.state_colors.items():
            # Find indices for this state
            state_mask = self.app.tag_state == state_val
            state_time = self.app.time_S[::30][state_mask]
            state_mag = self.app.magR[::30][state_mask]

            self.app.ax.scatter(state_time, state_mag, 
                                color=state_info['color'], 
                                label=state_info['name'],
                                s=10,
                                zorder=2) 

        # Set plot title using case file name
        self.app.ax.set_title(f'Signal: {os.path.basename(self.app.filepath)}')
        
        # Set x and y axis labels
        self.app.ax.set_xlabel('Time (s)')
        self.app.ax.set_ylabel('Magnitude (magR)')

        # Autoscale or restore previous limits
        if rescale:
            self.app.ax.set_xlim(self.app.time_S[0], self.app.time_S[-1])
            self.app.ax.set_ylim(
                self.app.magR.min() - abs(self.app.magR.min()) * 0.05,
                self.app.magR.max() + abs(self.app.magR.max()) * 0.05
            )
        else:
            # Restore previous view limits
            self.app.ax.set_xlim(current_xlim)
            self.app.ax.set_ylim(current_ylim)

        # Re-apply grid settings
        self.app.ax.grid(True, linestyle='--', color='darkgray')

        # Adjust plot margins
        self.app.fig.tight_layout(pad=1.0)

        self.app.ax.legend()
        self.app.canvas.draw()