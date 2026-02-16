# siglab_lib/externalPlot.py
import os
import tkinter as tk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

def create_stats_plot(app):
    """
    Create a plot of segment statistics in a new window
    
    Parameters:
    - app: Main application instance
    """
    # Use the pre-calculated stats from the app instance
    if not hasattr(app, 'stats') or app.stats is None:
        tk.messagebox.showinfo("Stats Plot", "No stats available. Calculate stats first.")
        return
    
    stats_data = app.stats
    
    # Create new top-level window
    plot_window = tk.Toplevel()
    plot_window.title(f"MinMaxRng plot: {os.path.basename(app.filepath)}")
    plot_window.geometry('1000x600')
    
    # Create matplotlib figure
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Create canvas WITH explicit interactive mode
    canvas = FigureCanvasTkAgg(fig, master=plot_window)
    canvas.draw()  # Important: call draw before creating toolbar
    
    # Create toolbar
    toolbar = NavigationToolbar2Tk(canvas, plot_window)
    toolbar.update()
    
    # Pack widgets in specific order
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
    toolbar.pack(side=tk.TOP, fill=tk.X)
    
    # Extract segment stats data
    segment_stats = stats_data['segmentStats']['each']
    tag_time_S = stats_data['segmentStats']['time']
    
    # Extract blood estimate values
    blood_est_val = stats_data['bloodEstVal']
    
    # Plot data
    ax.scatter(tag_time_S, segment_stats[:, 2], color='black', label='Mean', s=30)
    
    # Plot min-max range lines
    for i in range(len(tag_time_S)):
        ax.vlines(tag_time_S[i], segment_stats[i, 1], segment_stats[i, 0], 
                  color='blue', alpha=0.5, linewidth=2)
    
    # Plot blood estimate value as a horizontal red line
    ax.plot(tag_time_S, blood_est_val, color='darkred', linestyle='-', label='Blood Est Value')
    
    ax.set_title(f"MinMaxRng plot: {os.path.basename(app.filepath)}")
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Magnitude')
    ax.legend()
    ax.grid(True)
    
    # Show the plot
    canvas.draw()


#-------------------------------------------------------------
#                    create_higuchi_plot
#-------------------------------------------------------------
def create_higuchi_plot(app):
    """
    Create plots of Higuchi Fractal Dimension statistics
    
    Parameters:
    - app: Main application instance
    """
    from siglab_lib.calcHiguchi import calculate_higuchi_stats
    
    # Calculate Higuchi statistics
    higuchi_stats = calculate_higuchi_stats(app.magR, app.time_S)
    
    # Create new top-level window 
    plot_window = tk.Toplevel()
    plot_window.title(f"Higuchi Fractal Dimension: {os.path.basename(app.filepath)}")
    plot_window.geometry('1000x600')
    plot_window.configure(bg='#B0C4DE')  # Match main window background
    
    # Create matplotlib figure with two subplots
    fig, (mean_ax, slope_ax) = plt.subplots(2, 1, figsize=(10, 6), height_ratios=[1, 1], sharex=True)
    
    # Set figure background to match main window
    fig.patch.set_facecolor('#B0C4DE')
    
    # Set axes background to match plot area in main window
    mean_ax.set_facecolor('#E6EDF3')
    slope_ax.set_facecolor('#E6EDF3')
    
    # Create canvas WITH explicit interactive mode
    canvas = FigureCanvasTkAgg(fig, master=plot_window)
    canvas.draw()  # Important: call draw before creating toolbar
    
    # Create toolbar
    toolbar = NavigationToolbar2Tk(canvas, plot_window)
    toolbar.update()
    
    # Pack widgets in specific order
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
    toolbar.pack(side=tk.TOP, fill=tk.X)
    
    # Extract time points
    tag_time_S = app.time_S[::30]  # Time points for each segment
    
    # Calculate 1-second mean of Higuchi values
    higuchi_mean = np.mean(higuchi_stats[:, :5], axis=1)
    
    # Plot Higuchi Mean with 1 pt width line and 10pt dots
    mean_ax.plot(tag_time_S, higuchi_mean, color='black', linewidth=1.0)
    mean_ax.scatter(tag_time_S, higuchi_mean, color='black', s=10)
    mean_ax.set_title(f"Higuchi Mean: {os.path.basename(app.filepath)}")
    mean_ax.set_ylabel('Higuchi Mean')
    mean_ax.grid(True)
    
    # Plot Higuchi Slope with dots only
    slope_ax.scatter(tag_time_S, higuchi_stats[:, 5], color='black', s=10)
    slope_ax.set_title(f"Higuchi Slope: {os.path.basename(app.filepath)}")
    slope_ax.set_xlabel('Time (s)')
    slope_ax.set_ylabel('Higuchi Slope')
    slope_ax.grid(True)
    
    # Adjust layout to prevent overlap
    plt.tight_layout()
    
    # Show the plot
    canvas.draw()


#-------------------------------------------------------------
#                create_sin_regression_plot
#-------------------------------------------------------------
def create_sin_regression_plot(app):
    """
    Create plots of Sinusoidal Regression parameters over time
    
    Parameters:
    - app: Main application instance with sinReg data
    """
    if app.sinReg is None:
        tk.messagebox.showinfo("Sin Regression Plot", "No sin regression data available. Calculate first.")
        return
    
    # Create new top-level window 
    plot_window = tk.Toplevel()
    plot_window.title(f"Sinusoidal Regression: {os.path.basename(app.filepath)}")
    plot_window.geometry('1000x800')
    plot_window.configure(bg='#B0C4DE')
    
    # Create matplotlib figure with 4 subplots
    fig, axes = plt.subplots(4, 1, figsize=(10, 8), sharex=True)
    freq_ax, amp_ax, err_ax, slope_ax = axes
    
    # Set figure background
    fig.patch.set_facecolor('#B0C4DE')
    
    # Set axes backgrounds
    for ax in axes:
        ax.set_facecolor('#E6EDF3')
    
    # Create canvas
    canvas = FigureCanvasTkAgg(fig, master=plot_window)
    canvas.draw()
    
    # Create toolbar
    toolbar = NavigationToolbar2Tk(canvas, plot_window)
    toolbar.update()
    
    # Pack widgets
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
    toolbar.pack(side=tk.TOP, fill=tk.X)
    
    # Extract time points from sinReg
    time_S = app.sinReg['time']
    
    # Plot Frequency
    freq_ax.plot(time_S, app.sinReg['sinFrq'], color='blue', linewidth=1.0)
    freq_ax.scatter(time_S, app.sinReg['sinFrq'], color='blue', s=5)
    freq_ax.set_ylabel('Frequency (Hz)')
    freq_ax.set_title(f"Sinusoidal Regression: {os.path.basename(app.filepath)}")
    freq_ax.grid(True)
    
    # Plot Amplitude
    amp_ax.plot(time_S, app.sinReg['sinAmp'], color='green', linewidth=1.0)
    amp_ax.scatter(time_S, app.sinReg['sinAmp'], color='green', s=5)
    amp_ax.set_ylabel('Amplitude')
    amp_ax.grid(True)
    
    # Plot Mean Error
    err_ax.plot(time_S, app.sinReg['meanErr'], color='red', linewidth=1.0)
    err_ax.scatter(time_S, app.sinReg['meanErr'], color='red', s=5)
    err_ax.set_ylabel('Mean Error')
    err_ax.grid(True)
    
    # Plot Slope
    slope_ax.plot(time_S, app.sinReg['slope'], color='purple', linewidth=1.0)
    slope_ax.scatter(time_S, app.sinReg['slope'], color='purple', s=5)
    slope_ax.set_ylabel('Slope')
    slope_ax.set_xlabel('Time (s)')
    slope_ax.grid(True)
    
    # Adjust layout
    plt.tight_layout()
    
    # Show the plot
    canvas.draw()


#-------------------------------------------------------------
#              create_sinreg_single_plot
#-------------------------------------------------------------
def create_sinreg_single_plot(app, param_key, y_label, color):
    """
    Create a single parameter time plot for sinusoidal regression
    
    Parameters:
    - app: Main application instance with sinReg data
    - param_key: Key in sinReg dictionary ('sinFrq', 'sinAmp', 'sinPhs', 'meanErr', 'slope', 'dcOffset')
    - y_label: Label for y-axis
    - color: Color for the plot line and markers
    """
    if app.sinReg is None:
        tk.messagebox.showinfo("Sin Regression Plot", "No sin regression data available. Calculate first.")
        return
    
    # Create new top-level window 
    plot_window = tk.Toplevel()
    plot_window.title(f"SinReg {y_label}: {os.path.basename(app.filepath)}")
    plot_window.geometry('1000x500')
    plot_window.configure(bg='#B0C4DE')
    
    # Create matplotlib figure
    fig, ax = plt.subplots(figsize=(10, 5))
    
    # Set figure background
    fig.patch.set_facecolor('#B0C4DE')
    ax.set_facecolor('#E6EDF3')
    
    # Create canvas
    canvas = FigureCanvasTkAgg(fig, master=plot_window)
    canvas.draw()
    
    # Create toolbar
    toolbar = NavigationToolbar2Tk(canvas, plot_window)
    toolbar.update()
    
    # Pack widgets
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
    toolbar.pack(side=tk.TOP, fill=tk.X)
    
    # Extract time points and data
    time_S = app.sinReg['time']
    data = app.sinReg[param_key]
    
    # Plot data
    ax.plot(time_S, data, color=color, linewidth=1.0)
    ax.scatter(time_S, data, color=color, s=10)
    ax.set_title(f"SinReg {y_label}: {os.path.basename(app.filepath)}")
    ax.set_xlabel('Time (s)')
    ax.set_ylabel(y_label)
    ax.grid(True)
    
    # Adjust layout
    plt.tight_layout()
    
    # Show the plot
    canvas.draw()


#-------------------------------------------------------------
#              create_sinreg_meanerr_norm_plot
#-------------------------------------------------------------
def create_sinreg_meanerr_norm_plot(app):
    """
    Create a time plot of normalized mean error (Amplitude / MeanErr)
    
    Parameters:
    - app: Main application instance with sinReg data
    """
    if app.sinReg is None:
        tk.messagebox.showinfo("Sin Regression Plot", "No sin regression data available. Calculate first.")
        return
    
    # Create new top-level window 
    plot_window = tk.Toplevel()
    plot_window.title(f"SinReg MeanErr Norm (Amp/Err): {os.path.basename(app.filepath)}")
    plot_window.geometry('1000x500')
    plot_window.configure(bg='#B0C4DE')
    
    # Create matplotlib figure
    fig, ax = plt.subplots(figsize=(10, 5))
    
    # Set figure background
    fig.patch.set_facecolor('#B0C4DE')
    ax.set_facecolor('#E6EDF3')
    
    # Create canvas
    canvas = FigureCanvasTkAgg(fig, master=plot_window)
    canvas.draw()
    
    # Create toolbar
    toolbar = NavigationToolbar2Tk(canvas, plot_window)
    toolbar.update()
    
    # Pack widgets
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
    toolbar.pack(side=tk.TOP, fill=tk.X)
    
    # Extract time points and calculate normalized error
    time_S = app.sinReg['time']
    amplitude = app.sinReg['sinAmp']
    mean_err = app.sinReg['meanErr']
    
    # Calculate normalized mean error (Amplitude / MeanErr)
    # Avoid division by zero
    with np.errstate(divide='ignore', invalid='ignore'):
        meanerr_norm = np.where(mean_err > 0, amplitude / mean_err, 0)
    
    # Plot data
    ax.plot(time_S, meanerr_norm, color='darkgreen', linewidth=1.0)
    ax.scatter(time_S, meanerr_norm, color='darkgreen', s=10)
    ax.set_title(f"SinReg MeanErr Norm (Amp/Err): {os.path.basename(app.filepath)}")
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Amplitude / Mean Error')
    ax.grid(True)
    
    # Adjust layout
    plt.tight_layout()
    
    # Show the plot
    canvas.draw()
