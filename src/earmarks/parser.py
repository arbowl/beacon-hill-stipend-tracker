"""
PDF parsing module for budget amendment documents.

This module handles:
1. Parsing Amendment Book PDFs to extract amendment data
2. Pattern matching for amendment numbers, amounts, line items
3. Caching parsed data to avoid expensive re-parsing
4. Error handling for malformed PDFs

Uses pdfplumber for PDF text extraction.
"""

from pathlib import Path
import json
import re
from sys import stderr
from typing import Any, Optional

try:
    import pdfplumber  # type: ignore
except ImportError:
    pdfplumber = None  # type: ignore
    print(
        "Warning: pdfplumber not installed. "
        "PDF parsing will not be available.",
        file=stderr
    )

from src.earmarks.fetchers import get_earmark_cache_dir, load_json_cache


def extract_dollar_amount(text: str) -> Optional[float]:
    """
    Extract dollar amount from text using various patterns.
    
    Args:
        text: Text to search for dollar amounts
    
    Returns:
        Float amount or None if not found
    
    Examples:
        "$1,000,000" -> 1000000.0
        "$50K" -> 50000.0
        "1.5M" -> 1500000.0
    """
    if not text:
        return None
    
    # Pattern 1: K suffix: $50K or 50K (check this first!)
    # Use word boundary to avoid matching "make", "kind", etc.
    match = re.search(r'\$?\s*([\d,]+(?:\.\d+)?)\s*K\b', text, re.I)
    if match:
        amount_str = match.group(1).replace(',', '')
        try:
            return float(amount_str) * 1000
        except ValueError:
            pass
    
    # Pattern 2: M suffix: $1.5M or 1.5M
    # Use word boundary to avoid matching "must", "million", etc.
    match = re.search(r'\$?\s*([\d,]+(?:\.\d+)?)\s*M\b', text, re.I)
    if match:
        amount_str = match.group(1).replace(',', '')
        try:
            return float(amount_str) * 1000000
        except ValueError:
            pass
    
    # Pattern 3: Standard dollar format: $1,000,000
    match = re.search(r'\$\s*([\d,]+(?:\.\d{2})?)', text)
    if match:
        amount_str = match.group(1).replace(',', '')
        try:
            return float(amount_str)
        except ValueError:
            pass
    
    # Pattern 4: Plain number (must be >= 1000 to avoid false positives)
    match = re.search(r'\b([\d,]+)\b', text)
    if match:
        amount_str = match.group(1).replace(',', '')
        try:
            amount = float(amount_str)
            if amount >= 1000:
                return amount
        except ValueError:
            pass
    
    return None


def extract_line_item(text: str) -> Optional[str]:
    """
    Extract line item code from text.
    
    Args:
        text: Text to search for line item codes
    
    Returns:
        Line item code or None if not found
    
    Examples:
        "Line item 7000-1234" -> "7000-1234"
        "Item 1234-5678" -> "1234-5678"
    """
    if not text:
        return None
    
    # Pattern: 4-digit code, dash, 4-digit code (e.g., 7000-1234)
    match = re.search(r'\b(\d{4}-\d{4})\b', text)
    if match:
        return match.group(1)
    
    return None


def extract_amendment_number(text: str) -> Optional[str]:
    """
    Extract amendment number from text.
    
    Args:
        text: Text to search for amendment numbers
    
    Returns:
        Amendment number or None if not found
    
    Examples:
        "Amendment 123" -> "123"
        "123 Some Title" -> "123"
        "47 Massachusetts Cultural Council" -> "47"
    """
    if not text:
        return None
    
    # Pattern 1: Just a number at the start of a line (MA format)
    # Must be 1-4 digits followed by whitespace or title
    match = re.match(r'^(\d{1,4})\s+[A-Z]', text)
    if match:
        return match.group(1)
    
    # Pattern 2: "Amendment" followed by optional # and number
    match = re.search(r'amendment\s*#?\s*(\d+)', text, re.I)
    if match:
        return match.group(1)
    
    return None


def extract_location(text: str) -> Optional[str]:
    """
    Extract city/town/location from earmark text.
    
    Args:
        text: Text to search for locations
    
    Returns:
        Location string or None if not found
    
    Examples:
        "for the city of Boston" -> "Boston"
        "in Attleboro" -> "Attleboro"
        "throughout Worcester County" -> "Worcester County"
    """
    if not text:
        return None
    
    # Common location patterns in earmarks
    patterns = [
        r'\bin\s+(?:the\s+)?(?:city\s+of\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        r'\bfor\s+(?:the\s+)?(?:city\s+of\s+|town\s+of\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        r'\bthroughout\s+([A-Z][a-z]+(?:\s+(?:County|Region|District))?)',
        r'\bat\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        r'\blocated\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        # County patterns
        r'\b([A-Z][a-z]+)\s+County\b',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            location = match.group(1).strip()
            # Filter out common false positives
            false_positives = {
                'Massachusetts', 'Section', 'Item', 'Line', 'The', 'This',
                'General', 'Court', 'House', 'Senate', 'Amendment'
            }
            if location not in false_positives:
                return location
    
    return None


def extract_organization_or_recipient(text: str) -> Optional[str]:
    """
    Extract organization, recipient, or project name from earmark text.
    
    Args:
        text: Text to search for organizations/recipients
    
    Returns:
        Organization/recipient string or None if not found
    
    Examples:
        "for the Boys and Girls Club" -> "Boys and Girls Club"
        "to support the Attleboro Youth Center" -> "Attleboro Youth Center"
        "for an inclusive playground project" -> "inclusive playground project"
    """
    if not text:
        return None
    
    # Patterns for organizations and projects
    patterns = [
        # "for [the] Organization Name"
        r'\bfor\s+(?:the\s+)?([A-Z][A-Za-z\s&\-]+(?:Center|Club|Council|Foundation|Association|Project|Program|Initiative))',
        # "to [the] Organization Name"
        r'\bto\s+(?:the\s+)?([A-Z][A-Za-z\s&\-]+(?:Center|Club|Council|Foundation|Association|Project|Program|Initiative))',
        # "support [the] Organization Name"
        r'\bsupport\s+(?:the\s+)?([A-Z][A-Za-z\s&\-]+(?:Center|Club|Council|Foundation|Association|Project|Program|Initiative))',
        # Project descriptions
        r'\bfor\s+(?:a|an)\s+([a-z][a-z\s\-]+(?:project|program|initiative|facility|center))',
        r'\bto\s+(?:construct|build|establish|create|fund)\s+(?:a|an)?\s*([a-z][a-z\s\-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            org = match.group(1).strip()
            # Clean up and validate
            if len(org) > 5 and len(org) < 100:  # Reasonable length
                return org
    
    return None


def parse_amendment_book(
    pdf_path: Path,
    fy_year: int,
    chamber: str
) -> list[dict[str, Any]]:
    """
    Parse Amendment Book PDF and extract amendments.
    
    Args:
        pdf_path: Path to cached PDF file
        fy_year: Fiscal year for metadata
        chamber: 'House' or 'Senate'
    
    Returns:
        List of amendment dictionaries with:
        {
            'amendment_number': str,
            'amount': Optional[float],
            'line_item': Optional[str],
            'description': str,
            'raw_text': str,
            'page_number': int,
            'fy_year': int,
            'chamber': str
        }
    """
    # Check if parsed data is cached
    cache_name = f"amendments_parsed_{fy_year}_{chamber}.json"
    cache_file = get_earmark_cache_dir() / cache_name
    if cache_file.exists():
        cached = load_json_cache(cache_file)
        if cached and isinstance(cached, list):
            print(f"  Using cached parsed amendments for {chamber}")
            return cached  # type: ignore
    
    # Check if pdfplumber is available
    if pdfplumber is None:
        msg = (
            f"Cannot parse {pdf_path}: pdfplumber not installed. "
            "Install with: pip install pdfplumber"
        )
        print(msg, file=stderr)
        return []
    
    # Check if PDF exists
    if not pdf_path or not pdf_path.exists():
        print(f"PDF not found: {pdf_path}", file=stderr)
        return []
    
    amendments: list[dict[str, Any]] = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            msg = f"  Parsing {len(pdf.pages)} pages from {pdf_path.name}"
            print(msg)
            
            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    text = page.extract_text()
                    if not text:
                        continue
                    
                    # Split into lines for processing
                    lines = text.split('\n')
                    
                    # Simple heuristic: look for amendment markers
                    current_amendment: dict[str, Any] | None = None
                    current_text_lines: list[str] = []
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Check if this line starts a new amendment
                        amend_num = extract_amendment_number(line)
                        if amend_num:
                            # Save previous amendment if exists
                            if current_amendment:
                                # type: ignore
                                current_amendment['raw_text'] = (
                                    '\n'.join(current_text_lines)
                                )
                                # Create description from first few lines
                                desc_text = ' '.join(current_text_lines[:5])
                                if len(desc_text) > 200:
                                    desc = desc_text[:200] + '...'
                                else:
                                    desc = desc_text
                                current_amendment['description'] = desc
                                amendments.append(current_amendment)
                            
                            # Start new amendment
                            current_amendment = {
                                'amendment_number': amend_num,
                                'amount': None,
                                'line_item': None,
                                'description': '',
                                'primary_sponsor': None,
                                'location': None,
                                'organization_or_recipient': None,
                                'raw_text': '',
                                'page_number': page_num,
                                'fy_year': fy_year,
                                'chamber': chamber
                            }
                            current_text_lines = [line]
                        elif current_amendment is not None:
                            # Continue accumulating text
                            current_text_lines.append(line)
                            
                            # Try to extract amount if not yet found
                            if current_amendment['amount'] is None:
                                amount = extract_dollar_amount(line)
                                if amount:
                                    current_amendment['amount'] = amount
                            
                            # Try to extract line item if not yet found
                            if current_amendment['line_item'] is None:
                                line_item = extract_line_item(line)
                                if line_item:
                                    current_amendment['line_item'] = (
                                        line_item
                                    )
                            
                            # Try to extract primary sponsor if not yet found
                            if current_amendment['primary_sponsor'] is None:
                                sponsor_match = re.search(
                                    r'Primary Sponsor:\s*(.+)',
                                    line,
                                    re.I
                                )
                                if sponsor_match:
                                    sponsor = sponsor_match.group(1).strip()
                                    # Remove line item if it appears after name
                                    sponsor = re.sub(r'\s+\d{4}$', '', sponsor)
                                    current_amendment['primary_sponsor'] = (
                                        sponsor
                                    )
                            
                            # Try to extract location if not yet found
                            if current_amendment.get('location') is None:
                                location = extract_location(line)
                                if location:
                                    current_amendment['location'] = location
                            
                            # Try to extract organization if not yet found
                            if current_amendment.get('organization_or_recipient') is None:
                                org = extract_organization_or_recipient(line)
                                if org:
                                    current_amendment['organization_or_recipient'] = org
                    
                    # Save last amendment on page
                    if current_amendment is not None:
                        current_amendment['raw_text'] = (
                            '\n'.join(current_text_lines)
                        )
                        # Create description from first few lines
                        desc_text = ' '.join(current_text_lines[:5])
                        if len(desc_text) > 200:
                            desc = desc_text[:200] + '...'
                        else:
                            desc = desc_text
                        current_amendment['description'] = desc
                        amendments.append(current_amendment)
                
                except Exception as e:
                    msg = f"  Error parsing page {page_num}: {e}"
                    print(msg, file=stderr)
                    continue
        
        print(f"  Extracted {len(amendments)} amendments from {chamber}")
        
    except Exception as e:
        print(f"Error opening PDF {pdf_path}: {e}", file=stderr)
        return []
    
    # Save to cache
    if amendments:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(amendments, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving cache {cache_file}: {e}", file=stderr)
    
    return amendments
