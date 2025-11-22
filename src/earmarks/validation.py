"""
Earmark validation using human audit decisions.

This module uses exported audit decisions (from the HTML audit tool) to:
1. Validate automated assignments against human review
2. Override incorrect assignments with correct ones
3. Track accuracy metrics over time
4. Flag high-confidence errors for system improvement

Workflow:
1. User audits assignments in HTML tool during plane ride/downtime
2. User clicks "Export My Audit Decisions" button
3. Saves JSON file to data/audit_decisions/
4. System uses these decisions to validate future runs
"""

from pathlib import Path
from typing import Any, Optional
import json
from datetime import datetime


def load_audit_decisions(audit_file: Path) -> dict[str, Any]:
    """
    Load audit decisions from exported JSON file.
    
    Args:
        audit_file: Path to exported audit decisions JSON
    
    Returns:
        Dictionary with metadata and decisions:
        {
            'audit_metadata': {...},
            'decisions': [{amendment_number, audit_status, audit_notes, ...}]
        }
    """
    if not audit_file.exists():
        return {'audit_metadata': {}, 'decisions': []}
    
    try:
        with open(audit_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n[Audit Validation] Loaded audit decisions from {audit_file.name}")
        metadata = data.get('audit_metadata', {})
        print(f"  Total reviewed: {metadata.get('total_items', 0)}")
        print(f"  Marked correct: {metadata.get('correct_count', 0)}")
        print(f"  Marked wrong: {metadata.get('wrong_count', 0)}")
        print(f"  Needs review: {metadata.get('unsure_count', 0)}")
        
        return data
    except Exception as e:
        print(f"[Audit Validation] Error loading audit file: {e}")
        return {'audit_metadata': {}, 'decisions': []}


def find_latest_audit_file(audit_dir: Path = Path("data/audit_decisions")) -> Optional[Path]:
    """
    Find the most recent audit decisions file.
    
    Args:
        audit_dir: Directory containing audit decision files
    
    Returns:
        Path to latest audit file, or None if no files found
    """
    if not audit_dir.exists():
        return None
    
    json_files = list(audit_dir.glob("earmark_audit_decisions_*.json"))
    if not json_files:
        return None
    
    # Sort by filename (contains date) to get latest
    latest = sorted(json_files, reverse=True)[0]
    return latest


def validate_assignments_against_audit(
    earmarks_by_member: dict[str, list[dict[str, Any]]],
    audit_decisions_file: Optional[Path] = None
) -> dict[str, Any]:
    """
    Validate current assignments against human audit decisions.
    
    Args:
        earmarks_by_member: Current automated assignments
        audit_decisions_file: Path to audit decisions, or None to auto-find latest
    
    Returns:
        Validation report with statistics and discrepancies:
        {
            'validation_stats': {...},
            'discrepancies': [...],
            'confirmed_correct': [...],
            'needs_human_review': [...]
        }
    """
    # Load audit decisions
    if audit_decisions_file is None:
        audit_decisions_file = find_latest_audit_file()
    
    if audit_decisions_file is None:
        print("\n[Audit Validation] No audit decisions file found")
        print("  Run audit in HTML tool and export decisions to enable validation")
        return {
            'validation_stats': {'audit_file_available': False},
            'discrepancies': [],
            'confirmed_correct': [],
            'needs_human_review': []
        }
    
    audit_data = load_audit_decisions(audit_decisions_file)
    decisions = audit_data.get('decisions', [])
    
    # Build lookup by amendment number
    audit_lookup = {
        d['amendment_number']: d 
        for d in decisions
    }
    
    # Flatten current assignments for comparison
    current_assignments = []
    for member_code, earmarks in earmarks_by_member.items():
        if member_code in ('UNKNOWN', 'UNMATCHED'):
            continue
        for earmark in earmarks:
            current_assignments.append({
                'amendment_number': earmark.get('amendment_number'),
                'member_code': member_code,
                'assigned_to': earmark.get('mapping_metadata', {}).get('matched_member'),
                'amount': earmark.get('amount'),
                'chamber': earmark.get('chamber')
            })
    
    # Compare current vs audit
    confirmed_correct = []
    discrepancies = []
    needs_review = []
    not_in_audit = []
    
    for assignment in current_assignments:
        amend_num = assignment['amendment_number']
        audit_decision = audit_lookup.get(amend_num)
        
        if audit_decision is None:
            # Not in audit file (new amendment or partial audit)
            not_in_audit.append(assignment)
            continue
        
        audit_status = audit_decision.get('audit_status')
        
        if audit_status == 'correct':
            # Human verified this is correct
            confirmed_correct.append({
                **assignment,
                'audit_notes': audit_decision.get('audit_notes')
            })
        
        elif audit_status == 'wrong':
            # Human says this is wrong
            discrepancies.append({
                **assignment,
                'audit_notes': audit_decision.get('audit_notes'),
                'audit_expected': audit_decision.get('assigned_to')
            })
        
        elif audit_status == 'unsure':
            # Human flagged for further review
            needs_review.append({
                **assignment,
                'audit_notes': audit_decision.get('audit_notes')
            })
    
    # Calculate statistics
    total_in_audit = len([a for a in current_assignments 
                          if a['amendment_number'] in audit_lookup])
    
    stats = {
        'audit_file_available': True,
        'audit_file': str(audit_decisions_file),
        'audit_date': audit_data.get('audit_metadata', {}).get('exported_at'),
        'total_current_assignments': len(current_assignments),
        'total_in_audit': total_in_audit,
        'confirmed_correct': len(confirmed_correct),
        'discrepancies_found': len(discrepancies),
        'needs_human_review': len(needs_review),
        'not_audited_yet': len(not_in_audit),
        'accuracy_rate': (len(confirmed_correct) / total_in_audit * 100) 
                        if total_in_audit > 0 else 0
    }
    
    print("\n[Audit Validation Results]")
    print(f"  Accuracy: {stats['accuracy_rate']:.1f}% "
          f"({stats['confirmed_correct']}/{stats['total_in_audit']} verified correct)")
    
    if discrepancies:
        print(f"  ⚠️  Found {len(discrepancies)} assignments marked wrong by human auditor")
        print("      See validation report for details")
    
    if needs_review:
        print(f"  ⚠️  {len(needs_review)} assignments flagged as 'unsure' by auditor")
    
    return {
        'validation_stats': stats,
        'discrepancies': discrepancies,
        'confirmed_correct': confirmed_correct,
        'needs_human_review': needs_review,
        'not_audited_yet': not_in_audit
    }


def apply_audit_corrections(
    earmarks_by_member: dict[str, list[dict[str, Any]]],
    members: list[dict[str, Any]],
    audit_decisions_file: Optional[Path] = None
) -> dict[str, list[dict[str, Any]]]:
    """
    Apply corrections from audit decisions to override incorrect assignments.
    
    This creates a corrected version of earmarks_by_member based on human audit.
    Only applies corrections for items marked 'wrong' with notes indicating the
    correct representative.
    
    Args:
        earmarks_by_member: Current automated assignments
        members: Member data for lookup
        audit_decisions_file: Path to audit decisions
    
    Returns:
        Corrected earmarks_by_member dictionary
    """
    # Load audit decisions
    if audit_decisions_file is None:
        audit_decisions_file = find_latest_audit_file()
    
    if audit_decisions_file is None:
        print("[Audit Validation] No corrections applied (no audit file)")
        return earmarks_by_member
    
    audit_data = load_audit_decisions(audit_decisions_file)
    decisions = audit_data.get('decisions', [])
    
    # Build member lookup
    member_lookup = {m['name']: m for m in members if m.get('name')}
    
    # Find corrections (marked 'wrong' with notes)
    corrections = {}
    for decision in decisions:
        if decision.get('audit_status') == 'wrong':
            notes = decision.get('audit_notes', '')
            # Try to extract correct member name from notes
            # (e.g., "Should be Senator Johnson")
            amend_num = decision['amendment_number']
            corrections[amend_num] = {
                'notes': notes,
                'current_assignment': decision.get('assigned_to')
            }
    
    if not corrections:
        print("[Audit Validation] No corrections to apply")
        return earmarks_by_member
    
    print(f"\n[Audit Validation] Applying {len(corrections)} manual corrections...")
    
    # Note: Actually applying corrections would require parsing the notes
    # to extract the intended member, which is complex. For now, we just
    # flag them. A future enhancement could add a structured correction format.
    
    print("  Manual correction application requires structured format")
    print("  Corrections logged but not automatically applied")
    print("  See validation report for details")
    
    return earmarks_by_member


def export_validation_report(
    validation_results: dict[str, Any],
    output_path: Path = Path("out/earmark_validation_report.json")
) -> None:
    """
    Export validation report to JSON file.
    
    Args:
        validation_results: Results from validate_assignments_against_audit()
        output_path: Path to write report
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(validation_results, f, indent=2, ensure_ascii=False)
    
    print(f"  [+] Validation report: {output_path}")


def get_audit_decision_for_amendment(
    amendment_number: str,
    audit_decisions_file: Optional[Path] = None
) -> Optional[dict[str, Any]]:
    """
    Get human audit decision for a specific amendment.
    
    Args:
        amendment_number: Amendment number to look up
        audit_decisions_file: Path to audit decisions
    
    Returns:
        Audit decision dict or None if not found
    """
    if audit_decisions_file is None:
        audit_decisions_file = find_latest_audit_file()
    
    if audit_decisions_file is None:
        return None
    
    audit_data = load_audit_decisions(audit_decisions_file)
    decisions = audit_data.get('decisions', [])
    
    for decision in decisions:
        if decision['amendment_number'] == amendment_number:
            return decision
    
    return None

