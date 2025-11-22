"""
Document discovery and download module for budget amendment earmark tracking.

This module handles:
1. Discovery of amendment documents (Amendment Books, Sponsor Indexes)
2. PDF downloading with caching
3. Sponsor index parsing
4. Cache management for earmark data

Follows patterns established in fetchers.py and helpers.py.
"""

from datetime import datetime, timedelta
import json
from pathlib import Path
import re
from sys import stderr
from typing import Optional
import urllib.request


def get_earmark_cache_dir() -> Path:
    """
    Get earmark cache directory, creating if needed.
    
    Returns:
        Path to data/cache directory
    """
    cache_dir = Path(__file__).parent.parent / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_earmark_data_dir(fy_year: int) -> Path:
    """
    Get earmark data directory for final datasets.
    
    Args:
        fy_year: Fiscal year (e.g., 2026)
    
    Returns:
        Path to data/earmark/{fy_year} directory
    """
    data_dir = Path(__file__).parent.parent / "data" / "earmark" / str(fy_year)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def is_cache_fresh(cached_at: Optional[str], max_age_hours: int = 24) -> bool:
    """
    Check if cache timestamp is fresh.
    
    Args:
        cached_at: ISO format timestamp string
        max_age_hours: Maximum age in hours for cache to be considered fresh
    
    Returns:
        True if cache is fresh, False otherwise
    """
    if not cached_at:
        return False
    
    try:
        cache_time = datetime.fromisoformat(cached_at)
        age = datetime.now() - cache_time
        return age < timedelta(hours=max_age_hours)
    except (ValueError, TypeError):
        return False


def load_json_cache(cache_file: Path) -> Optional[dict]:
    """
    Load JSON cache file with error handling.
    
    Args:
        cache_file: Path to cache file
    
    Returns:
        Cached data dict or None on error
    """
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading cache {cache_file}: {e}", file=stderr)
        return None


def save_json_cache(cache_file: Path, data: dict) -> None:
    """
    Save data to JSON cache with timestamp.
    
    Args:
        cache_file: Path to cache file
        data: Dictionary to cache
    """
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    data['cached_at'] = datetime.now().isoformat()
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving cache {cache_file}: {e}", file=stderr)


def find_amendment_documents(
    fy_year: int, 
    chamber: Optional[str] = None
) -> dict:
    """
    Discover amendment documents for a fiscal year.
    
    Args:
        fy_year: Fiscal year (e.g., 2026)
        chamber: Optional filter ('House', 'Senate', or None for both)
    
    Returns:
        Dictionary containing:
        {
            'amendment_book': {'house': url, 'senate': url},
            'sponsor_index': {'house': url, 'senate': url},
            'amendment_detail_pages': [urls...],
            'discovered_at': iso_timestamp
        }
    """
    # Check cache first
    cache_file = get_earmark_cache_dir() / f"earmark_documents_{fy_year}.json"
    if cache_file.exists():
        cached_data = load_json_cache(cache_file)
        if cached_data and is_cache_fresh(
            cached_data.get('discovered_at'), 
            max_age_hours=24
        ):
            discovered = cached_data.get('discovered_at')
            print(f"Using cached document discovery from {discovered}")
            return cached_data
    
    # Scrape budget debate pages for PDF links
    print(f"  Discovering amendment documents for FY{fy_year}...")
    
    documents = {
        'amendment_book': {'house': None, 'senate': None},
        'sponsor_index': {'house': None, 'senate': None},
        'amendment_detail_pages': [],
        'discovered_at': datetime.now().isoformat()
    }
    
    # Try to scrape House debate page
    if not chamber or chamber == 'House':
        base_url = "https://malegislature.gov/Budget"
        house_url = f"{base_url}/FY{fy_year}/HouseDebate"
        house_docs = _scrape_budget_page(house_url)
        documents['amendment_book']['house'] = house_docs.get(  # type: ignore
            'amendment_book'
        )
        documents['sponsor_index']['house'] = house_docs.get(  # type: ignore
            'sponsor_index'
        )
    
    # Try to scrape Senate debate page
    if not chamber or chamber == 'Senate':
        base_url = "https://malegislature.gov/Budget"
        senate_url = f"{base_url}/FY{fy_year}/SenateDebate"
        senate_docs = _scrape_budget_page(senate_url)
        # type: ignore
        documents['amendment_book']['senate'] = senate_docs.get(
            'amendment_book'
        )
        # type: ignore
        documents['sponsor_index']['senate'] = senate_docs.get(
            'sponsor_index'
        )
    
    # Save to cache
    save_json_cache(cache_file, documents)
    
    return documents


def _scrape_budget_page(url: str) -> dict[str, Optional[str]]:
    """
    Scrape a budget debate page for amendment document links.
    
    Args:
        url: URL of the budget debate page
    
    Returns:
        Dictionary with 'amendment_book' and 'sponsor_index' URLs
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("[Earmarks] BeautifulSoup not available", file=stderr)
        return {}
    
    result: dict[str, Optional[str]] = {
        'amendment_book': None,
        'sponsor_index': None
    }
    
    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "stipend-tracker/1.0"}
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            html = response.read().decode('utf-8')
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find all links to PDFs
            for link in soup.find_all('a', href=True):
                href = str(link.get('href', ''))
                text = link.get_text().lower()
                
                # Look for amendment book
                if 'amendment' in text and 'book' in text and '.pdf' in href:
                    if not result['amendment_book']:
                        if href.startswith('http'):
                            result['amendment_book'] = href
                        else:
                            base = 'https://malegislature.gov'
                            result['amendment_book'] = base + href
                
                # Look for sponsor index
                if 'sponsor' in text and 'index' in text and '.pdf' in href:
                    if not result['sponsor_index']:
                        if href.startswith('http'):
                            result['sponsor_index'] = href
                        else:
                            base = 'https://malegislature.gov'
                            result['sponsor_index'] = base + href
        
        return result
        
    except Exception as e:
        print(f"[Earmarks] Error scraping {url}: {e}", file=stderr)
        return result


def download_pdf(url: str, output_path: Path, max_retries: int = 3) -> bool:
    """
    Download a PDF file with retry logic.
    
    Args:
        url: URL of the PDF to download
        output_path: Path where the PDF should be saved
        max_retries: Maximum number of retry attempts
    
    Returns:
        True if download succeeded, False otherwise
    """
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "stipend-tracker/1.0"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                content = resp.read()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(content)
                return True
        except Exception as e:
            if attempt < max_retries - 1:
                delay = 1.0 * (2 ** attempt)
                print(
                    f"[PDF Download] Error downloading {url}, "
                    f"retrying in {delay:.1f}s: {e}",
                    file=stderr
                )
                import time
                time.sleep(delay)
                continue
            print(f"[PDF Download] Failed to download {url}: {e}", file=stderr)
            return False
    return False


def download_documents(documents: dict, fy_year: int) -> dict:
    """
    Download PDFs with error handling and caching.
    
    Args:
        documents: Document URLs from find_amendment_documents()
        fy_year: Fiscal year for cache naming
    
    Returns:
        Dictionary mapping document keys to local file paths:
        {
            'house_amendment_book': Path,
            'senate_amendment_book': Path,
            'house_sponsor_index': Path,
            'senate_sponsor_index': Path
        }
    """
    pdfs = {}
    
    # Download House amendment book
    house_book_url = documents.get('amendment_book', {}).get('house')
    if house_book_url:
        cache_name = f"amendment_book_{fy_year}_house.pdf"
        cache_path = get_earmark_cache_dir() / cache_name
        if cache_path.exists():
            print(f"  Using cached: {cache_path.name}")
            pdfs['house_amendment_book'] = cache_path
        elif download_pdf(house_book_url, cache_path):
            print(f"  Downloaded: {cache_path.name}")
            pdfs['house_amendment_book'] = cache_path
    
    # Download Senate amendment book
    senate_book_url = documents.get('amendment_book', {}).get('senate')
    if senate_book_url:
        cache_name = f"amendment_book_{fy_year}_senate.pdf"
        cache_path = get_earmark_cache_dir() / cache_name
        if cache_path.exists():
            print(f"  Using cached: {cache_path.name}")
            pdfs['senate_amendment_book'] = cache_path
        elif download_pdf(senate_book_url, cache_path):
            print(f"  Downloaded: {cache_path.name}")
            pdfs['senate_amendment_book'] = cache_path
    
    # Download House sponsor index
    house_sponsor_url = documents.get('sponsor_index', {}).get('house')
    if house_sponsor_url:
        cache_name = f"sponsor_index_{fy_year}_house.pdf"
        cache_path = get_earmark_cache_dir() / cache_name
        if cache_path.exists():
            print(f"  Using cached: {cache_path.name}")
            pdfs['house_sponsor_index'] = cache_path
        elif download_pdf(house_sponsor_url, cache_path):
            print(f"  Downloaded: {cache_path.name}")
            pdfs['house_sponsor_index'] = cache_path
    
    # Download Senate sponsor index
    senate_sponsor_url = documents.get('sponsor_index', {}).get('senate')
    if senate_sponsor_url:
        cache_name = f"sponsor_index_{fy_year}_senate.pdf"
        cache_path = get_earmark_cache_dir() / cache_name
        if cache_path.exists():
            print(f"  Using cached: {cache_path.name}")
            pdfs['senate_sponsor_index'] = cache_path
        elif download_pdf(senate_sponsor_url, cache_path):
            print(f"  Downloaded: {cache_path.name}")
            pdfs['senate_sponsor_index'] = cache_path
    
    return pdfs


def parse_sponsor_index(
    pdf_path: Optional[Path],
    fy_year: int,
    chamber: str
) -> dict[str, list[str]]:
    """
    Parse Sponsor Index PDF to map amendment numbers to legislators.
    
    Args:
        pdf_path: Path to cached Sponsor Index PDF (or None if not available)
        fy_year: Fiscal year
        chamber: 'House' or 'Senate'
    
    Returns:
        Dictionary mapping amendment numbers to sponsor names:
        {
            'amendment_1': ['Representative Smith', 'Senator Jones'],
            'amendment_2': ['Representative Brown'],
            ...
        }
    """
    # Check if parsed data is cached
    cache_name = f"sponsor_index_parsed_{fy_year}_{chamber}.json"
    cache_file = get_earmark_cache_dir() / cache_name
    if cache_file.exists():
        cached = load_json_cache(cache_file)
        if cached:
            print(f"  Using cached sponsor index for {chamber}")
            # Handle both old and new cache formats
            if 'sponsors' in cached:
                return cached['sponsors']  # type: ignore
            return cached  # type: ignore
    
    # Check if PDF exists
    if not pdf_path or not pdf_path.exists():
        print(
            f"Sponsor index PDF not found for {chamber}, "
            "returning empty mapping",
            file=stderr
        )
        return {}
    
    # Try to import pdfplumber
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        print(
            "pdfplumber not installed, cannot parse sponsor index",
            file=stderr
        )
        return {}
    
    sponsor_mapping: dict[str, list[str]] = {}
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(
                f"  Parsing sponsor index: "
                f"{len(pdf.pages)} pages from {pdf_path.name}"
            )
            
            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    text = page.extract_text()
                    if not text:
                        continue
                    
                    lines = text.split('\n')
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Look for patterns like:
                        # "Amendment 123 - Representative Smith"
                        # "123 Smith, John"
                        # Try multiple patterns
                        
                        # Pattern 1: "Amendment XXX" followed by name
                        match = re.search(
                            r'amendment\s*#?\s*(\d+)[\s\-:]+(.+)',
                            line,
                            re.I
                        )
                        if match:
                            amend_num = match.group(1)
                            sponsor_name = match.group(2).strip()
                            key = f"amendment_{amend_num}"
                            if key not in sponsor_mapping:
                                sponsor_mapping[key] = []
                            sponsor_mapping[key].append(sponsor_name)
                            continue
                        
                        # Pattern 2: Number at start, then name
                        match = re.search(
                            r'^(\d+)[\s\-:,]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?'
                            r'\s+[A-Z][a-z]+)',
                            line
                        )
                        if match:
                            amend_num = match.group(1)
                            sponsor_name = match.group(2).strip()
                            key = f"amendment_{amend_num}"
                            if key not in sponsor_mapping:
                                sponsor_mapping[key] = []
                            sponsor_mapping[key].append(sponsor_name)
                
                except Exception as e:
                    print(
                        f"  Error parsing sponsor index page "
                        f"{page_num}: {e}",
                        file=stderr
                    )
                    continue
        
        msg = (
            f"  Extracted {len(sponsor_mapping)} "
            f"sponsor mappings from {chamber}"
        )
        print(msg)
        
    except Exception as e:
        print(
            f"Error opening sponsor index PDF {pdf_path}: {e}",
            file=stderr
        )
        return {}
    
    # Save to cache (wrap in dict for save_json_cache)
    if sponsor_mapping:
        cache_data = {'sponsors': sponsor_mapping}
        save_json_cache(cache_file, cache_data)
    
    return sponsor_mapping
