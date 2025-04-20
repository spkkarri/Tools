import duckduckgo_search
import requests
import os
import google.generativeai as genai
import arxiv
import re
from urllib.parse import urlparse

# Gemini API setup (replace with your actual free tier API key)
genai.configure(api_key=api_key)  # Replace with your Gemini API key
model = genai.GenerativeModel('gemini-2.0-flash')

# Create pdfs folder if it doesn't exist
pdfs_folder = "pdfs"
if not os.path.exists(pdfs_folder):
    os.makedirs(pdfs_folder)

# Initial search query and other unchanged setup code...
base_query = "Algorithmic trading using Python textbooks and lecture notes filetype:pdf"
query_variants = [
    base_query,
    "Python algorithmic trading textbooks filetype:pdf",
    "Algorithmic trading Python lecture notes filetype:pdf",
    "Quantitative finance Python textbooks filetype:pdf",
    "High-frequency trading Python notes filetype:pdf",
    "Machine learning for algorithmic trading Python filetype:pdf"
]

# Function to check if URL is a PDF
def is_pdf(url):
    return url.lower().endswith('.pdf')

# Function to check if URL is from arXiv
def is_arxiv_url(url):
    return "arxiv.org" in url

# Extract arXiv ID from URL
def extract_arxiv_id(url):
    # Match arXiv IDs in formats like arxiv.org/abs/1234.5678 or arxiv.org/pdf/1234.5678
    match = re.search(r'arxiv\.org/(abs|pdf)/(\d+\.\d{4,5})', url)
    if match:
        return match.group(2)
    return None

# Download arXiv PDF
def download_arxiv_pdf(arxiv_id, filename):
    try:
        search = arxiv.Search(id_list=[arxiv_id])
        result = next(search.results())
        response = requests.get(result.pdf_url, stream=True, timeout=10)
        response.raise_for_status()
        filepath = os.path.join(pdfs_folder, filename)
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Downloaded: {filepath}")
        return True
    except Exception as e:
        print(f"Error downloading arXiv PDF {arxiv_id}: {e}")
        return False

# Download general PDF
def download_pdf(url, index):
    try:
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
            filename = f"pdf_{index}.pdf"
            filepath = os.path.join(pdfs_folder, filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded: {filepath}")
            return True
    except Exception:
        pass
    return False

# Filter relevant links using Gemini API
def filter_relevant(link, query):
    prompt = f"Is this link relevant to algorithmic trading using Python textbooks or lecture notes? URL: {link}"
    try:
        response = model.generate_content(prompt, generation_config=genai.GenerationConfig(max_output_tokens=50))
        return "yes" in response.text.lower()
    except Exception as e:
        print(f"Error processing link {link} with Gemini: {e}")
        return False

# Unchanged functions: identify_popular_websites, web_search_agent, arxiv_search_agent
def identify_popular_websites(query):
    ddg = duckduckgo_search.DDGS()
    results = ddg.text(query, max_results=50)
    domains = {}
    for result in results:
        domain = urlparse(result["href"]).netloc
        domains[domain] = domains.get(domain, 0) + 1
    popular_domains = sorted(domains.items(), key=lambda x: x[1], reverse=True)[:10]
    return [domain for domain, _ in popular_domains]

def web_search_agent(query, popular_domains, max_results=100):
    ddg = duckduckgo_search.DDGS()
    results = ddg.text(query, max_results=max_results)
    links = []
    for result in results:
        link = result["href"]
        domain = urlparse(link).netloc
        if is_pdf(link) and (domain in popular_domains or len(links) < 50):
            links.append(link)
    return links

def arxiv_search_agent(query):
    search = arxiv.Search(query=query, max_results=50)
    links = []
    for result in search.results():
        links.append(result.pdf_url)
    return links

# Main download logic (with fixed arXiv handling)
def download_materials():
    downloaded_files = set()
    query_index = 0
    total_downloads = 0

    # Identify popular websites
    popular_domains = identify_popular_websites(base_query)
    print(f"Popular domains: {popular_domains}")

    while total_downloads < 50 and query_index < len(query_variants):
        query = query_variants[query_index]
        print(f"Searching with query: {query}")

        # Run web and arXiv searches
        web_links = web_search_agent(query, popular_domains)
        arxiv_links = arxiv_search_agent(query)
        all_links = web_links + arxiv_links

        # Filter relevant links
        relevant_links = [link for link in all_links if filter_relevant(link, query)]

        # Download PDFs
        for i, link in enumerate(relevant_links):
            if total_downloads >= 50:
                break
            link = link.strip()
            # Handle arXiv URLs
            if is_arxiv_url(link):
                arxiv_id = extract_arxiv_id(link)
                if arxiv_id:
                    filename = f"arxiv_{arxiv_id}.pdf"
                    filepath = os.path.join(pdfs_folder, filename)
                    if filepath not in downloaded_files:
                        if download_arxiv_pdf(arxiv_id, filename):
                            downloaded_files.add(filepath)
                            total_downloads += 1
                else:
                    # Fallback to general PDF download if arXiv ID extraction fails
                    filename = f"pdf_{total_downloads}_{i}.pdf"
                    filepath = os.path.join(pdfs_folder, filename)
                    if filepath not in downloaded_files:
                        if download_pdf(link, f"{total_downloads}_{i}"):
                            downloaded_files.add(filepath)
                            total_downloads += 1
            else:
                # General PDF download
                filename = f"pdf_{total_downloads}_{i}.pdf"
                filepath = os.path.join(pdfs_folder, filename)
                if filepath not in downloaded_files:
                    if download_pdf(link, f"{total_downloads}_{i}"):
                        downloaded_files.add(filepath)
                        total_downloads += 1

        print(f"Total downloads after query '{query}': {total_downloads}")
        query_index += 1

    if total_downloads < 50:
        print(f"Only {total_downloads} files downloaded. Try broader queries or more sources.")

# Run the script
if __name__ == "__main__":
    download_materials()
