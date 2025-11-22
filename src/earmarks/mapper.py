"""
Earmark to legislator mapping module.

This module handles:
1. Mapping earmarks to legislators using sponsor index
2. Name normalization and matching
3. Handling ambiguous matches
4. Building earmark datasets grouped by member

Uses existing name normalization patterns from helpers.py and validate.py.
"""

from typing import Any, Optional
from difflib import SequenceMatcher

from src.helpers import normalize_legislator_name


def normalize_sponsor_name(name: str) -> str:
    """
    Normalize sponsor name from PDF for matching.
    
    Handles various formats:
    - "Smith, John" -> "john smith"
    - "Representative Smith" -> "smith"
    - "Sen. John Smith" -> "john smith"
    
    Args:
        name: Raw sponsor name from PDF
    
    Returns:
        Normalized name for matching
    """
    if not name:
        return ""
    
    # Use existing normalization
    normalized = normalize_legislator_name(name)
    
    # Handle "Last, First" format common in indexes
    if ',' in name and ',' not in normalized:
        # Split and reverse
        parts = [p.strip() for p in name.split(',', 1)]
        if len(parts) == 2:
            # "Smith, John" -> "John Smith"
            name = f"{parts[1]} {parts[0]}"
            normalized = normalize_legislator_name(name)
    
    return normalized


def calculate_name_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity score between two names.
    
    Args:
        name1: First name (normalized)
        name2: Second name (normalized)
    
    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not name1 or not name2:
        return 0.0
    
    # Direct match
    if name1 == name2:
        return 1.0
    
    # Check if one contains the other (for partial matches)
    if name1 in name2 or name2 in name1:
        return 0.9
    
    # Use sequence matcher for fuzzy matching
    return SequenceMatcher(None, name1, name2).ratio()


def find_member_by_name(
    sponsor_name: str,
    members: list[dict[str, Any]],
    chamber: Optional[str] = None,
    min_similarity: float = 0.7
) -> Optional[tuple[dict[str, Any], float, str]]:
    """
    Find member matching sponsor name with fallback strategies.
    
    Strategy:
    1. Try full name match with standard threshold (0.7)
    2. Fallback 1: Try last-name-only match with lower threshold (0.6)
    3. Fallback 2: Return None (caller assigns to UNKNOWN)
    
    Args:
        sponsor_name: Sponsor name from PDF
        members: List of member dictionaries from API
        chamber: Optional chamber filter ('House' or 'Senate')
        min_similarity: Minimum similarity score for match
    
    Returns:
        (member_dict, confidence, match_method) or None if no match
        match_method: 'full_name', 'last_name_only', or None
    """
    normalized_sponsor = normalize_sponsor_name(sponsor_name)
    
    if not normalized_sponsor:
        return None
    
    # Try full name match first
    best_match: Optional[dict[str, Any]] = None
    best_score = 0.0
    
    for member in members:
        # Filter by chamber if specified
        if chamber:
            member_branch = member.get('branch', '').lower()
            chamber_lower = chamber.lower()
            # Map chamber names
            if chamber_lower == 'house' and member_branch != 'house':
                continue
            if chamber_lower == 'senate' and member_branch != 'senate':
                continue
        
        # Normalize member name
        member_name = member.get('name', '')
        normalized_member = normalize_legislator_name(member_name)
        
        # Calculate similarity
        similarity = calculate_name_similarity(
            normalized_sponsor,
            normalized_member
        )
        
        if similarity > best_score:
            best_score = similarity
            best_match = member
    
    # Return if above threshold
    if best_score >= min_similarity and best_match:
        return best_match, best_score, 'full_name'
    
    # Fallback 1: Try last-name-only matching with lower threshold
    # Extract likely last name (last word, excluding suffixes)
    suffixes = {'jr', 'sr', 'ii', 'iii', 'iv', 'v', 'esq'}
    
    sponsor_parts = normalized_sponsor.split()
    if sponsor_parts:
        # Strip suffix if present
        sponsor_last = sponsor_parts[-1]
        if len(sponsor_parts) > 1 and sponsor_last in suffixes:
            sponsor_last = sponsor_parts[-2]
        
        last_name_best: Optional[dict[str, Any]] = None
        last_name_score = 0.0
        
        for member in members:
            # Try chamber filter first, but don't require it in fallback
            # (amendments can have cross-chamber sponsors)
            
            member_name = member.get('name', '')
            normalized_member = normalize_legislator_name(member_name)
            member_parts = normalized_member.split()
            
            if member_parts:
                # Strip suffix from member name too
                member_last = member_parts[-1]
                if len(member_parts) > 1 and member_last in suffixes:
                    member_last = member_parts[-2]
                
                # Compare last names
                similarity = calculate_name_similarity(
                    sponsor_last,
                    member_last
                )
                
                if similarity > last_name_score:
                    last_name_score = similarity
                    last_name_best = member
        
        # Accept last-name match with lower threshold (0.6)
        if last_name_score >= 0.6 and last_name_best:
            return last_name_best, last_name_score, 'last_name_only'
    
    # Fallback 2: No match found
    return None


def map_earmarks_to_members(
    earmarks: list[dict[str, Any]],
    members: list[dict[str, Any]],
    sponsor_index: dict[str, list[str]],
    use_llm: bool = False
) -> dict[str, list[dict[str, Any]]]:
    """
    Map earmarks to legislators.
    
    Args:
        earmarks: List of earmark dictionaries from classifier
        members: Member data from fetch_members()
        sponsor_index: Sponsor index mapping from parser
            {'amendment_1': ['Representative Smith'], ...}
        use_llm: Use LLM for ambiguous name matching (not yet implemented)
    
    Returns:
        Dictionary mapping member codes to earmarks:
        {
            'member_code': [
                {earmark1},
                {earmark2},
                ...
            ],
            ...
        }
    """
    earmarks_by_member: dict[str, list[dict[str, Any]]] = {}
    
    # Track mapping statistics
    stats = {
        'total_earmarks': len(earmarks),
        'mapped': 0,
        'unmapped': 0,
        'ambiguous': 0
    }
    
    for earmark in earmarks:
        amendment_num = earmark.get('amendment_number', '')
        chamber = earmark.get('chamber', '')
        
        if not amendment_num:
            stats['unmapped'] += 1
            continue
        
        # Get sponsors from index or directly from earmark
        key = f"amendment_{amendment_num}"
        sponsor_names = sponsor_index.get(key, [])
        
        # If no sponsor index, try primary_sponsor field from earmark
        if not sponsor_names:
            primary_sponsor = earmark.get('primary_sponsor')
            if primary_sponsor:
                sponsor_names = [primary_sponsor]
        
        if not sponsor_names:
            # No sponsor found anywhere
            stats['unmapped'] += 1
            # Add to unmatched list for reference
            if 'UNMATCHED' not in earmarks_by_member:
                earmarks_by_member['UNMATCHED'] = []
            earmark_copy = earmark.copy()
            earmark_copy['mapping_status'] = 'no_sponsor_found'
            earmarks_by_member['UNMATCHED'].append(earmark_copy)
            continue
        
        # Try to match each sponsor to a member
        matched = False
        for sponsor_name in sponsor_names:
            result = find_member_by_name(
                sponsor_name,
                members,
                chamber=chamber,
                min_similarity=0.7
            )
            
            if result:
                member, confidence, match_method = result
                member_code = member.get('member_code', '')
                
                if member_code:
                    # Add earmark to member's list
                    if member_code not in earmarks_by_member:
                        earmarks_by_member[member_code] = []
                    
                    # Add mapping metadata to earmark
                    earmark_copy = earmark.copy()
                    earmark_copy['mapping_metadata'] = {
                        'sponsor_name': sponsor_name,
                        'matched_member': member.get('name'),
                        'member_code': member_code,
                        'confidence': confidence,
                        'match_method': match_method,
                        'chamber': chamber
                    }
                    
                    earmarks_by_member[member_code].append(earmark_copy)
                    matched = True
                    stats['mapped'] += 1
                    
                    # Track fallback usage
                    if match_method == 'last_name_only':
                        stats['last_name_fallback'] = (
                            stats.get('last_name_fallback', 0) + 1
                        )
                    
                    break  # Found a match, move to next earmark
        
        if not matched:
            # Could not match any sponsor to a member
            stats['unmapped'] += 1
            if 'UNKNOWN' not in earmarks_by_member:
                earmarks_by_member['UNKNOWN'] = []
            earmark_copy = earmark.copy()
            earmark_copy['mapping_status'] = 'no_member_match'
            earmark_copy['attempted_sponsors'] = sponsor_names
            earmarks_by_member['UNKNOWN'].append(earmark_copy)
    
    # Print mapping statistics
    print("\n[Earmark Mapping Statistics]")
    print(f"  Total earmarks: {stats['total_earmarks']}")
    print(f"  Successfully mapped: {stats['mapped']}")
    print(f"  Unmapped: {stats['unmapped']}")
    
    if 'UNMATCHED' in earmarks_by_member:
        unmatched_count = len(earmarks_by_member['UNMATCHED'])
        print(f"  Unmatched earmarks: {unmatched_count}")
    
    # Remove UNMATCHED from return if empty
    if 'UNMATCHED' in earmarks_by_member:
        if not earmarks_by_member['UNMATCHED']:
            del earmarks_by_member['UNMATCHED']
    
    return earmarks_by_member


def aggregate_member_earmarks(
    earmarks_by_member: dict[str, list[dict[str, Any]]],
    members: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Aggregate earmark statistics per member.
    
    Args:
        earmarks_by_member: Earmarks grouped by member code
        members: Member data for enrichment
    
    Returns:
        List of member summaries with earmark totals:
        [
            {
                'member_code': str,
                'name': str,
                'chamber': str,
                'district': str,
                'party': str,
                'earmark_count': int,
                'total_earmark_dollars': float,
                'average_earmark_amount': float,
                'largest_earmark': float,
                'earmarks': [list of earmarks]
            },
            ...
        ]
    """
    # Create member lookup
    member_lookup = {
        m.get('member_code'): m for m in members
        if m.get('member_code')
    }
    
    summaries = []
    
    for member_code, member_earmarks in earmarks_by_member.items():
        if member_code == 'UNKNOWN':
            # Skip unknown sponsors for per-member aggregation
            continue
        
        # Get member info
        member = member_lookup.get(member_code, {})
        
        # Calculate statistics
        amounts = [
            e.get('amount', 0)
            for e in member_earmarks
            if e.get('amount') is not None
        ]
        
        total_dollars = sum(amounts) if amounts else 0.0
        avg_dollars = total_dollars / len(amounts) if amounts else 0.0
        max_dollars = max(amounts) if amounts else 0.0
        
        summary = {
            'member_code': member_code,
            'name': member.get('name', 'Unknown'),
            'chamber': member.get('branch', 'Unknown'),
            'district': member.get('district', 'Unknown'),
            'party': member.get('party', 'Unknown'),
            'earmark_count': len(member_earmarks),
            'total_earmark_dollars': total_dollars,
            'average_earmark_amount': avg_dollars,
            'largest_earmark': max_dollars,
            'earmarks': member_earmarks
        }
        
        summaries.append(summary)
    
    # Sort by total dollars descending
    summaries.sort(
        key=lambda x: x['total_earmark_dollars'],
        reverse=True
    )
    
    return summaries
