import tkinter as tk
from tkinter import ttk, messagebox
import os
import re
import subprocess
import sys

# Function to install missing packages
def install_package(package):
    try:
        __import__(package)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Install required package
required_packages = ["yt-dlp"]
for pkg in required_packages:
    install_package(pkg)

import yt_dlp

# Function to sanitize filename
def sanitize_filename(filename):
    return re.sub(r'[^\w\s-]', '', filename).strip().replace(' ', '_')

# Function to download a single video
def download_video(url, quality, output_path, file_list, status_label, text_area, root):
    try:
        ydl_opts = {
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'progress_hooks': [lambda d: update_progress(d, file_list, text_area, root)],
        }

        if quality == "Audio Only":
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            ydl_opts.update({
                'format': f'bestvideo[height<={quality[:-1]}]+bestaudio/best',
                'merge_output_format': 'mp4',
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = sanitize_filename(info['title'])
            file_list[title] = "100%"
            update_text_area(file_list, text_area, root)
            status_label.config(text=f"Downloaded: {title}")
    except Exception as e:
        status_label.config(text="Error occurred")
        messagebox.showerror("Error", f"Download failed: {str(e)}")

# Function to download a playlist
def download_playlist(url, quality, output_path, file_list, status_label, text_area, root):
    try:
        ydl_opts = {
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'noplaylist': False,
            'progress_hooks': [lambda d: update_progress(d, file_list, text_area, root)],
        }

        if quality == "Audio Only":
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            ydl_opts.update({
                'format': f'bestvideo[height<={quality[:-1]}]+bestaudio/best',
                'merge_output_format': 'mp4',
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            status_label.config(text="Playlist download complete")
            messagebox.showinfo("Success", "Playlist downloaded successfully")
    except Exception as e:
        status_label.config(text="Error occurred")
        messagebox.showerror("Error", f"Playlist download failed: {str(e)}")

# Function to update progress
def update_progress(d, file_list, text_area, root):
    if d['status'] == 'downloading':
        try:
            title = sanitize_filename(os.path.basename(d.get('filename', 'Unknown')))
            percent = d.get('_percent_str', '0%').strip()
            total_bytes = d.get('total_bytes', d.get('total_bytes_estimate', 0))
            downloaded_bytes = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0) or 0
            eta = d.get('eta', 0) or 0

            # Convert bytes to human-readable format
            def format_bytes(b):
                for unit in ['B', 'KiB', 'MiB', 'GiB']:
                    if b < 1024:
                        return f"{b:.2f}{unit}"
                    b /= 1024
                return f"{b:.2f}TiB"

            # Format time
            minutes, seconds = divmod(eta, 60)
            time_str = f"{minutes:02d}:{seconds:02d}"

            # Format progress string like terminal
            progress_str = f"[download] {percent} of {format_bytes(total_bytes)} in {time_str} at {format_bytes(speed)}/s"
            file_list[title] = progress_str
            update_text_area(file_list, text_area, root)
        except (ValueError, KeyError):
            pass
    elif d['status'] == 'finished':
        title = sanitize_filename(os.path.basename(d.get('filename', 'Unknown')))
        file_list[title] = "100%"
        update_text_area(file_list, text_area, root)

# Function to update text area with file list and autoscroll
def update_text_area(file_list, text_area, root):
    text_area.config(state='normal')
    text_area.delete(1.0, tk.END)
    for title, progress in file_list.items():
        text_area.insert(tk.END, f"{title}: {progress}\n")
    text_area.config(state='disabled')
    text_area.yview_moveto(1.0)  # Autoscroll to bottom
    root.update()

# Main download function
def start_download():
    url = url_entry.get().strip()
    quality = quality_var.get()
    output_path = os.path.join(os.getcwd(), "downloads")
    
    if not url:
        messagebox.showerror("Error", "Please enter a YouTube URL")
        return
    
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    
    status_label.config(text="Starting download...", fg="white")
    file_list.clear()
    text_area.config(state='normal')
    text_area.delete(1.0, tk.END)
    text_area.config(state='disabled')
    
    # Check if URL is a playlist
    if "playlist" in url.lower():
        download_playlist(url, quality, output_path, file_list, status_label, text_area, root)
    else:
        download_video(url, quality, output_path, file_list, status_label, text_area, root)

# GUI setup
root = tk.Tk()
root.title("YouTube Downloader")
root.geometry("600x500")
root.configure(bg="#2E2E2E")  # Dark background for contrast

# Styling
style = ttk.Style()
style.configure("TCombobox", fieldbackground="#404040", background="#404040", foreground="white")
style.map("TCombobox", fieldbackground=[("readonly", "#404040")], selectbackground=[("readonly", "#404040")])

# URL input
tk.Label(root, text="YouTube URL:", bg="#2E2E2E", fg="white", font=("Arial", 12)).pack(pady=10)
url_entry = tk.Entry(root, width=60, bg="#404040", fg="white", insertbackground="white")
url_entry.pack()

# Quality selection
tk.Label(root, text="Download Option:", bg="#2E2E2E", fg="white", font=("Arial", 12)).pack(pady=10)
quality_var = tk.StringVar(value="720p")
quality_menu = ttk.Combobox(root, textvariable=quality_var, values=["360p", "720p", "1080p", "Audio Only"], state="readonly")
quality_menu.pack()

# Download button
tk.Button(root, text="Download", command=start_download, bg="#00FF00", fg="black", font=("Arial", 12, "bold")).pack(pady=20)

# Scrollable text area for file list
tk.Label(root, text="Download Progress:", bg="#2E2E2E", fg="white", font=("Arial", 12)).pack(pady=5)
scrollbar = tk.Scrollbar(root)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
text_area = tk.Text(root, height=10, width=70, bg="#404040", fg="white", font=("Arial", 10), yscrollcommand=scrollbar.set, state='disabled')
text_area.pack(padx=20, pady=5)
scrollbar.config(command=text_area.yview)

# Status label
status_label = tk.Label(root, text="Ready", bg="#2E2E2E", fg="white", font=("Arial", 10), wraplength=500)
status_label.pack(pady=10)

# File list to track progress
file_list = {}

# Start the GUI
root.mainloop()
