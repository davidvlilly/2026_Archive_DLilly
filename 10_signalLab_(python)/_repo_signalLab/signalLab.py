import os
import sys
import tkinter as tk
from tkinter import messagebox
import numpy as np
import h5py
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.widgets import RectangleSelector
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
from siglab_lib.mainWinSupport import InteractionModes, ToolbarUtils
from siglab_lib.fileIO import FileOperations
from siglab_lib.mainWinPlot import MainWindowPlotter
from siglab_lib.calcStats import calculate_segment_stats
from siglab_lib.externalPlot import create_stats_plot, create_higuchi_plot

# Add library path
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(current_dir, 'siglab_lib')
sys.path.insert(0, lib_path)

class SignalLab:
    def __init__(self, root):
        # Window setup
        self.root = root
        self.root.title("SignalLab")
        self.root.geometry('1400x900')
        self.root.configure(bg='#B0C4DE')

        # Data storage
        self.filepath = None
        self.magR = None
        self.time_S = None
        self.tag_state = None
        self.stats = None
        self.higuchi_stats = None
        self.sinReg = None  # NEW: Sinusoidal regression results

        # State colors
        self.state_colors = {
            0: {'name': 'Unknown', 'color': 'gray', 'label_color': 'white'},
            1: {'name': 'Blood1', 'color': 'green', 'label_color': 'white'},
            2: {'name': 'Blood2', 'color': 'cyan', 'label_color': 'black'},
            3: {'name': 'Wall', 'color': 'blue', 'label_color': 'white'},
            4: {'name': 'Clot', 'color': 'orange', 'label_color': 'black'},
            5: {'name': 'Step', 'color': 'black', 'label_color': 'white'}
        }

        # Create toolbar/plot_utils/canvas
        self.file_ops = FileOperations(self)
        self._create_menu_bar()
        self.toolbar_frame = tk.Frame(self.root, bg='#B0C4DE', height=50)
        self.toolbar_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        self.plot_utils = MainWindowPlotter(self)
        self.plot_utils.create_plot_area()
        self.interaction_modes = InteractionModes(self)
        self.toolbar_utils = ToolbarUtils(self)
        self.toolbar_utils.create_toolbar_buttons(self.toolbar_frame)
        self.canvas.mpl_connect('button_press_event', self.interaction_modes.on_mouse_press)
        

    def _create_menu_bar(self):
        menubar = tk.Menu(self.root, background='#D0D8E0')
        self.root.config(menu=menubar)

        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open", command=self.file_ops.open_file)
        file_menu.add_command(label="Save", command=self.file_ops.save_file)
        file_menu.add_command(label="Save As", command=self.file_ops.save_as_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # Calculate Menu
        calc_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Calc", menu=calc_menu)
        calc_menu.add_command(label="Stats", command=self._calculate_stats)
        calc_menu.add_command(label="Higuchi", command=self._calculate_higuchi)
        calc_menu.add_command(label="Sin Regression", command=self._calculate_sin_regression)  # NEW
        calc_menu.add_separator()
        calc_menu.add_command(label="All", command=self._calculate_all)

        # Time-Plot Menu
        time_plot_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Time-Plot", menu=time_plot_menu)
        time_plot_menu.add_command(label="Stats", command=self._plot_stats)
        time_plot_menu.add_command(label="Higuchi", command=self._plot_higuchi)
        time_plot_menu.add_separator()
        time_plot_menu.add_command(label="SinReg: All", command=self._plot_sin_regression)
        time_plot_menu.add_command(label="SinReg: Frequency", command=self._plot_sinreg_freq)
        time_plot_menu.add_command(label="SinReg: Amplitude", command=self._plot_sinreg_amp)
        time_plot_menu.add_command(label="SinReg: Phase", command=self._plot_sinreg_phase)
        time_plot_menu.add_command(label="SinReg: Mean Error", command=self._plot_sinreg_err)
        time_plot_menu.add_command(label="SinReg: Slope", command=self._plot_sinreg_slope)
        time_plot_menu.add_command(label="SinReg: DC Offset", command=self._plot_sinreg_dc)
        time_plot_menu.add_command(label="SinReg: MeanErr Norm", command=self._plot_sinreg_err_norm)

        # Scatter-Plot Menu
        scatter_plot_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Scatter-Plot", menu=scatter_plot_menu)
        scatter_plot_menu.add_command(label="Higuchi", command=self._scatter_plot_higuchi)
        scatter_plot_menu.add_command(label="Range Vs BloodRefDiff", command=self._scatter_plot_range_bloodref)
        scatter_plot_menu.add_separator()  # NEW: Separator before sinReg scatter plots
        scatter_plot_menu.add_command(label="SinReg: Freq Vs MeanErr", command=self._scatter_plot_sinreg_freq_err)  # NEW
        scatter_plot_menu.add_command(label="SinReg: Amp Vs MeanErr", command=self._scatter_plot_sinreg_amp_err)  # NEW
        scatter_plot_menu.add_command(label="SinReg: Phase Vs MeanErr", command=self._scatter_plot_sinreg_phs_err)  # NEW


    def create_toolbar_buttons(self, toolbar):
        unknown_button_width = 10

        # Escape button
        escape_btn = tk.Button(
            toolbar, 
            text='Escape', 
            width=unknown_button_width,
            command=self.app.interaction_modes.escape_interactive_mode,
            anchor='center'
        )
        escape_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # State selection buttons
        for state_val, state_info in self.app.state_colors.items():
            btn = tk.Button(
                toolbar, 
                text=state_info['name'], 
                bg=state_info['color'],
                fg=state_info['label_color'],
                width=unknown_button_width,
                command=lambda s=state_val: self.app.interaction_modes.set_state_mode(s),
                anchor='center'
            )
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            
    def _calculate_stats(self):
        """Calculate and store signal statistics"""
        if self.magR is None:
            tk.messagebox.showinfo("Stats", "Please open a file first")
            return
            
        from siglab_lib.calcStats import calculate_segment_stats       
        self.stats = calculate_segment_stats(self)      
        print("Statistics calculated")
        
    def _plot_stats(self):
        """Launch external stats plot"""
        if self.stats is None:
            tk.messagebox.showinfo("Stats Plot", "Please calculate stats first using Calc > Stats")
            return
        
        from siglab_lib.externalPlot import create_stats_plot
        create_stats_plot(self)

    def _calculate_higuchi(self):
        """Calculate and store Higuchi Fractal Dimension statistics"""
        if self.magR is None:
            tk.messagebox.showinfo("Higuchi", "Please open a file first")
            return
            
        from siglab_lib.calcHiguchi import calculate_higuchi_stats
        self.higuchi_stats = calculate_higuchi_stats(self.magR, self.time_S)
        print("Higuchi Fractal Dimension statistics calculated")

    def _plot_higuchi(self):
        """Launch external Higuchi plot"""
        if not hasattr(self, 'higuchi_stats') or self.higuchi_stats is None:
            tk.messagebox.showinfo("Higuchi Plot", "Please calculate Higuchi stats first using Calc > Higuchi")
            return
        
        from siglab_lib.externalPlot import create_higuchi_plot
        create_higuchi_plot(self)

    # NEW: Sinusoidal Regression Methods
    def _calculate_sin_regression(self):
        """Calculate and store sinusoidal regression parameters"""
        if self.magR is None:
            tk.messagebox.showinfo("Sin Regression", "Please open a file first")
            return
            
        from siglab_lib.calcSinReg import calculate_sin_regression
        self.sinReg = calculate_sin_regression(self.magR, self.time_S)
        print("Sinusoidal regression parameters calculated")
        print(f"  - Segments: {len(self.sinReg['sinFrq'])}")
        print(f"  - Freq range: {self.sinReg['sinFrq'].min():.2f} - {self.sinReg['sinFrq'].max():.2f} Hz")
        print(f"  - Mean error range: {self.sinReg['meanErr'].min():.2f} - {self.sinReg['meanErr'].max():.2f}")

    def _plot_sin_regression(self):
        """Launch external sin regression time plot (all parameters)"""
        if self.sinReg is None:
            tk.messagebox.showinfo("Sin Regression Plot", "Please calculate sin regression first using Calc > Sin Regression")
            return
        
        from siglab_lib.externalPlot import create_sin_regression_plot
        create_sin_regression_plot(self)

    def _plot_sinreg_freq(self):
        """Launch sin regression frequency time plot"""
        if self.sinReg is None:
            tk.messagebox.showinfo("Sin Regression Plot", "Please calculate sin regression first using Calc > Sin Regression")
            return
        from siglab_lib.externalPlot import create_sinreg_single_plot
        create_sinreg_single_plot(self, 'sinFrq', 'Frequency (Hz)', 'blue')

    def _plot_sinreg_amp(self):
        """Launch sin regression amplitude time plot"""
        if self.sinReg is None:
            tk.messagebox.showinfo("Sin Regression Plot", "Please calculate sin regression first using Calc > Sin Regression")
            return
        from siglab_lib.externalPlot import create_sinreg_single_plot
        create_sinreg_single_plot(self, 'sinAmp', 'Amplitude', 'green')

    def _plot_sinreg_phase(self):
        """Launch sin regression phase time plot"""
        if self.sinReg is None:
            tk.messagebox.showinfo("Sin Regression Plot", "Please calculate sin regression first using Calc > Sin Regression")
            return
        from siglab_lib.externalPlot import create_sinreg_single_plot
        create_sinreg_single_plot(self, 'sinPhs', 'Phase (radians)', 'orange')

    def _plot_sinreg_err(self):
        """Launch sin regression mean error time plot"""
        if self.sinReg is None:
            tk.messagebox.showinfo("Sin Regression Plot", "Please calculate sin regression first using Calc > Sin Regression")
            return
        from siglab_lib.externalPlot import create_sinreg_single_plot
        create_sinreg_single_plot(self, 'meanErr', 'Mean Error', 'red')

    def _plot_sinreg_slope(self):
        """Launch sin regression slope time plot"""
        if self.sinReg is None:
            tk.messagebox.showinfo("Sin Regression Plot", "Please calculate sin regression first using Calc > Sin Regression")
            return
        from siglab_lib.externalPlot import create_sinreg_single_plot
        create_sinreg_single_plot(self, 'slope', 'Slope', 'purple')

    def _plot_sinreg_dc(self):
        """Launch sin regression DC offset time plot"""
        if self.sinReg is None:
            tk.messagebox.showinfo("Sin Regression Plot", "Please calculate sin regression first using Calc > Sin Regression")
            return
        from siglab_lib.externalPlot import create_sinreg_single_plot
        create_sinreg_single_plot(self, 'dcOffset', 'DC Offset', 'brown')

    def _plot_sinreg_err_norm(self):
        """Launch sin regression normalized mean error time plot (Amplitude / MeanErr)"""
        if self.sinReg is None:
            tk.messagebox.showinfo("Sin Regression Plot", "Please calculate sin regression first using Calc > Sin Regression")
            return
        from siglab_lib.externalPlot import create_sinreg_meanerr_norm_plot
        create_sinreg_meanerr_norm_plot(self)

    def _scatter_plot_sinreg_freq_err(self):
        """Launch Frequency vs Mean Error scatter plot"""
        if self.sinReg is None:
            tk.messagebox.showinfo("Sin Regression Scatter", "Please calculate sin regression first using Calc > Sin Regression")
            return
            
        from siglab_lib.scatterPlot import create_sinreg_freq_err_scatter
        create_sinreg_freq_err_scatter(self)

    def _scatter_plot_sinreg_amp_err(self):
        """Launch Amplitude vs Mean Error scatter plot"""
        if self.sinReg is None:
            tk.messagebox.showinfo("Sin Regression Scatter", "Please calculate sin regression first using Calc > Sin Regression")
            return
            
        from siglab_lib.scatterPlot import create_sinreg_amp_err_scatter
        create_sinreg_amp_err_scatter(self)

    def _scatter_plot_sinreg_phs_err(self):
        """Launch Phase vs Mean Error scatter plot"""
        if self.sinReg is None:
            tk.messagebox.showinfo("Sin Regression Scatter", "Please calculate sin regression first using Calc > Sin Regression")
            return
            
        from siglab_lib.scatterPlot import create_sinreg_phs_err_scatter
        create_sinreg_phs_err_scatter(self)
        
    def _scatter_plot_higuchi(self):
        """Launch Higuchi scatter plot"""
        from siglab_lib.scatterPlot import create_higuchi_scatter
        create_higuchi_scatter(self)

    def _scatter_plot_range_bloodref(self):
        """Launch Range vs Blood Reference Difference scatter plot"""
        from siglab_lib.scatterPlot import create_range_bloodref_scatter
        create_range_bloodref_scatter(self)

    def _set_state_mode(self, state_val):
        # State selection mode
        pass

    def _on_mouse_press(self, event):
        # Handle mouse press for state selection
        pass

    def _on_mouse_move(self, event):
        # Handle mouse move
        pass

    def _on_mouse_release(self, event):
        # Handle mouse release
        pass

    def _save_file(self):
        # Save current state to file
        pass

    def _save_as_file(self):
        # Save to a new file
        pass

    def _calculate_all(self):
        """Calculate all available metrics"""
        if self.magR is None:
            tk.messagebox.showinfo("Calculate All", "Please open a file first")
            return
            
        self._calculate_stats()
        self._calculate_higuchi()
        self._calculate_sin_regression()
        print("All calculations complete")

def main():
    root = tk.Tk()
    app = SignalLab(root)
    root.mainloop()

if __name__ == "__main__":
    main()
