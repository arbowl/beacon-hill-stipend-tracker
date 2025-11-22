"""
Earmark classification module for budget amendments.

This module handles:
1. Deterministic classification of amendments as earmarks
2. Pattern matching for geographic/organization/project specificity
3. Confidence scoring for classifications
4. Optional LLM integration for ambiguous cases

Classification criteria:
- Geographic specificity (mentions city/town/district)
- Organization specificity (names specific entity)
- Project specificity (specific project description)
- Amount thresholds ($5k-$1M+ typical range)
"""

import re
import math
from typing import Any, Optional

from src.earmarks.llm import LocalLLMProcessor


# MA-specific earmark boilerplate phrases (strongest signals)
EARMARK_PHRASES = [
    r'(?i)\bprovided(?:,)?\s+that\b',
    r'(?i)\bprovided\s+further(?:,)?\s+that\b',
    r'(?i)\bshall\s+be\s+expended\s+for\b',
    r'(?i)\bshall\s+be\s+provided\s+to\b',
    r'(?i)\bnot\s+less\s+than\s+\$?[\d,]+',
    r'(?i)\bup\s+to\s+\$?[\d,]+',
    r'(?i)\bfor\s+the\s+purpose\s+of\b',
    r'(?i)\bin\s+the\s+(?:city|town)\s+of\b',
    r'(?i)\bfor\s+(?:the\s+)?benefit\s+of\b',
]

# Expanded MA localities - municipalities, neighborhoods, regions
MA_LOCALITIES = {
    # Major cities
    'boston', 'worcester', 'springfield', 'cambridge', 'lowell',
    'brockton', 'quincy', 'lynn', 'new bedford', 'fall river',
    'newton', 'lawrence', 'somerville', 'framingham', 'haverhill',
    'waltham', 'malden', 'brookline', 'plymouth', 'medford',
    'taunton', 'chicopee', 'weymouth', 'revere', 'peabody',
    'methuen', 'barnstable', 'pittsfield', 'arlington', 'everett',
    'salem', 'westfield', 'leominster', 'fitchburg', 'beverly',
    'holyoke', 'marlborough', 'woburn', 'chelsea', 'braintree',
    'amherst', 'shrewsbury', 'dartmouth', 'billerica', 'natick',
    'randolph', 'northampton', 'attleboro', 'agawam', 'west springfield',
    # More municipalities
    'gloucester', 'danvers', 'andover', 'watertown', 'burlington',
    'lexington', 'milton', 'needham', 'dedham', 'wellesley',
    'belmont', 'reading', 'wakefield', 'stoneham', 'winchester',
    'melrose', 'concord', 'norwood', 'norfolk', 'rockland',
    'holbrook', 'abington', 'whitman', 'hanover', 'hingham',
    'cohasset', 'scituate', 'marshfield', 'duxbury', 'kingston',
    # Regional identifiers
    'cape cod', 'south coast', 'north shore', 'south shore',
    'merrimack valley', 'pioneer valley', 'berkshires',
    'metro boston', 'greater boston',
    # Neighborhoods/areas
    'dorchester', 'roxbury', 'jamaica plain', 'south end',
    'back bay', 'charlestown', 'east boston', 'allston',
    'brighton', 'west roxbury', 'mattapan', 'roslindale',
    'hyde park',
}


# Keywords and patterns for organizational specificity
ORGANIZATION_KEYWORDS = {
    'foundation', 'association', 'society', 'institute', 'center',
    'council', 'organization', 'commission', 'authority', 'trust',
    'coalition', 'collaborative', 'partnership', 'corporation',
    'company', 'university', 'college', 'school', 'hospital',
    'museum', 'library', 'church', 'temple', 'synagogue',
    # Legal suffixes
    'inc', 'corp', 'llc', 'ltd', 'dba',
    # Common MA nonprofits
    'ymca', 'ywca', 'boys and girls club', 'food pantry',
    'community health center', 'housing authority',
    'united way', 'community development corporation', 'cdc',
}

# Organizational patterns (regex)
ORGANIZATION_PATTERNS = [
    r'(?i)\bfriends\s+of\s+\w+',
    r'(?i)\bboys\s+(?:and|&)\s+girls\s+club',
    r'(?i)\bcommunity\s+(?:health\s+)?center',
    r'(?i)\bhousing\s+authority\b',
]


# Keywords indicating project specificity
PROJECT_KEYWORDS = {
    'construction', 'renovation', 'repair', 'upgrade', 'improvement',
    'building', 'facility', 'infrastructure', 'project', 'program',
    'initiative', 'development', 'installation', 'acquisition',
    'purchase', 'equipment', 'system', 'maintenance', 'expansion',
    # Planning/design
    'design', 'feasibility', 'planning', 'engineering', 'permitting',
    'pilot', 'technical assistance', 'training', 'capacity',
    'outreach', 'programming', 'after-school', 'violence prevention',
    'shelter', 'workforce', 'build-out', 'fit-out',
}


# Keywords suggesting broad/statewide programs (weak anti-earmark signals)
ROUTINE_KEYWORDS = {
    'statewide', 'subject to appropriation', 'for grants to municipalities',
    'administered by', 'operating expenses', 'general fund',
    'personnel', 'salaries', 'benefits', 'overhead',
    'contingency', 'reserve',
}


def normalize_text(text: str) -> str:
    """
    Normalize text for better pattern matching.
    
    Handles:
    - Hyphenated line breaks (renova-\\ntion -> renovation)
    - Excessive whitespace
    - Unicode normalization
    
    Args:
        text: Raw text
    
    Returns:
        Normalized text
    """
    if not text:
        return ""
    
    # Remove hyphenated line breaks
    text = re.sub(r'-\s*\n\s*', '', text)
    
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Normalize common unicode chars
    text = text.replace('–', '-').replace('—', '-')
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace(''', "'").replace(''', "'")
    
    return text.strip()


def match_earmark_boilerplate(text: str) -> tuple[bool, float, list[str]]:
    """
    Check for MA-specific earmark boilerplate phrases.
    
    These phrases are strong positive signals that something is an earmark.
    
    Args:
        text: Text to analyze
    
    Returns:
        (has_boilerplate, confidence, matched_phrases)
    """
    matches = []
    
    for pattern in EARMARK_PHRASES:
        for match in re.finditer(pattern, text):
            matches.append(match.group(0))
    
    if not matches:
        return False, 0.0, []
    
    # Each phrase is a strong signal; cap confidence
    confidence = min(0.95, 0.6 + 0.15 * len(matches))
    
    return True, confidence, matches


def has_geographic_specificity(text: str) -> tuple[bool, float]:
    """
    Check if text mentions specific geographic location.
    
    Args:
        text: Text to analyze
    
    Returns:
        (has_specificity: bool, confidence: float)
    """
    if not text:
        return False, 0.0
    
    text_lower = text.lower()
    
    # Check for MA city/town names
    for locality in MA_LOCALITIES:
        if re.search(r'\b' + re.escape(locality) + r'\b', text_lower):
            return True, 0.9
    
    # Check for generic geographic indicators
    geo_patterns = [
        r'\bcity\s+of\s+\w+',
        r'\btown\s+of\s+\w+',
        r'\b\w+\s+county\b',
        r'\bdistrict\s+\d+',
        r'\b\d+(st|nd|rd|th)\s+district\b'
    ]
    
    for pattern in geo_patterns:
        if re.search(pattern, text_lower):
            return True, 0.8
    
    return False, 0.0


def has_organization_specificity(text: str) -> tuple[bool, float]:
    """
    Check if text names specific organization.
    
    Args:
        text: Text to analyze
    
    Returns:
        (has_specificity: bool, confidence: float)
    """
    if not text:
        return False, 0.0
    
    text_lower = text.lower()
    
    # Check for organization keywords
    matches = 0
    for keyword in ORGANIZATION_KEYWORDS:
        if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
            matches += 1
    
    if matches >= 2:
        return True, 0.9
    elif matches == 1:
        return True, 0.7
    
    # Check for capitalized proper names (likely organizations)
    # Pattern: Capital word followed by capital word(s)
    proper_name_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b'
    proper_names = re.findall(proper_name_pattern, text)
    if len(proper_names) >= 2:
        return True, 0.6
    
    return False, 0.0


def has_project_specificity(text: str) -> tuple[bool, float]:
    """
    Check if text describes specific project.
    
    Args:
        text: Text to analyze
    
    Returns:
        (has_specificity: bool, confidence: float)
    """
    if not text:
        return False, 0.0
    
    text_lower = text.lower()
    
    # Check for project keywords
    matches = 0
    for keyword in PROJECT_KEYWORDS:
        if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
            matches += 1
    
    if matches >= 2:
        return True, 0.8
    elif matches == 1:
        return True, 0.6
    
    return False, 0.0


def has_routine_indicators(text: str) -> tuple[bool, float]:
    """
    Check if text has indicators of routine budget item.
    
    Args:
        text: Text to analyze
    
    Returns:
        (has_indicators: bool, confidence: float)
    """
    if not text:
        return False, 0.0
    
    text_lower = text.lower()
    
    # Check for routine keywords
    matches = 0
    for keyword in ROUTINE_KEYWORDS:
        if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
            matches += 1
    
    if matches >= 3:
        return True, 0.9
    elif matches >= 2:
        return True, 0.7
    elif matches == 1:
        return True, 0.5
    
    return False, 0.0


def is_amount_in_earmark_range(amount: Optional[float]) -> tuple[bool, float]:
    """
    Check if amount is in typical earmark range.
    
    Args:
        amount: Dollar amount
    
    Returns:
        (in_range: bool, confidence: float)
    """
    if amount is None:
        return False, 0.0
    
    # Typical earmark range: $5,000 to $3,000,000
    if 5000 <= amount <= 3000000:
        # More confident for amounts in sweet spot ($25k-$1M)
        if 25000 <= amount <= 1000000:
            return True, 0.9
        # $1M-$3M range: possible but less confident
        elif 1000000 < amount <= 3000000:
            return True, 0.6
        return True, 0.7
    
    # Very small amounts unlikely to be earmarks
    if amount < 5000:
        return False, 0.8
    
    # Very large amounts are policy changes, not earmarks
    if amount > 3000000:
        return False, 0.9
    
    return True, 0.5


def deterministic_classify(amendment: dict[str, Any]) -> dict[str, Any]:
    """
    Deterministic earmark classification using pattern matching.
    
    Args:
        amendment: Amendment dictionary from parser with keys:
            - description: str
            - raw_text: str
            - amount: Optional[float]
            - line_item: Optional[str]
    
    Returns:
        Classification result dictionary:
        {
            'is_earmark': bool,
            'confidence': float,
            'geographic_specific': bool,
            'organization_specific': bool,
            'project_specific': bool,
            'routine_indicators': bool,
            'amount_in_range': bool,
            'reasoning': str
        }
    """
    # Get text to analyze (prefer raw_text, fallback to description)
    text = amendment.get('raw_text') or amendment.get('description', '')
    amount = amendment.get('amount')
    
    # Normalize text for better matching
    text = normalize_text(text)
    
    # Check for earmark boilerplate first (strongest signal)
    has_boiler, boiler_conf, boiler_matches = match_earmark_boilerplate(text)
    
    # Check various criteria
    geo_specific, geo_conf = has_geographic_specificity(text)
    org_specific, org_conf = has_organization_specificity(text)
    proj_specific, proj_conf = has_project_specificity(text)
    routine, routine_conf = has_routine_indicators(text)
    amount_ok, amount_conf = is_amount_in_earmark_range(amount)
    
    # Weighted scoring approach (no hard caps)
    signals = []
    score = 0.0
    
    # Boilerplate phrases (strongest signal)
    if has_boiler:
        score += 1.5 * boiler_conf
        signals.append(
            f"earmark boilerplate ({boiler_conf:.2f}): "
            f"{', '.join(boiler_matches[:2])}"
        )
    
    # Geographic specificity
    if geo_specific:
        score += 1.0 * geo_conf
        signals.append(f"geographic ({geo_conf:.2f})")
    
    # Organization specificity  
    if org_specific:
        score += 0.8 * org_conf
        signals.append(f"organization ({org_conf:.2f})")
    
    # Project specificity
    if proj_specific:
        score += 0.7 * proj_conf
        signals.append(f"project ({proj_conf:.2f})")
    
    # Amount in typical range (weak positive)
    if amount_ok:
        score += 0.3 * amount_conf
        signals.append(f"amount range ({amount_conf:.2f})")
    
    # Soft penalty for large amounts (scales with size)
    if amount and amount > 1000000:
        # Logarithmic penalty for amounts > $1M
        penalty = min(0.8, 0.2 * math.log10(amount / 1000000))
        score -= penalty
        signals.append(f"large amount penalty (-{penalty:.2f})")
    
    # Routine/statewide indicators (down-weight)
    if routine:
        score -= 0.7 * routine_conf
        signals.append(f"routine/statewide (-{routine_conf:.2f})")
    
    # Decision threshold
    threshold = 1.5
    is_earmark = score >= threshold
    
    # Confidence using sigmoid
    confidence = 1.0 / (1.0 + math.exp(-2.0 * (score - threshold)))
    confidence = max(0.1, min(0.95, confidence))  # Bound it
    
    signal_summary = ", ".join(signals)
    reasoning = (
        f"Score: {score:.2f} (threshold: {threshold}). {signal_summary}"
    )
    
    return {
        'is_earmark': is_earmark,
        'confidence': confidence,
        'geographic_specific': geo_specific,
        'organization_specific': org_specific,
        'project_specific': proj_specific,
        'routine_indicators': routine,
        'amount_in_range': amount_ok,
        'reasoning': reasoning
    }


def classify_earmarks(
    amendments: list[dict[str, Any]],
    use_llm: bool = False
) -> list[dict[str, Any]]:
    """
    Classify a list of amendments, returning only earmarks.
    
    Args:
        amendments: List of amendment dictionaries
        use_llm: Whether to use LLM for low-confidence cases
    
    Returns:
        List of amendments classified as earmarks with classification
        metadata added
    """
    earmarks = []
    llm_processor = None
    
    # Initialize LLM if requested
    if use_llm:
        llm_processor = LocalLLMProcessor()
        if not llm_processor.test_connection():
            print("[Classifier] LLM unavailable, using deterministic only")
            llm_processor = None
    
    for amendment in amendments:
        result = deterministic_classify(amendment)
        
        # Use LLM for low confidence cases
        if llm_processor and result['confidence'] < 0.7:
            try:
                llm_result = llm_processor.classify_earmark(
                    amendment.get('description', ''),
                    amendment.get('amount')
                )
                # Use LLM result if it has higher confidence
                if llm_result.get('confidence', 0) > result['confidence']:
                    result = llm_result
            except Exception as e:
                print(f"[Classifier] LLM error: {e}")
        
        if result['is_earmark']:
            # Add classification metadata to amendment
            amendment['classification'] = result
            earmarks.append(amendment)
    
    return earmarks


def is_earmark(
    amendment: dict[str, Any],
    use_llm: bool = False
) -> tuple[bool, float, dict[str, Any]]:
    """
    Determine if an amendment is an earmark.
    
    Args:
        amendment: Amendment dictionary from parser
        use_llm: Whether to use LLM for uncertain cases
    
    Returns:
        (is_earmark: bool, confidence: float, metadata: dict)
    """
    result = deterministic_classify(amendment)
    
    # Use LLM for low confidence cases
    if use_llm and result['confidence'] < 0.7:
        llm_processor = LocalLLMProcessor()
        llm_result = llm_processor.classify_earmark(
            amendment.get('description', ''),
            amendment.get('amount')
        )
        # Use LLM result if it has higher confidence
        if llm_result.get('confidence', 0) > result['confidence']:
            result = llm_result
    return result['is_earmark'], result['confidence'], result
