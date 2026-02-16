# siglab_lib/scatterPlot.py
import os
import tkinter as tk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

def create_higuchi_scatter(app):
    """
    Create a scatter plot of Higuchi Mean vs Slope, colored by state
    
    Parameters:
    - app: Main application instance
    """
    from siglab_lib.calcHiguchi import calculate_higuchi_stats
    from siglab_lib.calcStats import calculate_segment_stats
    
    # Calculate Higuchi and segment statistics
    higuchi_stats = calculate_higuchi_stats(app.magR, app.time_S)
    segment_stats = calculate_segment_stats(app)
    
    # Create scatter plot window
    plot_window = tk.Toplevel()
    plot_window.title(f"Higuchi Mean vs Slope: {os.path.basename(app.filepath)}")
    plot_window.geometry('800x600')
    plot_window.configure(bg='#B0C4DE')  # Match main window background
    
    # Create matplotlib figure
    fig, ax = plt.subplots(figsize=(8, 6))
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
    
    # Calculate Higuchi Mean and Slope
    higuchi_mean = np.mean(higuchi_stats[:, :5], axis=1)
    higuchi_slope = higuchi_stats[:, 5]
    
    # Plot scatter for each state
    for state_val, state_info in app.state_colors.items():
        # Find indices for this state
        state_mask = app.tag_state == state_val
        
        # Plot scatter for this state
        if state_val == 0:
            ax.scatter(
                higuchi_mean[state_mask], 
                higuchi_slope[state_mask], 
                color=state_info['color'], 
                label=state_info['name'],
                s=1
            )
        else:
            ax.scatter(
                higuchi_mean[state_mask], 
                higuchi_slope[state_mask], 
                color=state_info['color'], 
                label=state_info['name'],
                s=10
            )
    
    ax.set_title(f"Higuchi Mean vs Slope: {os.path.basename(app.filepath)}")
    ax.set_xlabel('Higuchi Mean')
    ax.set_ylabel('Higuchi Slope')
    ax.grid(True)
    ax.legend()
    
    # Adjust layout
    plt.tight_layout()
    
    # Show the plot
    canvas.draw()

def create_range_bloodref_scatter(app):
    """
    Create a scatter plot of Range vs Blood Reference Difference, colored by state
    
    Parameters:
    - app: Main application instance
    """
    from siglab_lib.calcStats import calculate_segment_stats
    
    # Calculate segment statistics
    segment_stats = calculate_segment_stats(app)
    
    # Create scatter plot window
    plot_window = tk.Toplevel()
    plot_window.title(f"Range vs Blood Reference Diff: {os.path.basename(app.filepath)}")
    plot_window.geometry('800x600')
    plot_window.configure(bg='#B0C4DE')  # Match main window background
    
    # Create matplotlib figure
    fig, ax = plt.subplots(figsize=(8, 6))
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
    
    # Extract segment statistics
    segment_rng = segment_stats['segmentStats']['each'][:, 3]  # Range column
    
    # Calculate blood reference difference
    blood_est_val = segment_stats['bloodEstVal']
    segment_mean = segment_stats['segmentStats']['each'][:, 2]  # Mean column
    blood_ref_diff = np.abs(segment_mean - blood_est_val)
    
    # Plot scatter for each state
    for state_val, state_info in app.state_colors.items():
        # Find indices for this state
        state_mask = app.tag_state == state_val
        
        # Plot scatter for this state
        if state_val == 0:
            ax.scatter(
                segment_rng[state_mask], 
                blood_ref_diff[state_mask], 
                color=state_info['color'], 
                label=state_info['name'],
                s=1
            )
        else:
            ax.scatter(
                segment_rng[state_mask], 
                blood_ref_diff[state_mask], 
                color=state_info['color'], 
                label=state_info['name'],
                s=10
            )
    
    ax.set_title(f"Range vs Blood Reference Diff: {os.path.basename(app.filepath)}")
    ax.set_xlabel('Range')
    ax.set_ylabel('Blood Reference Difference')
    ax.grid(True)
    ax.legend()
    
    # Adjust layout
    plt.tight_layout()
    
    # Show the plot
    canvas.draw()


#-------------------------------------------------------------
#          Sinusoidal Regression Scatter Plots
#-------------------------------------------------------------

def _create_sinreg_scatter_base(app, x_data, y_data, x_label, y_label, title_suffix):
    """
    Base function to create sinusoidal regression scatter plots
    
    Parameters:
    - app: Main application instance
    - x_data: X-axis data array
    - y_data: Y-axis data array  
    - x_label: Label for X-axis
    - y_label: Label for Y-axis
    - title_suffix: Suffix for the window title
    """
    # Create scatter plot window
    plot_window = tk.Toplevel()
    plot_window.title(f"SinReg {title_suffix}: {os.path.basename(app.filepath)}")
    plot_window.geometry('800x600')
    plot_window.configure(bg='#B0C4DE')
    
    # Create matplotlib figure
    fig, ax = plt.subplots(figsize=(8, 6))
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
    
    # Handle length mismatch between sinReg (may have different length) and tag_state
    # sinReg is 1 Hz output, tag_state is also 1 Hz (decimated from 30 Hz)
    num_sinreg_points = len(x_data)
    num_tag_points = len(app.tag_state)
    
    # Use the minimum length
    num_points = min(num_sinreg_points, num_tag_points)
    
    # Truncate data to match
    x_data_plot = x_data[:num_points]
    y_data_plot = y_data[:num_points]
    tag_state_plot = app.tag_state[:num_points]
    
    # Plot scatter for each state
    for state_val, state_info in app.state_colors.items():
        # Find indices for this state
        state_mask = tag_state_plot == state_val
        
        # Plot scatter for this state
        if state_val == 0:
            ax.scatter(
                x_data_plot[state_mask], 
                y_data_plot[state_mask], 
                color=state_info['color'], 
                label=state_info['name'],
                s=1,
                alpha=0.5
            )
        else:
            ax.scatter(
                x_data_plot[state_mask], 
                y_data_plot[state_mask], 
                color=state_info['color'], 
                label=state_info['name'],
                s=10
            )
    
    ax.set_title(f"SinReg {title_suffix}: {os.path.basename(app.filepath)}")
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.grid(True)
    ax.legend()
    
    # Adjust layout
    plt.tight_layout()
    
    # Show the plot
    canvas.draw()


def create_sinreg_freq_err_scatter(app):
    """
    Create a scatter plot of Frequency vs Mean Error, colored by state
    
    Parameters:
    - app: Main application instance with sinReg data
    """
    if app.sinReg is None:
        tk.messagebox.showinfo("Sin Regression Scatter", "Please calculate sin regression first")
        return
    
    _create_sinreg_scatter_base(
        app,
        x_data=app.sinReg['sinFrq'],
        y_data=app.sinReg['meanErr'],
        x_label='Frequency (Hz)',
        y_label='Mean Error',
        title_suffix='Freq vs MeanErr'
    )


def create_sinreg_amp_err_scatter(app):
    """
    Create a scatter plot of Amplitude vs Mean Error, colored by state
    
    Parameters:
    - app: Main application instance with sinReg data
    """
    if app.sinReg is None:
        tk.messagebox.showinfo("Sin Regression Scatter", "Please calculate sin regression first")
        return
    
    _create_sinreg_scatter_base(
        app,
        x_data=app.sinReg['sinAmp'],
        y_data=app.sinReg['meanErr'],
        x_label='Amplitude',
        y_label='Mean Error',
        title_suffix='Amp vs MeanErr'
    )


def create_sinreg_phs_err_scatter(app):
    """
    Create a scatter plot of Phase vs Mean Error, colored by state
    
    Parameters:
    - app: Main application instance with sinReg data
    """
    if app.sinReg is None:
        tk.messagebox.showinfo("Sin Regression Scatter", "Please calculate sin regression first")
        return
    
    _create_sinreg_scatter_base(
        app,
        x_data=app.sinReg['sinPhs'],
        y_data=app.sinReg['meanErr'],
        x_label='Phase (radians)',
        y_label='Mean Error',
        title_suffix='Phase vs MeanErr'
    )
