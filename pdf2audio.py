import os
import subprocess
import sys
import math

# ----------- User Variables -----------
CHUNK_DURATION_MIN = 30  # Set chunk length (minutes)
OVERLAP_SECONDS = 5      # Set overlap (seconds)

# ----------- Auto-install Required Packages -----------
def install_if_needed(package, import_name=None):
    try:
        __import__(import_name or package)
    except ImportError:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

install_if_needed("PyPDF2")
install_if_needed("gtts")
install_if_needed("tqdm")  # for progress bar

# ----------- Imports -----------
import PyPDF2
from gtts import gTTS
from tqdm import tqdm

# ----------- Constants -----------
WORDS_PER_MIN = 150  # Average speech speed for gTTS
WORDS_PER_CHUNK = CHUNK_DURATION_MIN * WORDS_PER_MIN
OVERLAP_WORDS = int(OVERLAP_SECONDS * WORDS_PER_MIN / 60)

# ----------- Extract Text from PDF (Generator) -----------
def extract_text_by_page(pdf_file):
    with open(pdf_file, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                yield page_text.strip()

# ----------- Split Text into Overlapping Chunks (Generator) -----------
def split_text_into_chunks_gen(text_iter, words_per_chunk=WORDS_PER_CHUNK, overlap_words=OVERLAP_WORDS):
    buffer = []
    for text in text_iter:
        buffer.extend(text.split())
        while len(buffer) >= words_per_chunk:
            chunk = " ".join(buffer[:words_per_chunk])
            yield chunk
            buffer = buffer[words_per_chunk - overlap_words:]
    # Yield any remaining words as the last chunk
    if buffer:
        yield " ".join(buffer)

# ----------- Convert Text to Audio -----------
def convert_text_to_audio(text_chunk, output_path):
    tts = gTTS(text=text_chunk, lang="en")
    tts.save(output_path)

# ----------- Main Function -----------
def convert_pdf_to_audiobook(pdf_file, chunk_duration_min=CHUNK_DURATION_MIN, overlap_seconds=OVERLAP_SECONDS):
    print(f"\n🔍 Processing: {pdf_file}")
    base_name = os.path.splitext(pdf_file)[0]

    words_per_chunk = chunk_duration_min * WORDS_PER_MIN
    overlap_words = int(overlap_seconds * WORDS_PER_MIN / 60)

    text_iter = extract_text_by_page(pdf_file)
    chunks = list(split_text_into_chunks_gen(text_iter, words_per_chunk, overlap_words))
    if not chunks:
        print("❌ Skipping empty or unreadable PDF.")
        return

    print(f"🧩 PDF split into {len(chunks)} audio chunk(s) of ~{chunk_duration_min} mins each.")

    for idx, chunk in enumerate(tqdm(chunks, desc="🔊 Converting to audio", unit="chunk")):
        output_filename = f"{base_name}_part{idx + 1}.mp3"
        convert_text_to_audio(chunk, output_filename)

    print(f"✅ Completed: {pdf_file} ➜ {len(chunks)} audio file(s) generated.\n")

# ----------- Convert All PDFs in Directory -----------
def convert_all_pdfs_to_audio():
    pdf_files = [f for f in os.listdir('.') if f.lower().endswith('.pdf')]
    if not pdf_files:
        print("📂 No PDF files found in the current directory.")
        return

    for pdf_file in pdf_files:
        convert_pdf_to_audiobook(pdf_file, CHUNK_DURATION_MIN, OVERLAP_SECONDS)

if __name__ == "__main__":
    convert_all_pdfs_to_audio()
