import os
import subprocess
import re
import sys
import argparse
import json
import requests
import math

# --- Helper Functions ---

def install_package(package, pip_name=None):
    """Checks if a package is installed and installs it if missing."""
    try:
        __import__(package)
    except ImportError:
        pip_pkg = pip_name if pip_name else package
        print(f"[INFO] Installing missing package: {pip_pkg}")
        # --- CHANGE: Added specific handling for CUDA related packages ---
        if pip_pkg in ["ctranslate2", "faster-whisper"]:
             print(f"[HINT] The installation of '{pip_pkg}' may take a while. It is being compiled for your system.")
             print("[HINT] For GPU support with faster-whisper, ensure you have the correct NVIDIA CUDA Toolkit installed.")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_pkg])

def sanitize_filename(filename):
    """Sanitizes a filename by removing or replacing invalid characters."""
    return re.sub(r'[^\w\s-]', '', filename).strip().replace(' ', '_')

# --- Package Installation ---
print("[INFO] Checking and installing required packages...")
install_package("requests")
install_package("argparse")
install_package("pydub")
install_package("tiktoken")
install_package("torch")
install_package("torchaudio")
install_package("ollama")
# --- CHANGE: Added faster-whisper and its dependency ---
install_package("ctranslate2")
install_package("faster_whisper", pip_name="faster-whisper")
try:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--upgrade", "transformers", "openai-whisper"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
except subprocess.CalledProcessError as e:
    print(f"[WARNING] Could not silently upgrade packages. Continuing with existing versions. Error: {e}")

import ollama

# --- Core Functions ---

def extract_audio(video_file, output_path):
    """Extracts audio from a video file using FFmpeg."""
    print(f"[INFO] Extracting audio from: {video_file}")
    audio_file = os.path.join(output_path, os.path.splitext(os.path.basename(video_file))[0] + ".mp3")
    try:
        subprocess.run(
            ["ffmpeg", "-i", video_file, "-y", "-vn", "-acodec", "libmp3lame", "-ab", "192k", audio_file],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"[SUCCESS] Audio extracted to {audio_file}")
        return audio_file
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] FFmpeg error extracting audio from {video_file}: {e.stderr}")
        return None
    except FileNotFoundError:
        print("[ERROR] FFmpeg command not found. Please install FFmpeg and ensure it's in your system's PATH.")
        return None

def list_ollama_models(ollama_ip, ollama_port):
    """Fetches and lists available models from the Ollama server using a direct API call."""
    print(f"[INFO] Fetching available Ollama models from http://{ollama_ip}:{ollama_port} ...")
    try:
        url = f"http://{ollama_ip}:{ollama_port}/api/tags"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        models_data = response.json()
        models = [model["name"] for model in models_data.get("models", []) if "name" in model]
        if not models:
            print("[WARNING] No models found on the Ollama server.")
            return None
        print(f"[SUCCESS] Fetched {len(models)} models from Ollama.")
        return models
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Could not connect to Ollama server at http://{ollama_ip}:{ollama_port}. Error: {e}")
        return None

def select_ollama_model(models):
    """Prompts the user to select an Ollama model from a list."""
    print("\n[INFO] Available Ollama Models for Summarization:")
    for idx, model in enumerate(models):
        print(f"  {idx+1}. {model}")
    while True:
        try:
            choice = int(input(f"[INPUT] Select the Ollama model number to use [1-{len(models)}]: "))
            if 1 <= choice <= len(models):
                selected_model = models[choice-1]
                print(f"[INFO] Selected Ollama model: {selected_model}")
                return selected_model
        except (ValueError, IndexError):
            pass
        print("[WARNING] Invalid selection. Please enter a valid number.")

def transcribe_audio_hf(audio_file, model_name="openai/whisper-large-v3"):
    """Transcribes audio using the standard HuggingFace pipeline."""
    print(f"[INFO] Transcribing audio using standard HuggingFace model: {model_name}.")
    print("[INFO] This may take some time...")
    try:
        import torch
        from transformers import pipeline
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        torch_dtype = torch.float16 if "cuda" in device else torch.float32
        print(f"[INFO] Using device: {device} with dtype: {torch_dtype}")
        pipe = pipeline(
            "automatic-speech-recognition", model=model_name, torch_dtype=torch_dtype, device=device,
        )
        result = pipe(audio_file, chunk_length_s=30, stride_length_s=5, return_timestamps=False)
        transcript = result["text"]
        print(f"[SUCCESS] HuggingFace transcription completed for {audio_file}")
        return transcript
    except Exception as e:
        print(f"[ERROR] An error occurred during HuggingFace transcription: {e}")
        return None

# --- CHANGE: Added new function for faster-whisper ---
def transcribe_audio_faster_whisper(audio_file, model_name="large-v3"):
    """Transcribes audio using the optimized faster-whisper library."""
    print(f"[INFO] Transcribing audio using Faster-Whisper (Turbo) model: {model_name}.")
    print("[INFO] This should be significantly faster, especially on a GPU.")
    try:
        from faster_whisper import WhisperModel
        import torch

        # Determine device and compute type for optimal performance
        if torch.cuda.is_available():
            device = "cuda"
            compute_type = "float16"
            print("[INFO] Using device: CUDA (GPU) with compute type: float16")
        else:
            device = "cpu"
            compute_type = "int8"
            print("[INFO] Using device: CPU with compute type: int8")

        model = WhisperModel(model_name, device=device, compute_type=compute_type)
        segments, _ = model.transcribe(audio_file, beam_size=5)
        transcript = "".join(segment.text for segment in segments)
        print(f"[SUCCESS] Faster-Whisper transcription completed for {audio_file}")
        return transcript.strip()
    except Exception as e:
        print(f"[ERROR] An error occurred during Faster-Whisper transcription: {e}")
        print("[HINT] Ensure CUDA toolkit is correctly installed for GPU support, or this will fall back to CPU.")
        return None

# --- CHANGE: Updated wrapper to handle STT model choice ---
def transcribe_audio(audio_file, stt_choice, whisper_model_size):
    """Wrapper function to select and run the chosen STT model."""
    # Note: faster-whisper uses short names like 'large-v3', while transformers uses 'openai/whisper-large-v3'
    hf_model_name = f"openai/whisper-{whisper_model_size}"
    faster_whisper_model_name = whisper_model_size

    print(f"[INFO] Preparing to transcribe with model size: {whisper_model_size}")

    if stt_choice == "1":
        return transcribe_audio_hf(audio_file, model_name=hf_model_name)
    elif stt_choice == "2":
        return transcribe_audio_faster_whisper(audio_file, model_name=faster_whisper_model_name)
    else:
        print("[WARNING] Invalid STT choice. Defaulting to standard HuggingFace.")
        return transcribe_audio_hf(audio_file, model_name=hf_model_name)

def split_text_into_chunks(text, max_tokens=4096):
    """Splits a long text into smaller chunks based on token count."""
    import tiktoken
    print(f"[INFO] Splitting transcript into chunks for the summarizer (max_tokens={max_tokens})...")
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    tokens = encoding.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + max_tokens
        chunk_tokens = tokens[start:end]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)
        start = end
    print(f"[INFO] Transcript split into {len(chunks)} chunk(s).")
    return chunks

def ollama_generate_with_library(client, prompt, model):
    """Sends a prompt to the Ollama API using the official library and returns the response."""
    try:
        response = client.generate(model=model, prompt=prompt)
        summary = response.get("response", "").strip()
        print("[SUCCESS] Response received from Ollama.")
        return summary
    except Exception as e:
        print(f"[ERROR] An error occurred calling the Ollama API via the library: {e}")
        return None

def summarize_transcript_recursive(transcript, client, model):
    """Summarizes a transcript using a recursive map-reduce approach."""
    print("[INFO] Starting recursive summarization process...")
    chunks = split_text_into_chunks(transcript, max_tokens=4096)
    if len(chunks) == 1:
        print("[INFO] Transcript is short. Performing direct summarization.")
        final_summary_prompt = create_final_summary_prompt(chunks[0])
        return ollama_generate_with_library(client, final_summary_prompt, model)
    intermediate_summaries = []
    for i, chunk in enumerate(chunks):
        print(f"[INFO] Summarizing chunk {i+1}/{len(chunks)}...")
        intermediate_prompt = (
            "You are a helpful assistant. Your task is to summarize the following section of a financial lecture transcript. "
            "Focus on extracting the key points, definitions, and strategies discussed in this specific part.\n\n"
            f"Transcript Section:\n\"\"\"\n{chunk}\n\"\"\"\n\n"
            "Provide a concise summary of this section:"
        )
        summary = ollama_generate_with_library(client, intermediate_prompt, model)
        if summary:
            intermediate_summaries.append(summary)
        else:
            print(f"[WARNING] Failed to summarize chunk {i+1}. It will be skipped.")
    if not intermediate_summaries:
        return "[ERROR] Could not generate any intermediate summaries."
    print("[INFO] All chunks summarized. Creating final combined summary...")
    combined_text = "\n\n---\n\n".join(intermediate_summaries)
    final_prompt = create_final_summary_prompt(combined_text, is_combined=True)
    final_summary = ollama_generate_with_library(client, final_prompt, model)
    return final_summary

def create_final_summary_prompt(text, is_combined=False):
    """Creates a high-quality, finance-focused prompt for the final summarization step."""
    source_text_type = "a collection of summaries from different parts of a lecture" if is_combined else "a lecture transcript"
    prompt = (
        "You are an expert financial analyst and educator. Your task is to create a comprehensive, detailed summary of "
        f"{source_text_type} on a financial topic (e.g., stock market, securities, equity, mutual funds). "
        "The summary must be well-structured, easy to read, and highlight all key concepts, definitions, strategies, and examples mentioned. "
        "Use markdown for formatting, such as headings, bullet points, and bold text, to improve readability.\n\n"
        f"Now, based on the principles above, create a comprehensive summary of the following text:\n\n"
        f"Source Text:\n\"\"\"\n{text}\n\"\"\"\n\n"
        "Comprehensive Summary:"
    )
    return prompt

def main(args):
    """Main function to orchestrate the video processing pipeline."""
    video_folder = args.video_folder
    ollama_host = f"http://{args.ollama_ip}:{args.ollama_port}"
    whisper_model_size = args.whisper_model

    print(f"[INFO] Starting processing for folder: {video_folder}")
    if not os.path.isdir(video_folder):
        print(f"[ERROR] Video folder not found: {video_folder}")
        sys.exit(1)

    abs_video_folder = os.path.abspath(video_folder)
    parent_dir = os.path.dirname(abs_video_folder)
    base_folder_name = os.path.basename(abs_video_folder.rstrip(os.sep))
    transcript_root = os.path.join(parent_dir, f"{base_folder_name}_Output")
    audio_path = os.path.join(transcript_root, "1_Audio_Files")
    transcript_path = os.path.join(transcript_root, "2_Transcripts")
    summary_path = os.path.join(transcript_root, "3_Summaries")
    os.makedirs(audio_path, exist_ok=True)
    os.makedirs(transcript_path, exist_ok=True)
    os.makedirs(summary_path, exist_ok=True)

    models = list_ollama_models(args.ollama_ip, args.ollama_port)
    if models:
        ollama_model_choice = select_ollama_model(models)
    else:
        print("[ERROR] Could not retrieve Ollama models. Exiting.")
        sys.exit(1)

    print(f"[INFO] Initializing Ollama client for host: {ollama_host}")
    try:
        ollama_client = ollama.Client(host=ollama_host)
    except Exception as e:
        print(f"[ERROR] Failed to create Ollama client: {e}")
        sys.exit(1)

    # --- CHANGE: Updated STT selection menu ---
    print("\n[INFO] Please choose the local Speech-to-Text (STT) engine.")
    print("  1. Standard Whisper (via HuggingFace - Accurate, Slower)")
    print("  2. Turbo Whisper (via faster-whisper - Accurate, Much Faster on GPU)")
    stt_choice = ""
    while stt_choice not in ["1", "2"]:
        stt_choice = input("Enter your choice [1 or 2, default 2]: ").strip() or "2"
        if stt_choice not in ["1", "2"]:
            print("[WARNING] Invalid choice. Please enter 1 or 2.")

    video_files = [f for f in os.listdir(video_folder) if f.lower().endswith((".mp4", ".mov", ".avi", ".mkv"))]
    if not video_files:
        print(f"[WARNING] No video files found in '{video_folder}'.")
        return

    print(f"\n[INFO] Found {len(video_files)} video file(s) to process.")
    for idx, video_file in enumerate(video_files, 1):
        video_path = os.path.join(video_folder, video_file)
        base_name = sanitize_filename(os.path.splitext(video_file)[0])
        print(f"\n{'='*20} [ {idx}/{len(video_files)}: {video_file} ] {'='*20}")

        audio_file = extract_audio(video_path, audio_path)
        if not audio_file:
            print(f"[SKIPPING] Audio extraction failed for {video_file}.")
            continue

        # --- CHANGE: Pass the user's STT choice to the transcribe function ---
        transcript = transcribe_audio(audio_file, stt_choice, whisper_model_size)
        if transcript:
            transcript_file = os.path.join(transcript_path, f"{base_name}_transcript.txt")
            with open(transcript_file, "w", encoding="utf-8") as f: f.write(transcript)
            print(f"[SUCCESS] Transcript saved to {transcript_file}")
        else:
            print(f"[SKIPPING] Transcription failed for {video_file}.")
            continue

        print(f"[INFO] Starting summarization for: {base_name}")
        summary = summarize_transcript_recursive(transcript, ollama_client, ollama_model_choice)
        if summary:
            summary_file = os.path.join(summary_path, f"{base_name}_summary.md")
            with open(summary_file, "w", encoding="utf-8") as f: f.write(summary)
            print(f"[SUCCESS] Summary saved to {summary_file}")
        else:
            print(f"[ERROR] Summary generation failed for {video_file}")

    print(f"\n{'='*20} [ Processing Complete ] {'='*20}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe and summarize video files.")
    parser.add_argument("video_folder", nargs="?", default="MF", help="Path to the video folder (default: MF)")
    parser.add_argument("--ollama_ip", default="172.180.9.187", help="Ollama server IP address (default: 172.180.9.187)")
    parser.add_argument("--ollama_port", type=int, default=8080, help="Ollama server port (default: 8080)")
    parser.add_argument("--whisper_model", default="large-v3", help="Whisper model size to use (e.g., 'tiny', 'base', 'small', 'medium', 'large-v3'). Default: large-v3")
    args = parser.parse_args()
    main(args)
