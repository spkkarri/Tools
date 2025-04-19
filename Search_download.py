#pip install duckduckgo_search google-generativeai arxiv
import duckduckgo_search
import requests
import os
import google.generativeai as genai
import arxiv
import re

# Gemini API setup (replace with your actual free tier API key)
genai.configure(api_key="AIxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
model = genai.GenerativeModel('gemini-2.0-flash')

# Search query
query = "Machine learning textbooks and lecture notes filetype:pdf"

# DuckDuckGo search
ddg = duckduckgo_search.DDGS()
results = ddg.text(query, max_results=100)

# Save links to links.txt
with open("pdf_links.txt", "w") as f:
    for result in results:
        f.write(result["href"] + "\n")

# Function to check if URL is a PDF
def is_pdf(url):
    return url.lower().endswith('.pdf')

def is_arxiv_url(url):
    return "arxiv.org" in url

def download_arxiv_pdf(arxiv_id, filename):
    try:
        search = arxiv.Search(id_list=[arxiv_id])
        result = next(search.results())
        response = requests.get(result.pdf_url, stream=True, timeout=10)
        response.raise_for_status()

        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Downloaded: {filename}")

    except Exception as e:
        print(f"Error downloading arXiv PDF: {e}")

# Download PDFs
def download_pdf(url, index):
    try:
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
            filename = f"pdf_{index}.pdf"
            with open(filename, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded: {filename}")
    except Exception:
        pass

# Create pdf_links.txt if it doesn't exist, or read from it if it does
if not os.path.exists("pdf_links.txt"):
    open("pdf_links.txt", "w").close()  # Create an empty file

# Read links from pdf_links.txt
with open("pdf_links.txt", "r") as f:
    links = f.readlines()

# Gemini API to filter relevant links
relevant_links = []
for link in links:
    link = link.strip()
    prompt = f"Is this link relevant to AI and LLM driven agents? URL: {link}"
    try:
        response = model.generate_content(prompt, generation_config=genai.GenerationConfig(max_output_tokens=50))
        if "yes" in response.text.lower():
            relevant_links.append(link)
    except Exception as e:
        print(f"Error processing link {link} with Gemini: {e}")

# Download PDFs from relevant links
for i, link in enumerate(relevant_links):
    link = link.strip()
    if is_pdf(link):
        if is_arxiv_url(link):
            # Extract arXiv ID
            match = re.search(r'arxiv\.org/abs/(\d+\.\d+)', link)
            if match:
                arxiv_id = match.group(1)
                filename = f"arxiv_{arxiv_id}.pdf"
                download_arxiv_pdf(arxiv_id, filename)
            else:
                download_pdf(link, i)
        else:
            download_pdf(link, i)
