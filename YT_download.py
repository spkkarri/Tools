import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import re
import subprocess
import sys
import threading
import shutil

# Function to install missing packages
def install_package(package):
    try:
        __import__(package)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Install required packages
for pkg in ["yt_dlp"]:
    install_package(pkg)

import yt_dlp

# Sanitize filename
def sanitize_filename(filename):
    return re.sub(r'[^\w\s-]', '', filename).strip().replace(' ', '_')

# Check if ffmpeg is available
def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        messagebox.showerror("Missing FFmpeg", "FFmpeg not found in system PATH. Please install it to continue.")
        return False
    return True

# Detect if URL is a playlist
def is_playlist(url):
    try:
        with yt_dlp.YoutubeDL({}) as ydl:
            info = ydl.extract_info(url, download=False)
            return 'entries' in info
    except Exception:
        return False

# Update progress
def update_progress(d, file_list, text_area, root):
    if d['status'] == 'downloading':
        try:
            title = sanitize_filename(d['info_dict'].get('title', 'Unknown'))
            percent = d.get('_percent_str', '0%').strip()
            total_bytes = d.get('total_bytes', d.get('total_bytes_estimate', 0))
            downloaded_bytes = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0) or 0
            eta = d.get('eta', 0) or 0

            def format_bytes(b):
                for unit in ['B', 'KiB', 'MiB', 'GiB']:
                    if b < 1024:
                        return f"{b:.2f}{unit}"
                    b /= 1024
                return f"{b:.2f}TiB"

            minutes, seconds = divmod(eta, 60)
            time_str = f"{minutes:02d}:{seconds:02d}"
            progress_str = f"[download] {percent} of {format_bytes(total_bytes)} in {time_str} at {format_bytes(speed)}/s"
            file_list[title] = progress_str
            update_text_area(file_list, text_area, root)
        except Exception:
            pass
    elif d['status'] == 'finished':
        title = sanitize_filename(d['info_dict'].get('title', 'Unknown'))
        file_list[title] = "100%"
        update_text_area(file_list, text_area, root)

# Update text area
def update_text_area(file_list, text_area, root):
    text_area.config(state='normal')
    text_area.delete(1.0, tk.END)
    for title, progress in file_list.items():
        text_area.insert(tk.END, f"{title}: {progress}\n")
    text_area.config(state='disabled')
    text_area.yview_moveto(1.0)
    root.update()

# Download a single video
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

# Download playlist
def download_playlist(url, quality, output_path, file_list, status_label, text_area, root):
    try:
        ydl_opts = {
    		'outtmpl': os.path.join(output_path, '%(playlist_index)s-%(title)s.%(ext)s'),
    		'noplaylist': False,
    		'progress_hooks': [lambda d: update_progress(d, file_list, text_area, root)],
    		'format': f'bestvideo[height<={quality[:-1]}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    		'ignoreerrors': True,
    		'merge_output_format': 'mp4',
		}

        if quality == "Audio Only":
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                        'ignoreerrors': True
            })
        else:
            ydl_opts.update({
                'format': f'bestvideo[height<={quality[:-1]}]+bestaudio/best',
                'merge_output_format': 'mp4',
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            status_label.config(text="Playlist download complete")
            messagebox.showinfo("Success", "Playlist downloaded successfully")
    except Exception as e:
        status_label.config(text="Error occurred")
        messagebox.showerror("Error", f"Playlist download failed: {str(e)}")

# Threaded download logic
def threaded_download(url, quality, output_path, file_list, status_label, text_area, root):
    if is_playlist(url):
        download_playlist(url, quality, output_path, file_list, status_label, text_area, root)
    else:
        download_video(url, quality, output_path, file_list, status_label, text_area, root)

# Start download from GUI
def start_download():
    url = url_entry.get().strip()
    quality = quality_var.get()
    output_path = dir_var.get()

    if not url:
        messagebox.showerror("Error", "Please enter a YouTube URL")
        return

    if not check_ffmpeg():
        return

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    status_label.config(text="Starting download...", fg="white")
    file_list.clear()
    text_area.config(state='normal')
    text_area.delete(1.0, tk.END)
    text_area.config(state='disabled')

    threading.Thread(
        target=threaded_download,
        args=(url, quality, output_path, file_list, status_label, text_area, root),
        daemon=True
    ).start()

# Select directory
def choose_directory():
    path = filedialog.askdirectory()
    if path:
        dir_var.set(path)

# GUI setup
root = tk.Tk()
root.title("YouTube Downloader")
root.geometry("650x550")
root.configure(bg="#2E2E2E")

style = ttk.Style()
style.configure("TCombobox", fieldbackground="#404040", background="#404040", foreground="white")
style.map("TCombobox", fieldbackground=[("readonly", "#404040")], selectbackground=[("readonly", "#404040")])

tk.Label(root, text="YouTube URL:", bg="#2E2E2E", fg="white", font=("Arial", 12)).pack(pady=10)
url_entry = tk.Entry(root, width=70, bg="#404040", fg="white", insertbackground="white")
url_entry.pack()

tk.Label(root, text="Download Option:", bg="#2E2E2E", fg="white", font=("Arial", 12)).pack(pady=10)
quality_var = tk.StringVar(value="720p")
quality_menu = ttk.Combobox(root, textvariable=quality_var, values=["360p", "720p", "1080p", "Audio Only"], state="readonly")
quality_menu.pack()

tk.Label(root, text="Download Location:", bg="#2E2E2E", fg="white", font=("Arial", 12)).pack(pady=10)
dir_var = tk.StringVar(value=os.path.join(os.getcwd(), "downloads"))
dir_frame = tk.Frame(root, bg="#2E2E2E")
dir_frame.pack(pady=5)
tk.Entry(dir_frame, textvariable=dir_var, width=55, bg="#404040", fg="white", insertbackground="white").pack(side=tk.LEFT)
tk.Button(dir_frame, text="Browse", command=choose_directory, bg="#404040", fg="white").pack(side=tk.LEFT, padx=5)

tk.Button(root, text="Download", command=start_download, bg="#00FF00", fg="black", font=("Arial", 12, "bold")).pack(pady=20)

tk.Label(root, text="Download Progress:", bg="#2E2E2E", fg="white", font=("Arial", 12)).pack()
scrollbar = tk.Scrollbar(root)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
text_area = tk.Text(root, height=10, width=80, bg="#404040", fg="white", font=("Arial", 10), yscrollcommand=scrollbar.set, state='disabled')
text_area.pack(padx=20, pady=5)
scrollbar.config(command=text_area.yview)

status_label = tk.Label(root, text="Ready", bg="#2E2E2E", fg="white", font=("Arial", 10), wraplength=500)
status_label.pack(pady=10)

file_list = {}

root.mainloop()
