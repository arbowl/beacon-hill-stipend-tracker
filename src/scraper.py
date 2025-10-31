"""
HTML scraping module to extract vice chair information from committee pages.

The MA Legislature API doesn't expose vice chair data, so we scrape it from
the committee detail pages on malegislature.gov.
"""

from __future__ import annotations

import re
import time
import urllib.request
from typing import Optional
from sys import stderr

from bs4 import BeautifulSoup


def _fetch_html(url: str, max_retries: int = 3) -> Optional[str]:
    """
    Fetch HTML content from a URL with retry logic.

    Args:
        url: The URL to fetch
        max_retries: Maximum number of retry attempts

    Returns:
        HTML content as string, or None on failure
    """
    for attempt in range(max_retries):
        try:  # pylint: disable=broad-exception-caught
            req = urllib.request.Request(
                url, headers={"User-Agent": "stipend-tracker/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            if attempt < max_retries - 1:
                delay = 1.0 * (2 ** attempt)
                msg = (f"[Scraper] Error fetching {url}, "
                       f"retrying in {delay:.1f}s")
                print(f"{msg}: {e}", file=stderr)
                time.sleep(delay)
                continue
            print(f"[Scraper] Failed to fetch {url}: {e}", file=stderr)
            return None
    return None


def _parse_member_code_from_url(url: str) -> Optional[str]:
    """
    Extract member code from legislator profile URL.

    Examples:
        '/LegislativeMembers/ABC1' -> 'ABC1'
        '/Legislators/Profile/L_S1/194' -> 'L_S1'
    """
    if not url:
        return None
    # Try pattern for /LegislativeMembers/CODE
    match = re.search(r'/LegislativeMembers/([A-Z0-9_]+)', url, re.I)
    if match:
        return match.group(1)
    # Try pattern for /Legislators/Profile/CODE/GC
    match = re.search(r'/Legislators/Profile/([A-Z0-9_]+)/\d+', url, re.I)
    if match:
        return match.group(1)
    return None


def scrape_vice_chairs(
    base_url: str, gc_number: int, committee_code: str
) -> dict[str, Optional[str]]:
    """
    Scrape vice chair information from committee detail page.

    Args:
        base_url: Base URL (e.g., 'https://malegislature.gov')
        gc_number: General Court number (e.g., 194)
        committee_code: Committee code (e.g., 'H33', 'J10')

    Returns:
        Dictionary with keys:
        - house_vice_chair_code: Member code or None
        - senate_vice_chair_code: Member code or None
    """
    if BeautifulSoup is None:
        msg = ("[Scraper] BeautifulSoup not available, "
               "skipping vice chair scraping")
        print(msg, file=stderr)
        return {
            "house_vice_chair_code": None,
            "senate_vice_chair_code": None,
        }

    result: dict[str, Optional[str]] = {
        "house_vice_chair_code": None,
        "senate_vice_chair_code": None,
    }

    # Construct committee detail page URL
    url = f"{base_url}/Committees/Detail/{committee_code}/{gc_number}"

    try:
        html = _fetch_html(url)
        if not html:
            return result

        soup = BeautifulSoup(html, "html.parser")

        # Look for Senate Members section
        senate_section = soup.find("h2", string="Senate Members")
        if senate_section:
            senate_container = senate_section.find_next(
                "ul", class_="committeeMemberList"
            )
            if not senate_container:
                senate_container = senate_section.find_next("div")

            if senate_container:
                # Look for Vice Chair pattern in list items
                for li_elem in senate_container.find_all("li"):
                    # Check if this li contains "Vice Chair" text
                    li_text = li_elem.get_text(strip=True)
                    if "Vice" in li_text and "Chair" in li_text:
                        # Find the link within this li element
                        link = li_elem.find("a")
                        if link:
                            href = link.get("href", "")
                            member_code = _parse_member_code_from_url(href)
                            if member_code:
                                result["senate_vice_chair_code"] = member_code
                                break

        # Look for House Members section
        house_section = soup.find("h2", string="House Members")
        if house_section:
            house_container = house_section.find_next(
                "ul", class_="committeeMemberList"
            )
            if not house_container:
                house_container = house_section.find_next("div")

            if house_container:
                # Look for Vice Chair pattern in list items
                for li_elem in house_container.find_all("li"):
                    # Check if this li contains "Vice Chair" text
                    li_text = li_elem.get_text(strip=True)
                    if "Vice" in li_text and "Chair" in li_text:
                        # Find the link within this li element
                        link = li_elem.find("a")
                        if link:
                            href = link.get("href", "")
                            member_code = _parse_member_code_from_url(href)
                            if member_code:
                                result["house_vice_chair_code"] = member_code
                                break

        return result

    except Exception as e:  # pylint: disable=broad-exception-caught
        msg = f"[Scraper] Error scraping vice chairs for {committee_code}"
        print(f"{msg}: {e}", file=stderr)
        return result

