import sys
import subprocess

def ensure_package(pkg):
    try:
        __import__(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

for pkg in ["requests", "pandas", "scholarly"]:
    ensure_package(pkg)

import requests
import pandas as pd
from scholarly import scholarly

Search_query = "Battery SoC and SoH estimation using deep learning"

# Publication type flags
journals = True
conference = False
book_chapter = False
all_types = True  # If True, ignore other flags and include all

def search_openalex(query, per_page=100, max_records=1000):
    base_url = "https://api.openalex.org/works"
    params = {
        "per_page": per_page,
        "sort": "relevance_score:desc",
        "filter": f"title_and_abstract.search:{query}",
        "cursor": "*"
    }
    records = []
    total_fetched = 0

    while True:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        for result in results:
            if not all_types:
                primary_location = result.get("primary_location") or {}
                source = primary_location.get("source") or {}
                source_type = source.get("type", "")
                work_type = result.get("type", "")
                # Filtering logic
                if journals and source_type == "journal":
                    pass
                elif conference and work_type == "proceedings-article":
                    pass
                elif book_chapter and work_type == "book-chapter":
                    pass
                else:
                    continue
            title = result.get("title", "")
            abstract = result.get("abstract_inverted_index", "")
            # Extract year from OpenAlex metadata if available
            year = result.get("publication_year", "")
            citations = result.get("cited_by_count", "")
            # OpenAlex returns abstract as an inverted index; reconstruct if present
            if isinstance(abstract, dict):
                abstract_text = " ".join([word for word, _ in sorted(abstract.items(), key=lambda x: min(x[1]))])
            else:
                abstract_text = ""
            records.append({
                "title": title,
                "abstract": abstract_text,
                "year": str(year),
                "citations": citations
            })
        total_fetched += len(results)
        print(f"Fetched {total_fetched} records so far...")
        # Check if there is a next page
        next_cursor = data.get("meta", {}).get("next_cursor")
        if not next_cursor or len(results) == 0 or total_fetched >= max_records:
            break
        params["cursor"] = next_cursor
    return pd.DataFrame(records[:max_records])

def search_google_scholar(query, max_results=100):
    records = []
    search = scholarly.search_pubs(query)
    for i, result in enumerate(search):
        if i >= max_results:
            break
        bib = result.get('bib', {})
        pub_type = bib.get('pub_type', '').lower()
        venue = bib.get('venue', '').lower()
        # Filtering logic
        include = False
        if all_types:
            include = True
        else:
            if journals and ('journal' in pub_type or 'journal' in venue):
                include = True
            elif conference and ('conference' in pub_type or 'conference' in venue):
                include = True
            elif book_chapter and ('chapter' in pub_type or 'chapter' in venue or 'book' in pub_type or 'book' in venue):
                include = True
        if not include:
            continue
        title = bib.get('title', '')
        abstract = bib.get('abstract', '')
        year = bib.get('pub_year', '')
        # Try to get citations from both bib and top-level result
        citations = bib.get('citedby', None)
        if citations is None:
            citations = result.get('num_citations', None)
        if citations is None:
            citations = 0
        records.append({
            "title": title,
            "abstract": abstract,
            "year": str(year),
            "citations": citations
        })
    return pd.DataFrame(records)

# Fetch data from OpenAlex API
df_openalex = search_openalex(Search_query, per_page=100, max_records=1000)
print(f"OpenAlex results: {len(df_openalex)}")

# Fetch data from Google Scholar
df_scholar = search_google_scholar(Search_query, max_results=100)
print(f"Google Scholar results: {len(df_scholar)}")

# Combine and remove duplicates based on title (case-insensitive)
df_combined = pd.concat([df_openalex, df_scholar], ignore_index=True)
df_combined['title_lower'] = df_combined['title'].str.lower().str.strip()
df_unique = df_combined.drop_duplicates(subset=['title_lower']).drop(columns=['title_lower'])

# Ensure 'year' column is present and fallback to extracting from title if missing
df_unique['year'] = df_unique['year'].replace('', pd.NA)
missing_years = df_unique['year'].isna()
df_unique.loc[missing_years, 'year'] = df_unique.loc[missing_years, 'title'].str.extract(r'(\d{4})', expand=False)

# Ensure 'citations' column exists and fill missing with 0
df_unique['citations'] = pd.to_numeric(df_unique.get('citations', 0), errors='coerce').fillna(0).astype(int)

# Filter based on year
df_filtered = df_unique[df_unique['year'] >= '2022']
print(df_filtered.head())

# Save filtered DataFrame to CSV
df_filtered.to_csv("filtered_results.csv", index=False)
print("Filtered results saved to 'filtered_results.csv'")
