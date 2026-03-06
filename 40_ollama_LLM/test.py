
import tkinter as tk

def close_program():
    root.quit()

# Create the main application window
root = tk.Tk()
root.title("Blue Square Window")

# Set the size of the window
window_width = 400
window_height = 400
root.geometry(f"{window_width}x{window_height}")

# Create a canvas for drawing
canvas = tk.Canvas(root, width=window_width, height=window_height)
canvas.pack()

# Draw a blue square in the center
square_size = 100
start_x = (window_width - square_size) // 2
start_y = (window_height - square_size) // 2
blue_color = "blue"
canvas.create_rectangle(start_x, start_y, start_x + square_size, start_y + square_size, fill=blue_color)

# Create a menu bar
menu_bar = tk.Menu(root)
root.config(menu=menu_bar)

# Add an exit option to the menu
file_menu = tk.Menu(menu_bar, tearoff=0)
file_menu.add_command(label="Exit", command=close_program)
menu_bar.add_cascade(label="File", menu=file_menu)

# Start the main event loop
root.mainloop()
