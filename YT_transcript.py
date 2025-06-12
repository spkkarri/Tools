import os
import subprocess
import re
import sys
import socket
import argparse
import json
import requests

def install_package(package, pip_name=None):
    try:
        __import__(package)
    except ImportError:
        pip_pkg = pip_name if pip_name else package
        print(f"[INFO] Installing missing package: {pip_pkg}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_pkg])

# Install correct packages
print("[INFO] Checking and installing required packages...")
install_package("requests")
install_package("argparse")
try:
    import whisper
    if not hasattr(whisper, "load_model"):
        print("[WARNING] Incorrect whisper package detected, reinstalling openai-whisper.")
        raise ImportError
    print("[INFO] OpenAI Whisper is available.")
    WHISPER_AVAILABLE = True
except ImportError:
    print("[INFO] Uninstalling incorrect whisper package (if present)...")
    subprocess.call([sys.executable, "-m", "pip", "uninstall", "-y", "whisper"])
    install_package("whisper", "openai-whisper")
    import whisper
    print("[INFO] OpenAI Whisper installed and imported.")
    WHISPER_AVAILABLE = True
except Exception:
    print("[INFO] Whisper not available, falling back to HuggingFace transformers.")
    WHISPER_AVAILABLE = False
    install_package("transformers")
    install_package("torchaudio")
    from transformers import pipeline
    import torch

def extract_audio(video_file, output_path):
    print(f"[INFO] Extracting audio from: {video_file}")
    audio_file = os.path.join(output_path, os.path.splitext(os.path.basename(video_file))[0] + ".mp3")
    try:
        subprocess.run(
            ["ffmpeg", "-i", video_file, "-vn", "-acodec", "libmp3lame", "-ab", "192k", audio_file],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"[SUCCESS] Audio extracted to {audio_file}")
        return audio_file
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Error extracting audio from {video_file}: {e.stderr}")
        return None

def sanitize_filename(filename):
    """Sanitizes a filename by removing or replacing invalid characters."""
    return re.sub(r'[^\w\s-]', '', filename).strip().replace(' ', '_')

def list_ollama_models(ollama_ip="172.180.9.187", ollama_port=11434):  # Default Ollama port
    print(f"[INFO] Fetching available Ollama models from {ollama_ip}:{ollama_port} ...")
    try:
        url = f"http://{ollama_ip}:{ollama_port}/api/tags"
        response = requests.get(url)
        response.raise_for_status()
        models_data = response.json()
        models = [model["name"] for model in models_data["models"]]
        print(f"[SUCCESS] Fetched {len(models)} models from Ollama.")
        return models
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Error listing Ollama models: {e}")
        return None

def select_ollama_model(models):
    print("\n[INFO] Available Ollama Models:")
    for idx, model in enumerate(models):
        print(f"  {idx+1}. {model}")
    while True:
        try:
            choice = int(input("[INPUT] Select the Ollama model number to use for summarization: "))
            if 1 <= choice <= len(models):
                print(f"[INFO] Selected Ollama model: {models[choice-1]}")
                return models[choice-1]
        except Exception:
            pass
        print("[WARNING] Invalid selection. Please enter a valid number.")

def split_audio(audio_file, chunk_length=600, overlap=30):
    print(f"[INFO] Splitting audio into chunks (chunk_length={chunk_length}s, overlap={overlap}s)...")
    install_package("pydub")
    from pydub import AudioSegment
    audio = AudioSegment.from_file(audio_file)
    duration = len(audio) / 1000  # in seconds
    chunks = []
    start = 0
    idx = 0
    while start < duration:
        end = min(start + chunk_length, duration)
        chunk = audio[start*1000:end*1000]
        chunk_path = f"{audio_file}_chunk{idx}.mp3"
        chunk.export(chunk_path, format="mp3")
        print(f"[INFO] Created chunk: {chunk_path} ({start:.1f}s to {end:.1f}s)")
        chunks.append(chunk_path)
        if end == duration:
            break
        start = end - overlap
        idx += 1
    print(f"[SUCCESS] Total chunks created: {len(chunks)}")
    return chunks

def transcribe_audio_whisper(audio_file, model_name="large"):
    print(f"[INFO] Transcribing audio using Whisper ({model_name})...")
    import whisper
    model = whisper.load_model(model_name)
    install_package("pydub")
    from pydub.utils import mediainfo
    info = mediainfo(audio_file)
    duration = float(info['duration'])
    max_duration = 30 * 60  # 30 minutes, Whisper can handle up to this in one go
    if duration <= max_duration:
        result = model.transcribe(audio_file)
        print(f"[SUCCESS] Transcription completed for {audio_file}")
        return result["text"]
    else:
        print("[INFO] Audio is long, splitting into chunks for transcription...")
        chunks = split_audio(audio_file, chunk_length=max_duration-10, overlap=30)
        texts = []
        for chunk in chunks:
            print(f"[INFO] Transcribing chunk: {chunk}")
            result = model.transcribe(chunk)
            texts.append(result["text"])
            os.remove(chunk)
        print(f"[SUCCESS] All chunks transcribed and merged.")
        return "\n".join(texts)

def transcribe_audio_hf(audio_file, model_name="openai/whisper-large-v3", chunking_strategy="sliding_window"):
    print(f"[INFO] Transcribing audio using HuggingFace model: {model_name} with {chunking_strategy} chunking...")
    install_package("transformers")
    install_package("torch")
    install_package("pydub")
    from transformers import pipeline
    import torch

    # The pipeline handles chunking automatically for Whisper Large V3.
    # Set chunk_length_s and stride_length_s for sliding window if desired.
    pipe_kwargs = {
        "model": model_name,
        "device": 0 if torch.cuda.is_available() else -1,
        "generate_kwargs": {"task": "transcribe"},
    }
    if chunking_strategy == "sliding_window":
        # Use a stride for overlap/context retention
        pipe_kwargs["chunk_length_s"] = 30
        pipe_kwargs["stride_length_s"] = 5  # 5 seconds overlap for context

    pipe = pipeline("automatic-speech-recognition", **pipe_kwargs)

    # The pipeline will handle long audio automatically with chunking and context retention.
    result = pipe(audio_file)
    text = result["text"] if isinstance(result, dict) else result
    print(f"[SUCCESS] Transcription completed for {audio_file}")
    return text

def transcribe_audio(audio_file, model_name="large", stt_choice=None):
    # Only ask for STT model if stt_choice is not provided
    if stt_choice is None:
        print("[INFO] Asking user for preferred STT model...")
        print("Choose Speech-to-Text model:")
        print("1. OpenAI Whisper Large V3 (HuggingFace, open-source, accurate, context-aware)")
        print("2. Groq Whisper Large V3 Turbo (if you have API access, not open-source)")
        print("3. Default OpenAI Whisper (local, if available)")
        stt_choice = input("Enter 1, 2, or 3 [default 1]: ").strip() or "1"

    if stt_choice == "2":
        print("[INFO] Groq Whisper Large V3 Turbo selected. Please implement API call if you have access.")
        print("[ERROR] Groq Whisper Large V3 Turbo is not implemented in this script. Falling back to HuggingFace Whisper Large V3.")
        return transcribe_audio_hf(audio_file, model_name="openai/whisper-large-v3", chunking_strategy="sliding_window")
    elif stt_choice == "3":
        if WHISPER_AVAILABLE:
            return transcribe_audio_whisper(audio_file, model_name)
        else:
            print("[WARNING] Local Whisper not available. Falling back to HuggingFace Whisper Large V3.")
            return transcribe_audio_hf(audio_file, model_name="openai/whisper-large-v3", chunking_strategy="sliding_window")
    else:
        # Default: HuggingFace Whisper Large V3 with sliding window chunking
        return transcribe_audio_hf(audio_file, model_name="openai/whisper-large-v3", chunking_strategy="sliding_window")

def summarize_transcript(transcript, ollama_ip="172.180.9.187", ollama_port=11434, model="llama2"):
    print(f"[INFO] Sending transcript to Ollama ({model}) for summarization...")
    try:
        url = f"http://{ollama_ip}:{ollama_port}/api/generate"
        data = {
            "model": model,
            "prompt": (
                "You are a highly skilled strategy expert with extensive knowledge of technical terminologies and execution procedures. "
                "Your task is to provide an extremely detailed summary of the following transcript, ensuring that no core component, "
                "key terminology, or strategic element is omitted. The summary should be an excessive depiction of the transcript's content.\n\n"
                "Here's an example of how to summarize a strategy transcript:\n"
                "Transcript: \"The core strategy involves a three-pronged approach: first, we leverage AI for data analysis; second, we implement blockchain for secure transactions; and third, we utilize cloud computing for scalability. Key terminologies include: AI, Blockchain, Cloud Computing, Scalability, and Secure Transactions. The execution procedure involves setting up AWS instances, deploying a Hyperledger Fabric network, and integrating a TensorFlow model.\"\n"
                "Summary: \"The core strategy is a three-pronged approach: (1) AI-driven data analysis using TensorFlow models, (2) secure transactions via a Hyperledger Fabric blockchain network, and (3) cloud computing on AWS for scalability. Key terminologies: AI, Blockchain, Cloud Computing, Scalability, Secure Transactions, TensorFlow, Hyperledger Fabric, AWS. Execution: Set up AWS EC2 instances, deploy Hyperledger Fabric network, integrate TensorFlow model for AI-driven data analysis.\"\n\n"
                f"Now, summarize the following transcript:\n{transcript}"
            ),
            "stream": False  # Get the full response at once
        }
        response = requests.post(url, json=data, stream=False)
        response.raise_for_status()
        response_json = response.json()
        summary = response_json["response"]
        print(f"[SUCCESS] Summary received from Ollama.")
        return summary
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Error summarizing transcript with Ollama: {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        print(f"[ERROR] Error parsing Ollama response: {e}")
        return None

def main(video_folder, ollama_ip, ollama_port, whisper_model="large", ollama_model=None):
    print(f"[INFO] Starting processing for folder: {video_folder}")
    abs_video_folder = os.path.abspath(video_folder)
    parent_dir = os.path.dirname(abs_video_folder)
    base_folder_name = os.path.basename(abs_video_folder.rstrip("/"))
    transcript_root = os.path.join(parent_dir, base_folder_name + "_transcripts")

    output_path = os.path.join(transcript_root, "audio_output")
    transcript_path = os.path.join(transcript_root, "transcript_output")

    os.makedirs(output_path, exist_ok=True)
    os.makedirs(transcript_path, exist_ok=True)

    models = list_ollama_models(ollama_ip, ollama_port)
    if models:
        ollama_model = select_ollama_model(models)
    else:
        print("[WARNING] Could not retrieve Ollama models. Using default: llama2")
        ollama_model = "llama2"

    video_files = [f for f in os.listdir(video_folder) if f.endswith(".mp4")]
    print(f"[INFO] Found {len(video_files)} video files to process.")

    # Ask user for STT model only once
    print("[INFO] Initial Speech-to-Text model selection:")
    print("Choose Speech-to-Text model:")
    print("1. OpenAI Whisper Large V3 (HuggingFace, open-source, accurate, context-aware)")
    print("2. Groq Whisper Large V3 Turbo (if you have API access, not open-source)")
    print("3. Default OpenAI Whisper (local, if available)")
    stt_choice = input("Enter 1, 2, or 3 [default 1]: ").strip() or "1"

    for idx, video_file in enumerate(video_files, 1):
        video_path = os.path.join(video_folder, video_file)
        print(f"\n[STEP {idx}/{len(video_files)}] Processing: {video_path}")

        audio_file = extract_audio(video_path, output_path)
        if audio_file:
            print(f"[INFO] Starting transcription for: {audio_file}")
            transcript = transcribe_audio(audio_file, model_name=whisper_model, stt_choice=stt_choice)
            if transcript:
                base_name = os.path.splitext(video_file)[0]
                # Save transcript as .txt instead of .exe
                transcript_file = os.path.join(transcript_path, sanitize_filename(base_name) + ".txt")
                try:
                    with open(transcript_file, "w", encoding="utf-8") as f:
                        f.write(transcript)
                    print(f"[SUCCESS] Transcript saved to {transcript_file}")

                    print(f"[INFO] Starting summarization for: {base_name}")
                    summary = summarize_transcript(transcript, ollama_ip, ollama_port, ollama_model)
                    if summary:
                        summary_file = os.path.join(transcript_path, sanitize_filename(base_name) + "_summary.txt")
                        with open(summary_file, "w", encoding="utf-8") as f:
                            f.write(summary)
                        print(f"[SUCCESS] Summary saved to {summary_file}")
                    else:
                        print(f"[ERROR] Summary generation failed for {video_file}")

                except Exception as e:
                    print(f"[ERROR] Error saving transcript for {video_file}: {e}")
            else:
                print(f"[ERROR] Transcription failed for {video_file}")
        else:
            print(f"[ERROR] Audio extraction failed for {video_file}")

    print("[INFO] All processing complete.")

if __name__ == "__main__":
    print("[INFO] Parsing command-line arguments...")
    parser = argparse.ArgumentParser(description="Transcribe and summarize video files.")
    parser.add_argument("video_folder", nargs="?", default="MF", help="Path to the video folder (default: current directory)")
    parser.add_argument("--ollama_ip", default="172.180.9.187", help="Ollama server IP address (default: 172.180.9.187)")
    parser.add_argument("--ollama_port", type=int, default=8080, help="Ollama server port (default: 11434)")
    parser.add_argument("--whisper_model", default="large", help="Whisper model to use (default: large)")
    args = parser.parse_args()

    main(args.video_folder, args.ollama_ip, args.ollama_port, args.whisper_model)
