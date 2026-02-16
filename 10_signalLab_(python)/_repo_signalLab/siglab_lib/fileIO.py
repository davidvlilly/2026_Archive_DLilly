# siglab_lib/fileIO.py
import os
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import h5py
from siglab_lib.mainWinPlot import MainWindowPlotter

class FileOperations:
    def __init__(self, app):
        """
        Initialize file operations for the SignalLab application
        
        Parameters:
        - app: Main application instance
        """
        self.app = app

    def open_file(self):
        """
        Open HDF5 file and load signal data
        """
        filepath = filedialog.askopenfilename(
            title="Open F5B File",
            filetypes=[("F5B files", "*.f5b")]
        )
        
        if filepath:
            try:
                with h5py.File(filepath, 'r') as f:
                    self.app.magR = f['signal/magR'][:]
                    self.app.time_S = f['signal/time_S'][:]
                    self.app.tag_state = f['tag/state'][:]
                    self.app.filepath = filepath

                # Plot the data
                self.app.plot_utils.plot_data()

            except Exception as e:
                messagebox.showerror("File Open Error", str(e))

    def save_file(self):
        """
        Save current state to the original file
        """
        if self.app.filepath is None:
            self.save_as_file()
            return

        try:
            with h5py.File(self.app.filepath, 'r+') as f:
                # Delete existing state dataset if it exists
                if 'tag/state' in f:
                    del f['tag/state']
                
                # Create new dataset with current states
                f.create_dataset('tag/state', data=self.app.tag_state)
            
            messagebox.showinfo("Save", f"Updated states saved to {self.app.filepath}")
        
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def save_as_file(self):
        """
        Save current state to a new file
        """
        if self.app.filepath is None:
            messagebox.showinfo("Save As", "No data to save")
            return

        try:
            # Open file dialog to choose save location
            save_path = filedialog.asksaveasfilename(
                defaultextension=".f5b",
                filetypes=[("F5B files", "*.f5b")]
            )

            if save_path:
                # Open original file
                with h5py.File(self.app.filepath, 'r') as src:
                    # Create new file
                    with h5py.File(save_path, 'w') as dst:
                        # Manually copy groups and datasets
                        def copy_group(src_group, dst_group):
                            for key, item in src_group.items():
                                if isinstance(item, h5py.Group):
                                    # Create new group
                                    new_group = dst_group.create_group(key)
                                    copy_group(item, new_group)
                                else:
                                    # Carefully copy dataset
                                    try:
                                        # Try to get data
                                        if item.shape == ():
                                            # Scalar dataset
                                            dst_group.create_dataset(key, data=item[()])
                                        else:
                                            # Multidimensional dataset
                                            dst_group.create_dataset(key, data=item[:])
                                    except Exception as e:
                                        print(f"Could not copy dataset {key}: {e}")
                        
                        # Copy all groups and datasets
                        copy_group(src, dst)
                
                # Open the new file to ensure tag/state is updated
                with h5py.File(save_path, 'r+') as f:
                    # Update or create tag/state dataset
                    if 'tag/state' in f:
                        del f['tag/state']
                    f.create_dataset('tag/state', data=self.app.tag_state)
                
                #messagebox.showinfo("Save As", f"File saved to {save_path}")
        
        except Exception as e:
            messagebox.showerror("Save As Error", str(e))