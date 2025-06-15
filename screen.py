#sudo apt install gnome-screenshot

import sys
import subprocess
import os
import random

# --- User-configurable variables ---
INITIAL_DELAY = 10           # seconds before starting screenshots
KEY_PRESS_MIN = 10           # minimum seconds between down arrow key presses
KEY_PRESS_MAX = 15          # maximum seconds between down arrow key presses
POST_KEY_WAIT = 3            # seconds to wait after key press before screenshot
PAUSE_AFTER_CLICKS = 20      # pause after every N down arrow clicks
PAUSE_DURATION = 12         # pause duration in seconds (10 minutes)
MAX_CLICKS = 120             # exit after this many down arrow clicks
# -----------------------------------

# Force pyautogui to use Pillow backend for screenshots
os.environ["PYAUTOGUI_SCREENSHOT"] = "pillow"

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

for pkg in ["pyautogui", "numpy", "Pillow"]:
    try:
        __import__(pkg if pkg != "Pillow" else "PIL")
    except ImportError:
        install(pkg)

import time
import shutil
import pyautogui
import numpy as np
from PIL import Image, ImageChops, UnidentifiedImageError
import tkinter as tk
from PIL import ImageTk

def get_capture_region():
    print("Please select the region to capture for screenshots by dragging the mouse on the screen.")
    region = None
    rect = None

    # Take a fullscreen screenshot to use as the background
    screen_img = pyautogui.screenshot()
    screen_width, screen_height = screen_img.size

    def on_mouse_down(event):
        nonlocal start_x, start_y, rect
        start_x, start_y = event.x, event.y
        if rect:
            canvas.delete(rect)
        rect = canvas.create_rectangle(start_x, start_y, start_x, start_y, outline='red', width=2)

    def on_mouse_move(event):
        nonlocal rect
        if rect:
            canvas.coords(rect, start_x, start_y, event.x, event.y)

    def on_mouse_up(event):
        nonlocal region
        end_x, end_y = event.x, event.y
        left = min(start_x, end_x)
        top = min(start_y, end_y)
        width = abs(end_x - start_x)
        height = abs(end_y - start_y)
        region = (left, top, width, height)
        root.quit()

    # Create a fullscreen window with the screenshot as background
    root = tk.Tk()
    root.attributes('-fullscreen', True)
    root.title("Drag to select region")
    root.attributes('-topmost', True)
    root.overrideredirect(True)  # Remove window decorations

    canvas = tk.Canvas(root, cursor="cross", width=screen_width, height=screen_height)
    canvas.pack(fill=tk.BOTH, expand=True)

    # Convert PIL image to Tkinter PhotoImage and display
    tk_img = ImageTk.PhotoImage(screen_img)
    canvas.create_image(0, 0, anchor="nw", image=tk_img)

    start_x = start_y = 0
    rect = None
    canvas.bind("<ButtonPress-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_move)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)

    print("Drag mouse to select region, then release.")
    root.mainloop()
    root.destroy()

    if region and region[2] > 0 and region[3] > 0:
        print(f"Selected region: {region}")
        return region
    else:
        print("No region selected or invalid region. Exiting.")
        exit(1)

def capture_screen(region=None):
    try:
        img = pyautogui.screenshot(region=region)
        if not isinstance(img, Image.Image):
            raise ValueError("Screenshot is not a valid PIL Image.")
        return img
    except Exception as e:
        raise RuntimeError(f"Screenshot failed: {e}")

def main():
    folder = "screen shots"
    # Delete the folder if it exists, then create a new one
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder, exist_ok=True)
    count = 0
    arrow_clicks = 0

    print(f"Waiting for {INITIAL_DELAY} seconds before starting screenshots...")
    time.sleep(INITIAL_DELAY)

    # Let user select region
    region = get_capture_region()

    while arrow_clicks < MAX_CLICKS:
        interval = random.randint(KEY_PRESS_MIN, KEY_PRESS_MAX)
        print(f"Waiting {interval} seconds before next down arrow key press...")
        time.sleep(interval)
        pyautogui.press('down')
        arrow_clicks += 1
        print(f"Simulated Down Arrow key press. Total: {arrow_clicks}")
        time.sleep(POST_KEY_WAIT)
        try:
            img = capture_screen(region=region)
            filename = os.path.join(folder, f"screenshot_{count}.png")
            img.save(filename)
            print(f"Saved screenshot {filename}")
            count += 1
        except Exception as e:
            print("Failed to capture screen. Exiting.")
            print(f"Error: {e}")
            break

        if arrow_clicks % PAUSE_AFTER_CLICKS == 0 and arrow_clicks < MAX_CLICKS:
            print(f"Reached {arrow_clicks} arrow clicks. Pausing for {PAUSE_DURATION // 60} minutes...")
            time.sleep(PAUSE_DURATION)

    print(f"Reached {MAX_CLICKS} arrow clicks. Exiting program.")

if __name__ == "__main__":
    main()
